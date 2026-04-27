"""Proactive outreach engine — candidate selection and dispatch recording."""
from datetime import datetime, timedelta

from database import SessionLocal
from models import (
    Account, AccountStatus, BehavioralSignal,
    Channel, ContactStatus, Interaction, InteractionOutcome,
)


def _risk_tier(score: int | None) -> str:
    if score is None:
        return "Unknown"
    if score < 400:
        return "Low"
    if score < 700:
        return "Medium"
    return "High"


def select_candidates() -> list[dict]:
    """
    Return accounts that need proactive outreach, sorted by urgency.

    Eligibility:
    - Status DELINQUENT, 1–90 DPD
    - do_not_contact = False
    - No active payment plan or hardship enrollment
    - No outbound interaction in the last 7 days
    """
    db = SessionLocal()
    try:
        seven_days_ago = datetime.utcnow() - timedelta(days=7)

        accounts = (
            db.query(Account)
            .filter(
                Account.do_not_contact == False,
                Account.status == AccountStatus.DELINQUENT,
                Account.days_past_due > 0,
                Account.days_past_due <= 90,
                Account.payment_plan_active == False,
                Account.hardship_enrolled == False,
            )
            .all()
        )

        results = []
        for acc in accounts:
            # Skip if contacted outbound recently
            recently_contacted = any(
                i.direction == "outbound"
                and i.interaction_datetime >= seven_days_ago
                for i in acc.interactions
            )
            if recently_contacted:
                continue

            cust = acc.customer
            prefs = cust.contact_preferences
            email = next((p.contact_value for p in prefs if p.channel == "email"), None)
            phone = next((p.contact_value for p in prefs if p.channel == "voice_mobile"), None)
            last_pmt = acc.payment_history[0] if acc.payment_history else None
            risk = acc.latest_risk
            unprocessed = sum(1 for s in acc.behavioral_signals if not s.processed)

            candidate = {
                "account_number": acc.account_number,
                "name": f"{cust.first_name} {cust.last_name}",
                "email": email,
                "phone": phone,
                "balance": float(acc.current_balance),
                "days_past_due": acc.days_past_due,
                "delinquency_bucket": acc.delinquency_bucket.value if acc.delinquency_bucket else None,
                "hardship_enrolled": acc.hardship_enrolled,
                "unprocessed_signals": unprocessed,
            }

            if last_pmt:
                candidate["last_payment"] = {
                    "date": last_pmt.payment_date.strftime("%b %d, %Y"),
                    "amount": float(last_pmt.amount_paid),
                }

            if risk:
                candidate.update({
                    "risk_tier": _risk_tier(risk.delinquency_risk_score),
                    "hardship_probability": risk.hardship_probability,
                    "payment_propensity_score": risk.payment_propensity_score,
                    "recommended_action": risk.recommended_action,
                    "suggested_action": risk.recommended_offer,
                    "best_contact_channel": risk.best_contact_channel,
                })
            else:
                candidate.update({"risk_tier": "Unknown", "best_contact_channel": "email"})

            results.append(candidate)

        results.sort(key=lambda x: x["days_past_due"], reverse=True)
        return results
    finally:
        db.close()


_CHANNEL_MAP = {
    "email": Channel.OUTBOUND_EMAIL,
    "sms":   Channel.OUTBOUND_SMS,
    "voice": Channel.OUTBOUND_CALL,
}


def record_dispatch(account_number: str, channel: str, message: str) -> dict:
    """
    Record an outbound outreach attempt as an Interaction row.
    Marks all unprocessed BehavioralSignals as processed.
    """
    db = SessionLocal()
    try:
        acc = (
            db.query(Account)
            .filter(Account.account_number == account_number.upper().strip())
            .first()
        )
        if not acc:
            return {"success": False, "error": "Account not found"}

        cust = acc.customer

        interaction = Interaction(
            account_id=acc.id,
            customer_id=acc.customer_id,
            channel=_CHANNEL_MAP.get(channel, Channel.OUTBOUND_EMAIL),
            direction="outbound",
            initiated_by="ai_agent",
            is_ai_handled=True,
            ai_agent_version="alex-outreach-v1",
            contact_status=ContactStatus.VOICEMAIL,
            outcome=InteractionOutcome.NO_CONTACT,
            fdcpa_disclosure_given=True,
            notes=message,
        )
        db.add(interaction)

        for signal in acc.behavioral_signals:
            if not signal.processed:
                signal.processed = True
                signal.processed_at = datetime.utcnow()

        db.commit()

        return {
            "success": True,
            "interaction_id": interaction.id[:8].upper(),
            "account_number": account_number,
            "channel": channel,
            "confirmation": f"Outreach logged for {cust.first_name} {cust.last_name}.",
        }
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()
