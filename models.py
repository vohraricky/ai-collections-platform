"""
Collections Platform — Data Model
Customer 360 | Delinquency Signals | Contact History | Compliance
"""
import enum
import uuid
from datetime import datetime
from sqlalchemy import (
    Boolean, Column, Date, DateTime, Float, ForeignKey, Index,
    Integer, JSON, Numeric, String, Text, Enum as SAEnum,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def _uuid() -> str:
    return str(uuid.uuid4())


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────

class DelinquencyBucket(str, enum.Enum):
    CURRENT  = "current"
    DPD_1_29 = "dpd_1_29"
    DPD_30   = "dpd_30"
    DPD_60   = "dpd_60"
    DPD_90   = "dpd_90"
    DPD_120  = "dpd_120"
    DPD_150  = "dpd_150"
    DPD_180  = "dpd_180"
    CHARGEOFF = "chargeoff"


class AccountStatus(str, enum.Enum):
    ACTIVE     = "active"
    DELINQUENT = "delinquent"
    SUSPENDED  = "suspended"
    CLOSED     = "closed"
    CHARGEOFF  = "chargeoff"
    FRAUD      = "fraud"


class EmploymentStatus(str, enum.Enum):
    EMPLOYED      = "employed"
    SELF_EMPLOYED = "self_employed"
    UNEMPLOYED    = "unemployed"
    RETIRED       = "retired"
    STUDENT       = "student"
    DISABLED      = "disabled"


class Channel(str, enum.Enum):
    INBOUND_CALL    = "inbound_call"
    OUTBOUND_CALL   = "outbound_call"
    INBOUND_SMS     = "inbound_sms"
    OUTBOUND_SMS    = "outbound_sms"
    INBOUND_EMAIL   = "inbound_email"
    OUTBOUND_EMAIL  = "outbound_email"
    INBOUND_CHAT    = "inbound_chat"
    OUTBOUND_CHAT   = "outbound_chat"
    OUTBOUND_LETTER = "outbound_letter"
    IVR             = "ivr"


class ContactStatus(str, enum.Enum):
    CONNECTED    = "connected"
    NO_ANSWER    = "no_answer"
    VOICEMAIL    = "voicemail"
    WRONG_NUMBER = "wrong_number"
    DISCONNECTED = "disconnected"
    BUSY         = "busy"
    BLOCKED      = "blocked"


class InteractionOutcome(str, enum.Enum):
    PAYMENT_MADE        = "payment_made"
    PAYMENT_PROMISED    = "payment_promised"
    HARDSHIP_IDENTIFIED = "hardship_identified"
    ARRANGEMENT_SET     = "arrangement_set"
    DISPUTE_RAISED      = "dispute_raised"
    NO_RESOLUTION       = "no_resolution"
    REFUSED_TO_PAY      = "refused_to_pay"
    COMPLAINT_RAISED    = "complaint_raised"
    CEASE_AND_DESIST    = "cease_and_desist"
    NO_CONTACT          = "no_contact"


class ArrangementType(str, enum.Enum):
    PAYMENT_PLAN      = "payment_plan"
    SETTLEMENT        = "settlement"
    DEFERRAL          = "deferral"
    MINIMUM_REDUCTION = "minimum_reduction"


class ArrangementStatus(str, enum.Enum):
    ACTIVE    = "active"
    COMPLETED = "completed"
    BROKEN    = "broken"
    CANCELLED = "cancelled"


class HardshipType(str, enum.Enum):
    JOB_LOSS            = "job_loss"
    MEDICAL_EMERGENCY   = "medical_emergency"
    DIVORCE_SEPARATION  = "divorce_separation"
    DEATH_IN_FAMILY     = "death_in_family"
    NATURAL_DISASTER    = "natural_disaster"
    MILITARY_DEPLOYMENT = "military_deployment"
    INCOME_REDUCTION    = "income_reduction"
    OTHER               = "other"


class HardshipProgram(str, enum.Enum):
    REDUCED_INTEREST = "reduced_interest"
    FEE_WAIVER       = "fee_waiver"
    PAYMENT_DEFERRAL = "payment_deferral"
    FULL_HARDSHIP    = "full_hardship"
    CUSTOM           = "custom"


class HardshipStatus(str, enum.Enum):
    ACTIVE    = "active"
    COMPLETED = "completed"
    EXPIRED   = "expired"
    REVOKED   = "revoked"


class SignalType(str, enum.Enum):
    SPENDING_DECLINE        = "spending_decline"
    SPENDING_INCREASE       = "spending_increase"
    LOGIN_FREQUENCY_DROP    = "login_frequency_drop"
    PAYMENT_VELOCITY_CHANGE = "payment_velocity_change"
    MINIMUM_PAYMENT_ONLY    = "minimum_payment_only"
    PARTIAL_PAYMENT         = "partial_payment"
    RETURNED_PAYMENT        = "returned_payment"
    CASH_ADVANCE            = "cash_advance"
    OVERLIMIT               = "overlimit"
    MISSED_PAYMENT          = "missed_payment"
    BUREAU_DEROGATORY       = "bureau_derogatory"


class SignalSeverity(str, enum.Enum):
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


class ComplianceEventType(str, enum.Enum):
    FDCPA_DISCLOSURE       = "fdcpa_disclosure"
    MINI_MIRANDA_GIVEN     = "mini_miranda_given"
    TCPA_CONSENT_VERIFIED  = "tcpa_consent_verified"
    TCPA_CONSENT_OBTAINED  = "tcpa_consent_obtained"
    OPT_OUT_HONORED        = "opt_out_honored"
    DISPUTE_RECEIVED       = "dispute_received"
    DISPUTE_ACKNOWLEDGED   = "dispute_acknowledged"
    VALIDATION_NOTICE_SENT = "validation_notice_sent"
    CEASE_DESIST_RECEIVED  = "cease_desist_received"
    CEASE_DESIST_HONORED   = "cease_desist_honored"
    COMPLAINT_RECEIVED     = "complaint_received"
    REGULATORY_INQUIRY     = "regulatory_inquiry"


# ─────────────────────────────────────────────────────────────────────────────
# Mixin
# ─────────────────────────────────────────────────────────────────────────────

class TimestampMixin:
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


# ─────────────────────────────────────────────────────────────────────────────
# Customer 360
# ─────────────────────────────────────────────────────────────────────────────

class Customer(Base, TimestampMixin):
    """
    Core identity record. One customer may hold multiple accounts.
    PII fields (SSN, DOB) should be encrypted at rest in production.
    """
    __tablename__ = "customers"

    id                 = Column(String(36), primary_key=True, default=_uuid)
    external_id        = Column(String(64), unique=True, index=True,
                                comment="ID from originating CRM or core banking system")
    first_name         = Column(String(100), nullable=False)
    last_name          = Column(String(100), nullable=False)
    middle_name        = Column(String(100))
    date_of_birth      = Column(Date, comment="Encrypt at rest")
    ssn_hash           = Column(String(128), comment="Bcrypt hash — used for identity verification only")
    preferred_language = Column(String(10), default="en")
    timezone           = Column(String(50), default="America/New_York")
    deceased           = Column(Boolean, default=False)
    deceased_date      = Column(Date)

    accounts            = relationship("Account",           back_populates="customer")
    addresses           = relationship("Address",           back_populates="customer", order_by="Address.is_current.desc()")
    employment_records  = relationship("EmploymentRecord",  back_populates="customer", order_by="EmploymentRecord.reported_date.desc()")
    contact_preferences = relationship("ContactPreference", back_populates="customer")

    def __repr__(self) -> str:
        return f"<Customer {self.first_name} {self.last_name} id={self.id[:8]}>"


class Address(Base, TimestampMixin):
    """Current and historical addresses. is_current=True is the active address."""
    __tablename__ = "addresses"

    id                  = Column(String(36), primary_key=True, default=_uuid)
    customer_id         = Column(String(36), ForeignKey("customers.id"), nullable=False, index=True)
    address_type        = Column(String(20), default="home")       # home | work | mailing
    street_1            = Column(String(200))
    street_2            = Column(String(200))
    city                = Column(String(100))
    state               = Column(String(50))
    zip_code            = Column(String(20))
    country             = Column(String(50), default="US")
    is_current          = Column(Boolean, default=True)
    valid_from          = Column(Date)
    valid_to            = Column(Date)
    verification_status = Column(String(20), default="unverified") # verified | unverified | returned

    customer = relationship("Customer", back_populates="addresses")


class EmploymentRecord(Base, TimestampMixin):
    """
    Employment and income history. Multiple records per customer.
    Used by risk models to detect income shocks and hardship probability.
    """
    __tablename__ = "employment_records"

    id                = Column(String(36), primary_key=True, default=_uuid)
    customer_id       = Column(String(36), ForeignKey("customers.id"), nullable=False, index=True)
    employment_status = Column(SAEnum(EmploymentStatus), nullable=False)
    employer_name     = Column(String(200))
    job_title         = Column(String(200))
    annual_income     = Column(Numeric(12, 2), comment="Gross annual income in USD")
    income_frequency  = Column(String(20))                         # weekly | biweekly | monthly | annual
    start_date        = Column(Date)
    end_date          = Column(Date, comment="Null if current employer")
    reported_date     = Column(Date, nullable=False)
    source            = Column(String(30), default="customer_stated") # customer_stated | bureau | verified

    customer = relationship("Customer", back_populates="employment_records")


class ContactPreference(Base, TimestampMixin):
    """
    One row per channel per customer. Tracks TCPA consent and opt-outs.
    AI agent must check opted_out before any outbound contact.
    """
    __tablename__ = "contact_preferences"

    id                      = Column(String(36), primary_key=True, default=_uuid)
    customer_id             = Column(String(36), ForeignKey("customers.id"), nullable=False, index=True)
    channel                 = Column(String(30), nullable=False)   # email | sms | voice_mobile | voice_home | chat
    contact_value           = Column(String(200), nullable=False)  # the actual email or phone number
    is_primary              = Column(Boolean, default=False)
    is_verified             = Column(Boolean, default=False)
    verification_date       = Column(Date)
    tcpa_consent            = Column(Boolean, default=False,
                                     comment="Express written consent for autodialer/pre-recorded calls")
    tcpa_consent_date       = Column(DateTime)
    tcpa_consent_ip         = Column(String(45))
    opted_out               = Column(Boolean, default=False)
    opt_out_date            = Column(DateTime)
    opt_out_reason          = Column(String(200))
    preferred_hours_start   = Column(Integer, comment="Preferred contact window start — hour 0-23 local time")
    preferred_hours_end     = Column(Integer, comment="Preferred contact window end — hour 0-23 local time")
    preferred_days          = Column(JSON, comment="Ordered list of preferred contact days e.g. ['Mon','Tue']")
    bounce_count            = Column(Integer, default=0, comment="Email hard/soft bounce counter")
    last_successful_contact = Column(DateTime)

    customer = relationship("Customer", back_populates="contact_preferences")

    __table_args__ = (
        Index("idx_contact_customer_channel", "customer_id", "channel"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Account & Financial
# ─────────────────────────────────────────────────────────────────────────────

class Account(Base, TimestampMixin):
    """
    Credit card account. Central entity that most other tables hang off.
    delinquency_bucket and days_past_due are the primary collection triggers.
    """
    __tablename__ = "accounts"

    id                     = Column(String(36), primary_key=True, default=_uuid)
    account_number         = Column(String(64), unique=True, nullable=False, index=True)
    customer_id            = Column(String(36), ForeignKey("customers.id"), nullable=False, index=True)
    product_type           = Column(String(50), default="credit_card")
    credit_limit           = Column(Numeric(12, 2), nullable=False)
    current_balance        = Column(Numeric(12, 2), nullable=False, default=0)
    available_credit       = Column(Numeric(12, 2), default=0)
    purchase_balance       = Column(Numeric(12, 2), default=0)
    cash_advance_balance   = Column(Numeric(12, 2), default=0)
    fees_balance           = Column(Numeric(12, 2), default=0,
                                    comment="Accrued late fees and penalty charges")
    apr_purchase           = Column(Numeric(6, 4), comment="Annual percentage rate — purchases")
    apr_cash_advance       = Column(Numeric(6, 4))
    apr_penalty            = Column(Numeric(6, 4), comment="Penalty APR triggered by severe delinquency")
    minimum_payment_due    = Column(Numeric(12, 2), default=0)
    payment_due_date       = Column(Date)
    statement_date         = Column(Date)
    days_past_due          = Column(Integer, default=0, index=True)
    delinquency_bucket     = Column(SAEnum(DelinquencyBucket),
                                    default=DelinquencyBucket.CURRENT, index=True)
    status                 = Column(SAEnum(AccountStatus),
                                    default=AccountStatus.ACTIVE, index=True)
    opened_date            = Column(Date)
    closed_date            = Column(Date)
    last_payment_date      = Column(Date)
    last_payment_amount    = Column(Numeric(12, 2))
    last_statement_balance = Column(Numeric(12, 2))
    payment_plan_active    = Column(Boolean, default=False)
    hardship_enrolled      = Column(Boolean, default=False)
    do_not_contact         = Column(Boolean, default=False,
                                    comment="Set True on cease-and-desist; blocks all outbound contact")
    dispute_active         = Column(Boolean, default=False)
    assigned_agent_id      = Column(String(64), comment="Human agent or queue currently owning account")
    next_review_date       = Column(Date)
    account_flags          = Column(JSON, default=dict,
                                    comment="Operational flags: {'settlement_eligible': True, 'legal_hold': False}")

    customer             = relationship("Customer",           back_populates="accounts")
    payment_history      = relationship("PaymentHistory",     back_populates="account",
                                        order_by="PaymentHistory.payment_date.desc()")
    risk_profiles        = relationship("RiskProfile",        back_populates="account",
                                        order_by="RiskProfile.snapshot_date.desc()")
    behavioral_signals   = relationship("BehavioralSignal",   back_populates="account",
                                        order_by="BehavioralSignal.signal_date.desc()")
    interactions         = relationship("Interaction",         back_populates="account",
                                        order_by="Interaction.interaction_datetime.desc()")
    payment_arrangements = relationship("PaymentArrangement", back_populates="account")
    hardship_enrollments = relationship("HardshipEnrollment", back_populates="account")
    compliance_events    = relationship("ComplianceEvent",    back_populates="account",
                                        order_by="ComplianceEvent.event_datetime.desc()")

    @property
    def latest_risk(self) -> "RiskProfile | None":
        return self.risk_profiles[0] if self.risk_profiles else None

    @property
    def active_arrangement(self) -> "PaymentArrangement | None":
        return next(
            (a for a in self.payment_arrangements if a.status == ArrangementStatus.ACTIVE),
            None,
        )

    def __repr__(self) -> str:
        return f"<Account {self.account_number} DPD={self.days_past_due} balance=${self.current_balance}>"


class PaymentHistory(Base):
    """
    Every payment transaction, including returns and failures.
    days_late drives delinquency bucket calculations.
    """
    __tablename__ = "payment_history"

    id                  = Column(String(36), primary_key=True, default=_uuid)
    account_id          = Column(String(36), ForeignKey("accounts.id"), nullable=False, index=True)
    payment_date        = Column(Date, nullable=False)
    due_date            = Column(Date, comment="Which billing cycle this payment satisfies")
    amount_due          = Column(Numeric(12, 2))
    amount_paid         = Column(Numeric(12, 2), nullable=False)
    payment_method      = Column(String(30))    # ach | debit_card | check | wire | cash
    payment_source      = Column(String(30))    # online | ivr | agent | auto_pay | branch | mail
    status              = Column(String(30), nullable=False, default="settled")
    # settled | pending | returned_nsf | returned_stop | cancelled
    confirmation_number = Column(String(100))
    days_late           = Column(Integer, default=0,
                                 comment="0 = on time; positive integer = days late")
    created_at          = Column(DateTime, default=datetime.utcnow)

    account = relationship("Account", back_populates="payment_history")

    __table_args__ = (
        Index("idx_payment_account_date", "account_id", "payment_date"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Risk & Delinquency Signals
# ─────────────────────────────────────────────────────────────────────────────

class RiskProfile(Base):
    """
    Point-in-time snapshot from ML risk models. New row per scoring run.
    Drives which customers the AI agent contacts, when, and with what offer.

    Key signals fed into each score:
    - delinquency_risk_score  : payment history trend, utilization, balance trajectory
    - payment_propensity_score: historical payment behavior, income signals, engagement
    - hardship_probability    : spending pattern change, income drop, bureau flags
    - promise_reliability_rate: ratio of kept vs broken promises-to-pay historically
    """
    __tablename__ = "risk_profiles"

    id                       = Column(String(36), primary_key=True, default=_uuid)
    account_id               = Column(String(36), ForeignKey("accounts.id"),
                                      nullable=False, index=True)
    snapshot_date            = Column(Date, nullable=False)

    # Core scores
    delinquency_risk_score   = Column(Integer,
                                      comment="0–1000; higher = greater charge-off risk")
    payment_propensity_score = Column(Integer,
                                      comment="0–100; higher = more likely to pay this cycle")
    hardship_probability     = Column(Float,
                                      comment="0–1 likelihood customer is in financial hardship")
    churn_risk_score         = Column(Float,
                                      comment="0–1 probability of account closure post-resolution")
    promise_reliability_rate = Column(Float,
                                      comment="Historical PTP-kept rate 0–1")
    ltv_score                = Column(Float, comment="Estimated lifetime value score")

    # Contact optimization
    best_contact_channel     = Column(String(30),
                                      comment="Predicted highest-response channel for this cycle")
    best_contact_time_start  = Column(Integer, comment="Optimal contact window start — hour 0-23 local")
    best_contact_time_end    = Column(Integer, comment="Optimal contact window end — hour 0-23 local")
    best_contact_days        = Column(JSON,    comment="Ranked list of best contact days")

    # Recommended actions
    recommended_action       = Column(String(50),
                                      comment="SELF_CURE|EARLY_INTERVENTION|HARDSHIP_OUTREACH|PAYMENT_PLAN|SETTLEMENT|LEGAL")
    recommended_offer        = Column(String(100), comment="Specific offer to lead with in next interaction")

    # Model metadata
    model_version            = Column(String(30))
    features                 = Column(JSON,
                                      comment="Raw feature vector used for this prediction — for explainability")
    created_at               = Column(DateTime, default=datetime.utcnow)

    account = relationship("Account", back_populates="risk_profiles")

    __table_args__ = (
        Index("idx_risk_account_date", "account_id", "snapshot_date"),
    )


class BehavioralSignal(Base):
    """
    Individual delinquency or behavioral events detected by the platform.

    Examples by signal_value schema:
      SPENDING_DECLINE     : {"pct_change": -0.42, "period_days": 30, "category": "groceries"}
      RETURNED_PAYMENT     : {"amount": 250.00, "reason": "nsf", "bank": "Chase"}
      MINIMUM_PAYMENT_ONLY : {"consecutive_months": 4, "avg_payment_pct": 0.021}
      BUREAU_DEROGATORY    : {"tradeline_type": "mortgage", "new_derog_count": 2}

    processed=False signals are queued for AI agent action.
    """
    __tablename__ = "behavioral_signals"

    id           = Column(String(36), primary_key=True, default=_uuid)
    account_id   = Column(String(36), ForeignKey("accounts.id"), nullable=False, index=True)
    signal_date  = Column(Date, nullable=False)
    signal_type  = Column(SAEnum(SignalType), nullable=False, index=True)
    signal_value = Column(JSON, comment="Structured payload — schema varies by signal_type")
    severity     = Column(SAEnum(SignalSeverity), default=SignalSeverity.MEDIUM)
    source       = Column(String(30), default="transaction") # transaction|behavior|bureau|external
    processed    = Column(Boolean, default=False,
                          comment="True once AI agent has taken action on this signal")
    processed_at = Column(DateTime)
    created_at   = Column(DateTime, default=datetime.utcnow)

    account = relationship("Account", back_populates="behavioral_signals")

    __table_args__ = (
        Index("idx_signal_account_type_date", "account_id", "signal_type", "signal_date"),
        Index("idx_signal_unprocessed",       "processed", "severity"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Contact History (Omni-channel)
# ─────────────────────────────────────────────────────────────────────────────

class Interaction(Base):
    """
    Every customer touchpoint across all channels — inbound or outbound,
    AI-handled or human-handled. The primary audit trail for collections activity.

    promise_kept is backfilled by a nightly job after the promise_to_pay_date passes.
    sentiment_score is populated by NLP post-processing of transcripts.
    """
    __tablename__ = "interactions"

    id                     = Column(String(36), primary_key=True, default=_uuid)
    account_id             = Column(String(36), ForeignKey("accounts.id"),
                                    nullable=False, index=True)
    customer_id            = Column(String(36), ForeignKey("customers.id"),
                                    nullable=False, index=True)
    interaction_datetime   = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    channel                = Column(SAEnum(Channel), nullable=False)
    direction              = Column(String(10), nullable=False)   # inbound | outbound
    initiated_by           = Column(String(20), default="ai_agent")
    # ai_agent | human_agent | customer | system
    agent_id               = Column(String(64),
                                    comment="Human agent ID; null if fully AI-handled")
    is_ai_handled          = Column(Boolean, default=True)
    ai_agent_version       = Column(String(30))
    duration_seconds       = Column(Integer)
    contact_status         = Column(SAEnum(ContactStatus))
    outcome                = Column(SAEnum(InteractionOutcome))
    payment_collected      = Column(Numeric(12, 2))
    promise_to_pay_amount  = Column(Numeric(12, 2))
    promise_to_pay_date    = Column(Date)
    promise_kept           = Column(Boolean,
                                    comment="Backfilled True/False after PTP date passes")
    sentiment_score        = Column(Float,
                                    comment="-1.0 (hostile) to +1.0 (cooperative) from NLP analysis")
    notes                  = Column(Text)
    transcript_url         = Column(String(500))
    recording_url          = Column(String(500))
    fdcpa_disclosure_given = Column(Boolean, default=False)
    tcpa_verified          = Column(Boolean, default=False)
    created_at             = Column(DateTime, default=datetime.utcnow)

    account             = relationship("Account",            back_populates="interactions")
    compliance_events   = relationship("ComplianceEvent",    back_populates="interaction")
    payment_arrangement = relationship("PaymentArrangement", back_populates="interaction",
                                       uselist=False)
    hardship_enrollment = relationship("HardshipEnrollment", back_populates="interaction",
                                       uselist=False)

    __table_args__ = (
        Index("idx_interaction_account_dt",  "account_id", "interaction_datetime"),
        Index("idx_interaction_outcome",     "outcome"),
        Index("idx_interaction_ptp",         "promise_to_pay_date", "promise_kept"),
    )


class PaymentArrangement(Base, TimestampMixin):
    """
    Formal payment agreements reached with customers.
    broken_date + broken_reason feed the promise_reliability_rate ML feature.
    """
    __tablename__ = "payment_arrangements"

    id                     = Column(String(36), primary_key=True, default=_uuid)
    account_id             = Column(String(36), ForeignKey("accounts.id"),
                                    nullable=False, index=True)
    interaction_id         = Column(String(36), ForeignKey("interactions.id"), index=True)
    arrangement_type       = Column(SAEnum(ArrangementType), nullable=False)
    total_amount           = Column(Numeric(12, 2), nullable=False)
    monthly_amount         = Column(Numeric(12, 2))
    number_of_installments = Column(Integer)
    installments_paid      = Column(Integer, default=0)
    start_date             = Column(Date, nullable=False)
    end_date               = Column(Date)
    next_payment_date      = Column(Date)
    status                 = Column(SAEnum(ArrangementStatus),
                                    default=ArrangementStatus.ACTIVE, index=True)
    broken_date            = Column(Date)
    broken_reason          = Column(String(200))
    created_by             = Column(String(64), comment="Agent ID or 'AI_AGENT'")

    account     = relationship("Account",     back_populates="payment_arrangements")
    interaction = relationship("Interaction", back_populates="payment_arrangement")


class HardshipEnrollment(Base, TimestampMixin):
    """
    Customer enrollment in financial assistance programs.
    Reduces or pauses payments while preserving the customer relationship.
    """
    __tablename__ = "hardship_enrollments"

    id                   = Column(String(36), primary_key=True, default=_uuid)
    account_id           = Column(String(36), ForeignKey("accounts.id"),
                                  nullable=False, index=True)
    interaction_id       = Column(String(36), ForeignKey("interactions.id"), index=True)
    hardship_type        = Column(SAEnum(HardshipType), nullable=False)
    hardship_description = Column(Text, comment="Customer's own words — preserve verbatim")
    program_type         = Column(SAEnum(HardshipProgram), nullable=False)
    original_apr         = Column(Numeric(6, 4))
    reduced_apr          = Column(Numeric(6, 4))
    fees_waived_total    = Column(Numeric(12, 2))
    deferral_months      = Column(Integer)
    deferral_end_date    = Column(Date)
    program_start_date   = Column(Date, nullable=False)
    program_end_date     = Column(Date)
    status               = Column(SAEnum(HardshipStatus), default=HardshipStatus.ACTIVE, index=True)
    enrolled_by          = Column(String(64))

    account     = relationship("Account",     back_populates="hardship_enrollments")
    interaction = relationship("Interaction", back_populates="hardship_enrollment")


# ─────────────────────────────────────────────────────────────────────────────
# Compliance (Immutable Audit Trail)
# ─────────────────────────────────────────────────────────────────────────────

class ComplianceEvent(Base):
    """
    Immutable log of all compliance-relevant events.
    NEVER delete or update rows — append only.
    Required for FDCPA, TCPA, and CFPB regulatory audits.
    """
    __tablename__ = "compliance_events"

    id             = Column(String(36), primary_key=True, default=_uuid)
    account_id     = Column(String(36), ForeignKey("accounts.id"), nullable=False, index=True)
    interaction_id = Column(String(36), ForeignKey("interactions.id"), index=True)
    event_type     = Column(SAEnum(ComplianceEventType), nullable=False, index=True)
    event_datetime = Column(DateTime, nullable=False, default=datetime.utcnow)
    recorded_by    = Column(String(64), comment="Agent ID, 'AI_AGENT', or 'SYSTEM'")
    channel        = Column(String(30))
    description    = Column(Text)
    document_url   = Column(String(500), comment="Link to consent recording or written evidence")
    verified       = Column(Boolean, default=False)
    created_at     = Column(DateTime, default=datetime.utcnow)

    account     = relationship("Account",     back_populates="compliance_events")
    interaction = relationship("Interaction", back_populates="compliance_events")

    __table_args__ = (
        Index("idx_compliance_account_type", "account_id", "event_type"),
        Index("idx_compliance_datetime",     "event_datetime"),
    )
