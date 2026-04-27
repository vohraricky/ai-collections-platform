"""
Holistic customer risk scoring engine.

Aggregates signals across all accounts, bureau tradelines, banking behavior,
and life events to produce a CustomerRiskScore snapshot.

Component weights (must sum to 1.0):
  payment_capacity      0.30  — income vs obligations; strongest charge-off predictor
  cross_creditor_stress 0.25  — bureau picture across all creditors
  behavioral_stability  0.20  — on-us behavioral signals
  banking_liquidity     0.15  — checking/savings health and income signals
  life_event_impact     0.05  — active life event penalty
  engagement            0.05  — responsiveness and promise reliability

Each component scores 0-100 (higher = less risk).
Composite → holistic_risk_score 0-1000 (higher = more risk).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from math import exp

from database import SessionLocal
from models import (
    Account, BankingBehavior, BureauTradeline, ContactStatus,
    Customer, CustomerRiskScore, LifeEvent, LifeEventType,
)

_WEIGHTS = {
    "payment_capacity":      0.30,
    "cross_creditor_stress": 0.25,
    "behavioral_stability":  0.20,
    "banking_liquidity":     0.15,
    "life_event_impact":     0.05,
    "engagement":            0.05,
}

_LIFE_EVENT_SEVERITY = {
    LifeEventType.JOB_LOSS:            1.0,
    LifeEventType.BANKRUPTCY:          1.0,
    LifeEventType.MEDICAL_DIAGNOSIS:   0.85,
    LifeEventType.DEATH_IN_FAMILY:     0.75,
    LifeEventType.DIVORCE:             0.70,
    LifeEventType.INCOME_REDUCTION:    0.65,
    LifeEventType.MILITARY_DEPLOYMENT: 0.55,
    LifeEventType.JOB_CHANGE:          0.45,
    LifeEventType.NEW_DEPENDENT:       0.30,
    LifeEventType.RELOCATION:          0.20,
    LifeEventType.NATURAL_DISASTER:    0.80,
    LifeEventType.OTHER:               0.40,
}


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> int:
    return int(max(lo, min(hi, v)))


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + exp(-z))


# ── Component scoring ──────────────────────────────────────────────────────────

def _payment_capacity(customer: Customer, banking: BankingBehavior | None,
                      tradelines: list, own_accounts: list) -> tuple[int, float, float]:
    """Returns (score 0-100, monthly_income, monthly_obligations)."""
    # Income estimate: banking DD > employment record
    monthly_income = 0.0
    if banking and banking.direct_deposit_amount:
        monthly_income = float(banking.direct_deposit_amount)
    elif customer.employment_records:
        emp = customer.employment_records[0]
        if emp.annual_income:
            monthly_income = float(emp.annual_income) / 12

    # Obligations: bureau tradeline payments + own account minimums
    bureau_obligations = sum(float(t.monthly_payment or 0) for t in tradelines)
    own_obligations    = sum(float(a.minimum_payment_due or 0) for a in own_accounts)
    total_obligations  = bureau_obligations + own_obligations

    if monthly_income > 0:
        dti = total_obligations / monthly_income
        score = _clamp(100 * (1.0 - min(dti * 1.5, 1.0)))
    else:
        score = 35  # unknown income = moderate risk

    return score, monthly_income, total_obligations


def _cross_creditor_stress(tradelines: list) -> tuple[int, int, int]:
    """Returns (score 0-100, derogatory_count, max_dpd)."""
    if not tradelines:
        return 60, 0, 0   # no bureau data = slight uncertainty

    derogatory_count = sum(1 for t in tradelines if t.derogatory)
    max_dpd          = max((t.days_past_due or 0) for t in tradelines)

    revolving = [t for t in tradelines if (t.credit_limit or 0) > 0 and t.utilization_pct is not None]
    avg_util  = (
        sum(t.utilization_pct for t in revolving) / len(revolving)
        if revolving else 0.0
    )

    score = 100.0
    score -= min(derogatory_count * 15, 50)
    score -= min(avg_util * 25, 25)
    score -= min(max_dpd / 3.0, 25)     # 90 DPD → -25 pts max

    return _clamp(score), derogatory_count, max_dpd


def _behavioral_stability(customer: Customer) -> int:
    """Score 0-100 based on on-us behavioral signals and account DPD."""
    score = 100.0
    today_90 = date.today() - timedelta(days=90)

    for acc in customer.accounts:
        # Account-level DPD penalty
        if acc.days_past_due >= 90:
            score -= 20
        elif acc.days_past_due >= 60:
            score -= 12
        elif acc.days_past_due >= 30:
            score -= 6

        if acc.hardship_enrolled:
            score -= 8

        # Behavioral signal penalties (last 90 days)
        for sig in acc.behavioral_signals:
            if sig.signal_date < today_90:
                continue
            sev = sig.severity.value if sig.severity else "medium"
            score -= {"critical": 20, "high": 10, "medium": 4, "low": 1}.get(sev, 4)

    return _clamp(score)


def _banking_liquidity(banking: BankingBehavior | None) -> int:
    """Score 0-100 from banking behavior snapshot."""
    if not banking:
        return 50

    base = (banking.liquidity_score or 0.5) * 100

    # NSF / overdraft penalties
    base -= min((banking.nsf_count or 0) * 10, 30)
    base -= min((banking.overdraft_count or 0) * 8, 20)

    # Income shock signals
    if banking.direct_deposit_present is False:
        base -= 28
    elif banking.direct_deposit_change_pct is not None:
        if banking.direct_deposit_change_pct < -0.20:
            base -= 15
        elif banking.direct_deposit_change_pct < -0.10:
            base -= 8

    # Savings depletion
    if banking.savings_change_pct is not None and banking.savings_change_pct < -0.30:
        base -= 10

    return _clamp(base)


def _life_event_impact(customer: Customer) -> tuple[int, list]:
    """Returns (score 0-100, list of active event type strings)."""
    active = customer.active_life_events
    if not active:
        return 100, []

    today = date.today()
    penalty = 0.0
    active_types = []

    for ev in active:
        if ev.impact_on_income == "positive":
            continue                         # skip positive events

        weight      = _LIFE_EVENT_SEVERITY.get(ev.event_type, 0.40)
        confidence  = ev.confidence or 1.0
        months_old  = (today - ev.event_date).days / 30.0
        decay       = 1.0 if months_old < 3 else 0.70 if months_old < 6 else 0.50

        penalty += weight * confidence * decay * 40   # max 40 pts per event
        active_types.append(ev.event_type.value)

    return _clamp(100 - penalty), active_types


def _engagement(customer: Customer) -> int:
    """Score 0-100 based on contact responsiveness and promise reliability."""
    interactions = [i for acc in customer.accounts for i in acc.interactions]
    if not interactions:
        return 50

    outbound   = [i for i in interactions if i.direction == "outbound"]
    connected  = [i for i in outbound if i.contact_status == ContactStatus.CONNECTED]
    contact_rate = len(connected) / len(outbound) if outbound else 0.5

    sentiments = [i.sentiment_score for i in interactions if i.sentiment_score is not None]
    avg_sent   = sum(sentiments) / len(sentiments) if sentiments else 0.0
    sent_norm  = (avg_sent + 1.0) / 2.0     # -1..1 → 0..1

    ptps  = [i for i in interactions if i.promise_to_pay_amount]
    kept  = [i for i in ptps if i.promise_kept]
    ptp_rate = len(kept) / len(ptps) if ptps else 0.5

    return _clamp(contact_rate * 40 + sent_norm * 30 + ptp_rate * 30)


# ── Public API ─────────────────────────────────────────────────────────────────

def compute_customer_risk_score(customer_id: str, db=None) -> CustomerRiskScore | None:
    """
    Compute a holistic CustomerRiskScore for the given customer.

    If db is provided, uses that session (does NOT commit).
    Otherwise opens its own session and closes it after.
    Returns the unsaved CustomerRiskScore ORM object, or None if customer not found.
    """
    own_session = db is None
    if own_session:
        db = SessionLocal()

    try:
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            return None

        today = date.today()

        # Latest bureau pull
        latest_pull = (
            db.query(BureauTradeline.pull_date)
            .filter(BureauTradeline.customer_id == customer_id)
            .order_by(BureauTradeline.pull_date.desc())
            .first()
        )
        tradelines = []
        if latest_pull:
            tradelines = (
                db.query(BureauTradeline)
                .filter(
                    BureauTradeline.customer_id == customer_id,
                    BureauTradeline.pull_date == latest_pull[0],
                )
                .all()
            )

        # Latest banking snapshot
        banking = (
            db.query(BankingBehavior)
            .filter(BankingBehavior.customer_id == customer_id)
            .order_by(BankingBehavior.observation_date.desc())
            .first()
        )

        own_accounts = customer.accounts

        # ── Compute component scores ──────────────────────────────────────
        cap_score, monthly_income, monthly_obligations = _payment_capacity(
            customer, banking, tradelines, own_accounts
        )
        ccs_score, derog_count, cross_max_dpd = _cross_creditor_stress(tradelines)
        beh_score = _behavioral_stability(customer)
        liq_score = _banking_liquidity(banking)
        lev_score, active_event_types = _life_event_impact(customer)
        eng_score = _engagement(customer)

        scores = {
            "payment_capacity":      cap_score,
            "cross_creditor_stress": ccs_score,
            "behavioral_stability":  beh_score,
            "banking_liquidity":     liq_score,
            "life_event_impact":     lev_score,
            "engagement":            eng_score,
        }

        # ── Composite ────────────────────────────────────────────────────
        composite = sum(_WEIGHTS[k] * scores[k] for k in _WEIGHTS)
        holistic  = round((1.0 - composite / 100.0) * 1000)

        if holistic < 200:   tier = "very_low"
        elif holistic < 400: tier = "low"
        elif holistic < 600: tier = "medium"
        elif holistic < 800: tier = "high"
        else:                tier = "critical"

        # ── Predictions ─────────────────────────────────────────────────
        own_dpd_max = max((a.days_past_due for a in own_accounts), default=0)
        delinquent  = [a for a in own_accounts if a.days_past_due > 0]

        z = -4.0
        z += (holistic / 1000) * 5.0
        z += max(0, cross_max_dpd - 30) * 0.03
        z += derog_count * 0.4
        z += (1.0 - cap_score / 100.0) * 2.0
        z += (1.0 if active_event_types else 0.0) * 0.8
        chargeoff_risk = round(_sigmoid(z), 3)

        cure = round(min(0.99, max(0.01,
            1.0 - chargeoff_risk
            + (eng_score / 100) * 0.10
            + (cap_score / 100) * 0.10
        )), 3)

        if chargeoff_risk > 0.70 or holistic > 800:   urgency = "critical"
        elif chargeoff_risk > 0.50 or holistic > 600: urgency = "urgent"
        elif chargeoff_risk > 0.30 or holistic > 400: urgency = "engage"
        elif chargeoff_risk > 0.12:                   urgency = "monitor"
        else:                                          urgency = "none"

        # ── Recommendations ──────────────────────────────────────────────
        if lev_score < 60 and active_event_types:
            strategy  = "Lead with hardship program — life event is the primary driver. Focus on empathy and relief."
            offer_priority = ["hardship", "payment_plan", "payment_deferral"]
        elif cap_score < 40:
            strategy  = "Structured payment plan — income constrained vs obligations. Sustainable installments first."
            offer_priority = ["payment_plan", "reduced_interest", "hardship"]
        elif chargeoff_risk > 0.55:
            strategy  = "Immediate engagement required — high charge-off risk. Offer maximum flexibility."
            offer_priority = ["full_hardship", "payment_plan", "settlement"]
        elif holistic < 250:
            strategy  = "Proactive retention — this appears to be an isolated incident. Relationship-first, concession if needed."
            offer_priority = ["payment_plan", "fee_waiver"]
        else:
            strategy  = "Flexible engagement — offer payment plan or hardship program based on conversation."
            offer_priority = ["payment_plan", "hardship", "reduced_interest"]

        # Primary driver = weakest component
        primary_driver = min(scores, key=scores.get).replace("_", " ")

        dti = round(monthly_obligations / monthly_income, 3) if monthly_income > 0 else None

        feature_vector = {
            **{f"score_{k}": v for k, v in scores.items()},
            "composite_0_100": round(composite, 2),
            "dti": dti,
            "bureau_tradeline_count": len(tradelines),
            "own_account_count": len(own_accounts),
            "active_life_events": len(active_event_types),
        }

        return CustomerRiskScore(
            customer_id                 = customer_id,
            snapshot_date               = today,
            holistic_risk_score         = holistic,
            holistic_risk_tier          = tier,
            payment_capacity_score      = cap_score,
            cross_creditor_stress_score = ccs_score,
            behavioral_stability_score  = beh_score,
            banking_liquidity_score     = liq_score,
            life_event_impact_score     = lev_score,
            engagement_score            = eng_score,
            estimated_monthly_income    = round(monthly_income, 2) if monthly_income else None,
            total_monthly_obligations   = round(monthly_obligations, 2) if monthly_obligations else None,
            debt_to_income_ratio        = dti,
            bureau_derogatory_count     = derog_count,
            cross_creditor_max_dpd      = cross_max_dpd,
            active_life_event           = bool(active_event_types),
            active_life_event_types     = active_event_types,
            accounts_delinquent         = len(delinquent),
            accounts_total              = len(own_accounts),
            max_dpd_own_accounts        = own_dpd_max,
            total_own_exposure          = round(sum(float(a.current_balance) for a in own_accounts), 2),
            predicted_chargeoff_risk    = chargeoff_risk,
            predicted_cure_probability  = cure,
            intervention_urgency        = urgency,
            recommended_strategy        = strategy,
            recommended_offer_priority  = offer_priority,
            primary_risk_driver         = primary_driver,
            feature_vector              = feature_vector,
        )

    finally:
        if own_session:
            db.close()


def build_customer_360_payload(account_number: str) -> dict:
    """
    Return the full Customer 360 payload for a given account number.
    Computes a fresh score if none exists for today. Returns serializable dict.
    """
    db = SessionLocal()
    try:
        from models import Account as Acc
        acc = db.query(Acc).filter(Acc.account_number == account_number.upper()).first()
        if not acc:
            return {"found": False}

        customer = acc.customer
        today    = date.today()

        # Use today's score or compute fresh
        existing = (
            db.query(CustomerRiskScore)
            .filter(
                CustomerRiskScore.customer_id == customer.id,
                CustomerRiskScore.snapshot_date == today,
            )
            .first()
        )
        if not existing:
            existing = compute_customer_risk_score(customer.id, db)
            if existing:
                db.add(existing)
                db.commit()
                db.refresh(existing)

        # Latest bureau pull
        latest_pull = (
            db.query(BureauTradeline.pull_date)
            .filter(BureauTradeline.customer_id == customer.id)
            .order_by(BureauTradeline.pull_date.desc())
            .first()
        )
        tradelines = []
        if latest_pull:
            tradelines = (
                db.query(BureauTradeline)
                .filter(
                    BureauTradeline.customer_id == customer.id,
                    BureauTradeline.pull_date == latest_pull[0],
                )
                .all()
            )

        banking = (
            db.query(BankingBehavior)
            .filter(BankingBehavior.customer_id == customer.id)
            .order_by(BankingBehavior.observation_date.desc())
            .first()
        )

        active_events = customer.active_life_events

        payload: dict = {
            "found": True,
            "account_number": account_number.upper(),
            "customer_name": f"{customer.first_name} {customer.last_name}",
        }

        if existing:
            payload.update({
                "holistic_risk_score":         existing.holistic_risk_score,
                "holistic_risk_tier":          existing.holistic_risk_tier,
                "intervention_urgency":        existing.intervention_urgency,
                "predicted_chargeoff_risk":    existing.predicted_chargeoff_risk,
                "predicted_cure_probability":  existing.predicted_cure_probability,
                "recommended_strategy":        existing.recommended_strategy,
                "recommended_offer_priority":  existing.recommended_offer_priority,
                "primary_risk_driver":         existing.primary_risk_driver,
                "debt_to_income_ratio":        existing.debt_to_income_ratio,
                "estimated_monthly_income":    float(existing.estimated_monthly_income) if existing.estimated_monthly_income else None,
                "total_monthly_obligations":   float(existing.total_monthly_obligations) if existing.total_monthly_obligations else None,
                "component_scores": {
                    "payment_capacity":      existing.payment_capacity_score,
                    "cross_creditor_stress": existing.cross_creditor_stress_score,
                    "behavioral_stability":  existing.behavioral_stability_score,
                    "banking_liquidity":     existing.banking_liquidity_score,
                    "life_event_impact":     existing.life_event_impact_score,
                    "engagement":            existing.engagement_score,
                },
                "accounts_delinquent": existing.accounts_delinquent,
                "accounts_total":      existing.accounts_total,
                "max_dpd_own":         existing.max_dpd_own_accounts,
                "total_own_exposure":  float(existing.total_own_exposure) if existing.total_own_exposure else None,
                "scored_at":           existing.snapshot_date.isoformat(),
            })

        payload["bureau_summary"] = {
            "pull_date":            latest_pull[0].isoformat() if latest_pull else None,
            "total_tradelines":     len(tradelines),
            "derogatory_count":     sum(1 for t in tradelines if t.derogatory),
            "cross_creditor_max_dpd": max((t.days_past_due or 0) for t in tradelines) if tradelines else 0,
            "tradelines": [
                {
                    "creditor":       t.creditor_name,
                    "type":           t.account_type,
                    "balance":        float(t.current_balance or 0),
                    "limit":          float(t.credit_limit) if t.credit_limit else None,
                    "utilization_pct": round(t.utilization_pct * 100, 1) if t.utilization_pct else None,
                    "days_past_due":  t.days_past_due or 0,
                    "status":         t.account_status,
                    "derogatory":     t.derogatory,
                    "opened":         t.opened_date.isoformat() if t.opened_date else None,
                }
                for t in tradelines
            ],
        }

        payload["banking_behavior"] = {
            "observation_date":          banking.observation_date.isoformat() if banking else None,
            "liquidity_score":           banking.liquidity_score if banking else None,
            "direct_deposit_present":    banking.direct_deposit_present if banking else None,
            "direct_deposit_amount":     float(banking.direct_deposit_amount) if banking and banking.direct_deposit_amount else None,
            "direct_deposit_change_pct": banking.direct_deposit_change_pct if banking else None,
            "checking_avg_balance":      float(banking.checking_avg_balance) if banking and banking.checking_avg_balance else None,
            "checking_min_balance":      float(banking.checking_min_balance) if banking and banking.checking_min_balance else None,
            "nsf_count":                 banking.nsf_count if banking else 0,
            "overdraft_count":           banking.overdraft_count if banking else 0,
            "savings_avg_balance":       float(banking.savings_avg_balance) if banking and banking.savings_avg_balance else None,
            "savings_change_pct":        banking.savings_change_pct if banking else None,
            "spend_essentials_pct":      banking.spend_essentials_pct if banking else None,
        } if banking else None

        payload["active_life_events"] = [
            {
                "type":           e.event_type.value,
                "date":           e.event_date.isoformat(),
                "source":         e.source.value,
                "confidence":     e.confidence,
                "income_impact":  e.impact_on_income,
                "income_change_pct": e.income_change_pct,
                "description":    e.description,
                "resolved":       e.resolved,
            }
            for e in active_events
        ]

        payload["all_accounts"] = [
            {
                "account_number":  a.account_number,
                "balance":         float(a.current_balance),
                "credit_limit":    float(a.credit_limit),
                "days_past_due":   a.days_past_due,
                "status":          a.status.value if a.status else None,
                "is_this_account": a.account_number == account_number.upper(),
            }
            for a in customer.accounts
        ]

        return payload

    finally:
        db.close()
