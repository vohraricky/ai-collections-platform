"""Seed the database with the three demo customers."""
from decimal import Decimal
from datetime import date, datetime, timedelta

from database import SessionLocal, init_db
from models import (
    Account, AccountStatus, Channel, ContactPreference, ContactStatus,
    Customer, DelinquencyBucket, HardshipProgram, HardshipType,
    Interaction, InteractionOutcome, PaymentHistory, RiskProfile,
    BureauTradeline, BankingBehavior, LifeEvent, LifeEventType, LifeEventSource,
    CustomerRiskScore,
)


def seed_demo_data():
    init_db()
    db = SessionLocal()
    try:
        if db.query(Account).filter(Account.account_number == "ACC001").first():
            return  # already seeded

        # ── Sarah Johnson ─────────────────────────────────────────────────────
        sarah = Customer(
            external_id="EXT001",
            first_name="Sarah",
            last_name="Johnson",
            timezone="America/New_York",
        )
        db.add(sarah)
        db.flush()

        sarah_acc = Account(
            account_number="ACC001",
            customer_id=sarah.id,
            credit_limit=Decimal("5000.00"),
            current_balance=Decimal("2847.50"),
            available_credit=Decimal("2152.50"),
            apr_purchase=Decimal("0.2499"),
            minimum_payment_due=Decimal("142.38"),
            days_past_due=37,
            delinquency_bucket=DelinquencyBucket.DPD_30,
            status=AccountStatus.DELINQUENT,
            opened_date=date(2017, 1, 15),
            last_payment_date=date(2025, 11, 15),
            last_payment_amount=Decimal("150.00"),
        )
        db.add(sarah_acc)
        db.flush()

        db.add_all([
            ContactPreference(customer_id=sarah.id, channel="email",
                              contact_value="sarah.j@email.com",
                              is_primary=True, is_verified=True, tcpa_consent=True),
            ContactPreference(customer_id=sarah.id, channel="voice_mobile",
                              contact_value="(555) 010-1001",
                              is_primary=True, tcpa_consent=True),
        ])
        db.add(PaymentHistory(
            account_id=sarah_acc.id,
            payment_date=date(2025, 11, 15),
            amount_paid=Decimal("150.00"),
            payment_method="ach", payment_source="online",
            status="settled", days_late=0,
        ))
        db.add(RiskProfile(
            account_id=sarah_acc.id,
            snapshot_date=date(2026, 4, 20),
            delinquency_risk_score=320,
            payment_propensity_score=72,
            hardship_probability=0.18,
            best_contact_channel="voice_mobile",
            recommended_action="EARLY_INTERVENTION",
            recommended_offer="Proactive empathy — strong retention candidate",
        ))

        # ── Marcus Thompson ───────────────────────────────────────────────────
        marcus = Customer(
            external_id="EXT002",
            first_name="Marcus",
            last_name="Thompson",
            timezone="America/Chicago",
        )
        db.add(marcus)
        db.flush()

        marcus_acc = Account(
            account_number="ACC002",
            customer_id=marcus.id,
            credit_limit=Decimal("8000.00"),
            current_balance=Decimal("7234.20"),
            available_credit=Decimal("765.80"),
            apr_purchase=Decimal("0.2249"),
            minimum_payment_due=Decimal("361.71"),
            days_past_due=68,
            delinquency_bucket=DelinquencyBucket.DPD_60,
            status=AccountStatus.DELINQUENT,
            opened_date=date(2022, 3, 10),
            last_payment_date=date(2025, 9, 30),
            last_payment_amount=Decimal("200.00"),
        )
        db.add(marcus_acc)
        db.flush()

        db.add_all([
            ContactPreference(customer_id=marcus.id, channel="email",
                              contact_value="marcus.t@email.com",
                              is_primary=True, is_verified=True, tcpa_consent=True),
            ContactPreference(customer_id=marcus.id, channel="voice_mobile",
                              contact_value="(555) 010-1002",
                              is_primary=True, tcpa_consent=True),
        ])
        db.add(PaymentHistory(
            account_id=marcus_acc.id,
            payment_date=date(2025, 9, 30),
            amount_paid=Decimal("200.00"),
            payment_method="ach", payment_source="online",
            status="settled", days_late=32,
        ))
        db.add(RiskProfile(
            account_id=marcus_acc.id,
            snapshot_date=date(2026, 4, 20),
            delinquency_risk_score=620,
            payment_propensity_score=44,
            hardship_probability=0.61,
            best_contact_channel="email",
            recommended_action="HARDSHIP_OUTREACH",
            recommended_offer="Explore hardship program — 2 months delinquent",
        ))

        # ── Elena Rodriguez ───────────────────────────────────────────────────
        elena = Customer(
            external_id="EXT003",
            first_name="Elena",
            last_name="Rodriguez",
            timezone="America/Los_Angeles",
        )
        db.add(elena)
        db.flush()

        elena_acc = Account(
            account_number="ACC003",
            customer_id=elena.id,
            credit_limit=Decimal("6000.00"),
            current_balance=Decimal("4512.80"),
            available_credit=Decimal("1487.20"),
            apr_purchase=Decimal("0.1999"),
            minimum_payment_due=Decimal("225.64"),
            days_past_due=22,
            delinquency_bucket=DelinquencyBucket.DPD_1_29,
            status=AccountStatus.DELINQUENT,
            opened_date=date(2013, 2, 5),
            last_payment_date=date(2025, 11, 1),
            last_payment_amount=Decimal("300.00"),
        )
        db.add(elena_acc)
        db.flush()

        db.add_all([
            ContactPreference(customer_id=elena.id, channel="email",
                              contact_value="elena.r@email.com",
                              is_primary=True, is_verified=True, tcpa_consent=True),
            ContactPreference(customer_id=elena.id, channel="voice_mobile",
                              contact_value="(555) 010-1003",
                              is_primary=True, tcpa_consent=True),
        ])
        db.add(PaymentHistory(
            account_id=elena_acc.id,
            payment_date=date(2025, 11, 1),
            amount_paid=Decimal("300.00"),
            payment_method="ach", payment_source="online",
            status="settled", days_late=0,
        ))
        db.add(RiskProfile(
            account_id=elena_acc.id,
            snapshot_date=date(2026, 4, 20),
            delinquency_risk_score=210,
            payment_propensity_score=81,
            hardship_probability=0.29,
            best_contact_channel="email",
            recommended_action="EARLY_INTERVENTION",
            recommended_offer="Early intervention — premium customer worth retaining",
        ))

        db.commit()
        print("Demo data seeded.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def seed_holistic_data():
    """Add bureau tradelines, banking behavior, and life events for the three demo customers."""
    from scoring import compute_customer_risk_score

    db = SessionLocal()
    try:
        # Guard: skip if holistic data already exists
        if db.query(CustomerRiskScore).first():
            return

        today = date.today()
        pull_date = today - timedelta(days=5)

        sarah = db.query(Customer).filter(Customer.external_id == "EXT001").first()
        marcus = db.query(Customer).filter(Customer.external_id == "EXT002").first()
        elena = db.query(Customer).filter(Customer.external_id == "EXT003").first()

        if not (sarah and marcus and elena):
            return  # base data not seeded yet

        # ── Sarah Johnson (ACC001) — job change, stable overall ───────────────
        db.add_all([
            BureauTradeline(
                customer_id=sarah.id, pull_date=pull_date,
                creditor_name="First National Mortgage", account_type="mortgage",
                account_status="open", credit_limit=Decimal("320000"),
                current_balance=Decimal("285000"), monthly_payment=Decimal("1875"),
                days_past_due=0, derogatory=False, bureau_source="equifax",
                opened_date=date(2019, 6, 1),
            ),
            BureauTradeline(
                customer_id=sarah.id, pull_date=pull_date,
                creditor_name="Capital One", account_type="credit_card",
                account_status="open", credit_limit=Decimal("7500"),
                current_balance=Decimal("1200"), utilization_pct=0.16,
                monthly_payment=Decimal("60"), days_past_due=0,
                derogatory=False, bureau_source="equifax",
                opened_date=date(2020, 3, 15),
            ),
            BureauTradeline(
                customer_id=sarah.id, pull_date=pull_date,
                creditor_name="Toyota Financial", account_type="auto_loan",
                account_status="open", credit_limit=Decimal("28000"),
                current_balance=Decimal("14500"), monthly_payment=Decimal("420"),
                days_past_due=0, derogatory=False, bureau_source="equifax",
                opened_date=date(2022, 9, 1),
            ),
        ])
        db.add(BankingBehavior(
            customer_id=sarah.id, observation_date=today, period_days=30,
            checking_avg_balance=Decimal("2800"), checking_min_balance=Decimal("850"),
            direct_deposit_present=True, direct_deposit_amount=Decimal("4200"),
            direct_deposit_change_pct=-0.12,   # modest income dip (new job transition)
            nsf_count=0, overdraft_count=0,
            savings_avg_balance=Decimal("12000"), savings_change_pct=-0.05,
            spend_total=Decimal("3600"), spend_essentials_pct=0.62,
            liquidity_score=0.72,
        ))
        db.add(LifeEvent(
            customer_id=sarah.id,
            event_type=LifeEventType.JOB_CHANGE,
            event_date=today - timedelta(days=45),
            detected_date=today - timedelta(days=40),
            source=LifeEventSource.EMPLOYMENT_RECORD,
            confidence=0.80, impact_on_income="neutral",
            income_change_pct=-0.12,
            description="Employment record shows employer change; income temporarily reduced during transition.",
            resolved=False,
            expires_at=today + timedelta(days=90),
        ))

        # ── Marcus Thompson (ACC002) — job loss, severe cross-creditor stress ──
        marcus_acc = db.query(Account).filter(Account.account_number == "ACC002").first()
        db.add_all([
            BureauTradeline(
                customer_id=marcus.id, pull_date=pull_date,
                creditor_name="Chase Auto Finance", account_type="auto_loan",
                account_status="derogatory", credit_limit=Decimal("35000"),
                current_balance=Decimal("31200"), monthly_payment=Decimal("580"),
                days_past_due=62, times_30_dpd=2, times_60_dpd=1,
                derogatory=True, derogatory_date=today - timedelta(days=20),
                bureau_source="transunion",
                opened_date=date(2021, 5, 10),
            ),
            BureauTradeline(
                customer_id=marcus.id, pull_date=pull_date,
                creditor_name="Discover Bank", account_type="credit_card",
                account_status="open", credit_limit=Decimal("6000"),
                current_balance=Decimal("5780"), utilization_pct=0.96,
                monthly_payment=Decimal("145"), days_past_due=30,
                times_30_dpd=1, derogatory=False, bureau_source="transunion",
                opened_date=date(2019, 11, 1),
            ),
            BureauTradeline(
                customer_id=marcus.id, pull_date=pull_date,
                creditor_name="Citibank Personal", account_type="personal_loan",
                account_status="open", credit_limit=Decimal("10000"),
                current_balance=Decimal("9400"), monthly_payment=Decimal("290"),
                days_past_due=0, derogatory=False, bureau_source="transunion",
                opened_date=date(2023, 2, 15),
            ),
        ])
        db.add(BankingBehavior(
            customer_id=marcus.id, observation_date=today, period_days=30,
            checking_avg_balance=Decimal("340"), checking_min_balance=Decimal("12"),
            direct_deposit_present=False,           # income stopped
            direct_deposit_amount=Decimal("0"),
            direct_deposit_change_pct=-1.0,          # full income shock
            nsf_count=4, overdraft_count=3,
            overdraft_amount_total=Decimal("1240"),
            atm_cash_withdrawal_total=Decimal("800"),
            savings_avg_balance=Decimal("200"), savings_change_pct=-0.88,
            savings_withdrawal_count=6,
            spend_total=Decimal("1800"), spend_essentials_pct=0.89,
            liquidity_score=0.08,
        ))
        db.add(LifeEvent(
            customer_id=marcus.id,
            account_id=marcus_acc.id if marcus_acc else None,
            event_type=LifeEventType.JOB_LOSS,
            event_date=today - timedelta(days=75),
            detected_date=today - timedelta(days=70),
            source=LifeEventSource.BEHAVIORAL_INFERRED,
            confidence=0.90, impact_on_income="negative",
            income_change_pct=-1.0,
            description="Direct deposit stopped 10 weeks ago. NSF events and savings depletion pattern consistent with unemployment.",
            resolved=False,
            expires_at=today + timedelta(days=180),
        ))

        # ── Elena Rodriguez (ACC003) — medical emergency, depleted savings ─────
        elena_acc = db.query(Account).filter(Account.account_number == "ACC003").first()
        db.add_all([
            BureauTradeline(
                customer_id=elena.id, pull_date=pull_date,
                creditor_name="Great Lakes Student Loans", account_type="student_loan",
                account_status="open", credit_limit=Decimal("45000"),
                current_balance=Decimal("18200"), monthly_payment=Decimal("210"),
                days_past_due=0, derogatory=False, bureau_source="experian",
                opened_date=date(2015, 8, 1),
            ),
            BureauTradeline(
                customer_id=elena.id, pull_date=pull_date,
                creditor_name="Bank of America", account_type="credit_card",
                account_status="open", credit_limit=Decimal("9000"),
                current_balance=Decimal("3150"), utilization_pct=0.35,
                monthly_payment=Decimal("95"), days_past_due=0,
                derogatory=False, bureau_source="experian",
                opened_date=date(2016, 4, 20),
            ),
        ])
        db.add(BankingBehavior(
            customer_id=elena.id, observation_date=today, period_days=30,
            checking_avg_balance=Decimal("1100"), checking_min_balance=Decimal("180"),
            direct_deposit_present=True, direct_deposit_amount=Decimal("5800"),
            direct_deposit_change_pct=0.0,
            nsf_count=1, overdraft_count=1,
            savings_avg_balance=Decimal("800"), savings_change_pct=-0.72,
            savings_withdrawal_count=5,
            spend_total=Decimal("4900"), spend_essentials_pct=0.71,
            liquidity_score=0.32,
        ))
        db.add(LifeEvent(
            customer_id=elena.id,
            account_id=elena_acc.id if elena_acc else None,
            event_type=LifeEventType.MEDICAL_DIAGNOSIS,
            event_date=today - timedelta(days=60),
            detected_date=today - timedelta(days=55),
            source=LifeEventSource.SELF_REPORTED,
            confidence=1.0, impact_on_income="negative",
            income_change_pct=-0.20,
            description="Customer disclosed medical emergency during chat interaction. Savings depleted covering out-of-pocket costs.",
            resolved=False,
            expires_at=today + timedelta(days=150),
        ))

        db.flush()

        # ── Generate CustomerRiskScore for each ───────────────────────────────
        for customer in (sarah, marcus, elena):
            score = compute_customer_risk_score(customer.id, db)
            if score:
                db.add(score)

        db.commit()
        print("Holistic data seeded.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_data()
    seed_holistic_data()
    print("Done.")
