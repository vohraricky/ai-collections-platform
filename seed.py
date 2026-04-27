"""Seed the database with the three demo customers."""
from decimal import Decimal
from datetime import date, datetime

from database import SessionLocal, init_db
from models import (
    Account, AccountStatus, Channel, ContactPreference, ContactStatus,
    Customer, DelinquencyBucket, HardshipProgram, HardshipType,
    Interaction, InteractionOutcome, PaymentHistory, RiskProfile,
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


if __name__ == "__main__":
    seed_demo_data()
    print("Done.")
