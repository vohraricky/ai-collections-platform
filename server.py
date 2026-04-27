import json
import os
from datetime import date, datetime
from decimal import Decimal

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from anthropic import AsyncAnthropic

from database import SessionLocal, init_db
from seed import seed_demo_data
from outreach import select_candidates, record_dispatch
from channels import get_config, CHANNELS
from models import (
    Account, Customer, ContactPreference, PaymentHistory, RiskProfile,
    Interaction, PaymentArrangement, HardshipEnrollment, ComplianceEvent,
    Channel, ContactStatus, InteractionOutcome,
    ArrangementType, ArrangementStatus,
    HardshipType, HardshipProgram,
    ComplianceEventType,
)

# ── Startup ────────────────────────────────────────────────────────────────────
init_db()
seed_demo_data()

app = FastAPI(title="Collections AI Agent")
client = AsyncAnthropic()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Prompts & Tools ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are Alex, a compassionate Financial Wellness Advisor at Premier Bank's Customer Success team. You are NOT a collections agent — you are a relationship manager who calls when a customer may need support managing their account.

## YOUR MISSION
Transform every interaction into a relationship-building moment. Your success is measured equally by customer satisfaction AND resolution — never just payments.

## PERSONALITY & TONE
- Warm, genuine, and unhurried — never scripted or robotic
- Curious about what's happening in the customer's life before discussing solutions
- Optimistic: always frame options as opportunities, never ultimatums
- Human: acknowledge difficulty without judgment, use plain language

## CONVERSATION FLOW
1. Warm greeting — introduce yourself and the company genuinely
2. FDCPA disclosure — state this is an attempt to collect a debt (required)
3. Check in — ask how they're doing (genuine curiosity)
4. Listen first — understand their situation before mentioning money
5. Acknowledge — validate their experience before any solution talk
6. Explore together — present 2-3 tailored options as a conversation
7. Agree on next steps — clear, actionable, confirmed by the customer
8. Close warmly — thank them, offer ongoing support

## SOLUTIONS YOU CAN OFFER

**Payment Plans** (use create_payment_plan tool):
- 3-month plan: spreads balance into 3 equal installments
- 6-month plan: lower monthly commitment
- 12-month plan: maximum flexibility for larger balances

**Hardship Programs** (use enroll_hardship_program tool):
- reduced_interest: 0% interest rate for 12 months
- fee_waiver: immediate waiver of all late/penalty fees
- payment_deferral: 90-day pause with no penalties
- full_hardship: all of the above — for severe situations

**Other Options**:
- Free financial counseling referral (NFCC-certified)
- Goodwill late-fee waiver for long-standing customers
- Minimum payment reduction (60+ day cases)

## COMPLIANCE — FDCPA REQUIRED
- Always state your name and "Premier Bank" at the start
- Include: "This is an attempt to collect a debt"
- Never threaten legal action, garnishment, or asset seizure
- Honor dispute requests immediately — provide written notice offer
- No contact before 8am or after 9pm customer's local time
- Never use abusive, threatening, or misleading language
- Never misrepresent the balance or consequences

## LANGUAGE GUIDE
Use empathetic framing:
- "balance we can address together" — not "debt you owe"
- "gap in recent payments" — not "you're delinquent"
- "let's find what works for you" — not "you must pay"
- "help protect your credit standing" — not "or else"
- "would you be open to..." — not "you need to"

## TOOL USAGE
Always use lookup_account before discussing any specific figures. If a customer doesn't know their account number, look them up by name. After arranging a solution, always use the appropriate tool to document it.

Start every session: greet the customer warmly, state your name and company, give the FDCPA disclosure briefly, then ask for their account number or name so you can pull up their information.

Demo accounts available: ACC001 (Sarah Johnson), ACC002 (Marcus Thompson), ACC003 (Elena Rodriguez)."""

TOOLS = [
    {
        "name": "lookup_account",
        "description": "Look up a customer's account details by account number or full name. Always call this before discussing any balance or payment information.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account_number": {
                    "type": "string",
                    "description": "Account number (e.g. ACC001, ACC002)",
                },
                "name": {
                    "type": "string",
                    "description": "Customer's full or partial name",
                },
            },
        },
    },
    {
        "name": "create_payment_plan",
        "description": "Create a structured payment plan for the customer. Use after the customer agrees to a specific plan.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account_number": {"type": "string"},
                "monthly_amount": {
                    "type": "number",
                    "description": "Amount to charge per month in USD",
                },
                "duration_months": {
                    "type": "integer",
                    "description": "Number of months for the plan (3, 6, or 12)",
                },
                "start_date": {
                    "type": "string",
                    "description": "When to start (e.g. 'next billing cycle', 'January 1')",
                },
            },
            "required": ["account_number", "monthly_amount", "duration_months"],
        },
    },
    {
        "name": "enroll_hardship_program",
        "description": "Enroll a customer in a hardship assistance program. Use when customer has demonstrated genuine financial difficulty.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account_number": {"type": "string"},
                "hardship_reason": {
                    "type": "string",
                    "description": "Brief description of the customer's hardship (job loss, medical, etc.)",
                },
                "program_type": {
                    "type": "string",
                    "enum": ["reduced_interest", "fee_waiver", "payment_deferral", "full_hardship"],
                    "description": "Type of hardship program to enroll in",
                },
            },
            "required": ["account_number", "hardship_reason", "program_type"],
        },
    },
]


# ── DB-backed tool functions ───────────────────────────────────────────────────

def _risk_tier(score: int | None) -> str:
    if score is None:
        return "Unknown"
    if score < 400:
        return "Low"
    if score < 700:
        return "Medium"
    return "High"


def _infer_hardship_type(reason: str) -> HardshipType:
    r = reason.lower()
    if any(k in r for k in ("job", "unemploy", "laid off", "layoff")):
        return HardshipType.JOB_LOSS
    if any(k in r for k in ("medical", "health", "hospital", "illness")):
        return HardshipType.MEDICAL_EMERGENCY
    if any(k in r for k in ("divorce", "separation", "separat")):
        return HardshipType.DIVORCE_SEPARATION
    if any(k in r for k in ("death", "passed", "bereavement")):
        return HardshipType.DEATH_IN_FAMILY
    if any(k in r for k in ("disaster", "flood", "hurricane", "fire")):
        return HardshipType.NATURAL_DISASTER
    if any(k in r for k in ("military", "deployment", "deploy")):
        return HardshipType.MILITARY_DEPLOYMENT
    if any(k in r for k in ("income", "pay cut", "reduced")):
        return HardshipType.INCOME_REDUCTION
    return HardshipType.OTHER


def db_lookup_account(account_number=None, name=None) -> dict:
    db = SessionLocal()
    try:
        acc = None
        if account_number:
            acc = (
                db.query(Account)
                .filter(Account.account_number == account_number.upper().strip())
                .first()
            )
        if not acc and name:
            name_lower = name.strip().lower()
            for candidate in db.query(Account).join(Customer).all():
                full = f"{candidate.customer.first_name} {candidate.customer.last_name}".lower()
                if name_lower in full:
                    acc = candidate
                    break

        if not acc:
            return {
                "found": False,
                "message": "Customer not found.",
                "demo_accounts": [
                    "ACC001 — Sarah Johnson (37 days past due, $2,847 balance)",
                    "ACC002 — Marcus Thompson (68 days past due, $7,234 balance)",
                    "ACC003 — Elena Rodriguez (22 days past due, $4,512 balance)",
                ],
            }

        if acc.do_not_contact:
            return {
                "found": True,
                "account_number": acc.account_number,
                "do_not_contact": True,
                "message": "Cease-and-desist on file. Do not proceed with outbound contact.",
            }

        cust = acc.customer
        prefs = cust.contact_preferences
        email = next((p.contact_value for p in prefs if p.channel == "email"), None)
        phone = next((p.contact_value for p in prefs if p.channel == "voice_mobile"), None)

        last_pmt = acc.payment_history[0] if acc.payment_history else None
        risk = acc.latest_risk

        result = {
            "found": True,
            "account_number": acc.account_number,
            "name": f"{cust.first_name} {cust.last_name}",
            "email": email,
            "phone": phone,
            "balance": float(acc.current_balance),
            "minimum_due": float(acc.minimum_payment_due),
            "days_past_due": acc.days_past_due,
            "credit_limit": float(acc.credit_limit),
            "interest_rate": round(float(acc.apr_purchase) * 100, 2) if acc.apr_purchase else None,
            "account_opened": acc.opened_date.strftime("%b %Y") if acc.opened_date else None,
            "hardship_enrolled": acc.hardship_enrolled,
            "payment_plan_active": acc.payment_plan_active,
            "dispute_active": acc.dispute_active,
        }

        if last_pmt:
            result["last_payment"] = {
                "date": last_pmt.payment_date.strftime("%b %d, %Y"),
                "amount": float(last_pmt.amount_paid),
            }

        if risk:
            result["risk_tier"] = _risk_tier(risk.delinquency_risk_score)
            result["suggested_action"] = risk.recommended_offer
            result["hardship_probability"] = risk.hardship_probability
            result["payment_propensity_score"] = risk.payment_propensity_score

        return result
    finally:
        db.close()


def db_create_payment_plan(
    account_number: str,
    monthly_amount: float,
    duration_months: int,
    start_date: str = "next billing cycle",
) -> dict:
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
        today = date.today()

        interaction = Interaction(
            account_id=acc.id,
            customer_id=cust.id,
            channel=Channel.INBOUND_CHAT,
            direction="inbound",
            initiated_by="customer",
            is_ai_handled=True,
            contact_status=ContactStatus.CONNECTED,
            outcome=InteractionOutcome.ARRANGEMENT_SET,
            fdcpa_disclosure_given=True,
        )
        db.add(interaction)
        db.flush()

        total = round(monthly_amount * duration_months, 2)
        arrangement = PaymentArrangement(
            account_id=acc.id,
            interaction_id=interaction.id,
            arrangement_type=ArrangementType.PAYMENT_PLAN,
            total_amount=Decimal(str(total)),
            monthly_amount=Decimal(str(monthly_amount)),
            number_of_installments=duration_months,
            start_date=today,
            status=ArrangementStatus.ACTIVE,
            created_by="AI_AGENT",
        )
        db.add(arrangement)

        acc.payment_plan_active = True
        db.commit()

        email = next(
            (p.contact_value for p in cust.contact_preferences if p.channel == "email"), "email on file"
        )
        return {
            "success": True,
            "plan_id": arrangement.id[:8].upper(),
            "customer": f"{cust.first_name} {cust.last_name}",
            "monthly_payment": f"${monthly_amount:,.2f}",
            "duration": f"{duration_months} months",
            "start_date": start_date,
            "total_to_pay": f"${total:,.2f}",
            "current_balance": f"${float(acc.current_balance):,.2f}",
            "confirmation": f"Payment plan confirmed. Details sent to {email}.",
        }
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


_HARDSHIP_PROGRAMS = {
    "reduced_interest": {
        "label": "Reduced Interest",
        "detail": "Interest rate reduced to 0% for 12 months",
    },
    "fee_waiver": {
        "label": "Fee Waiver",
        "detail": "All late fees and penalty charges waived immediately",
    },
    "payment_deferral": {
        "label": "Payment Deferral",
        "detail": "90-day payment deferral — no penalties during deferral period",
    },
    "full_hardship": {
        "label": "Full Hardship Package",
        "detail": "0% interest + all fees waived + 60-day deferral",
    },
}

_PROGRAM_ENUM = {
    "reduced_interest": HardshipProgram.REDUCED_INTEREST,
    "fee_waiver": HardshipProgram.FEE_WAIVER,
    "payment_deferral": HardshipProgram.PAYMENT_DEFERRAL,
    "full_hardship": HardshipProgram.FULL_HARDSHIP,
}


def db_enroll_hardship(account_number: str, hardship_reason: str, program_type: str) -> dict:
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
        today = date.today()
        prog_info = _HARDSHIP_PROGRAMS.get(program_type, {"label": program_type, "detail": "Custom program"})

        interaction = Interaction(
            account_id=acc.id,
            customer_id=cust.id,
            channel=Channel.INBOUND_CHAT,
            direction="inbound",
            initiated_by="customer",
            is_ai_handled=True,
            contact_status=ContactStatus.CONNECTED,
            outcome=InteractionOutcome.HARDSHIP_IDENTIFIED,
            fdcpa_disclosure_given=True,
        )
        db.add(interaction)
        db.flush()

        enrollment = HardshipEnrollment(
            account_id=acc.id,
            interaction_id=interaction.id,
            hardship_type=_infer_hardship_type(hardship_reason),
            hardship_description=hardship_reason,
            program_type=_PROGRAM_ENUM.get(program_type, HardshipProgram.CUSTOM),
            program_start_date=today,
            enrolled_by="AI_AGENT",
        )
        db.add(enrollment)

        acc.hardship_enrolled = True
        db.commit()

        email = next(
            (p.contact_value for p in cust.contact_preferences if p.channel == "email"), "email on file"
        )
        return {
            "success": True,
            "enrollment_id": enrollment.id[:8].upper(),
            "customer": f"{cust.first_name} {cust.last_name}",
            "program": prog_info["label"],
            "details": prog_info["detail"],
            "reason_on_file": hardship_reason,
            "next_steps": [
                "Account updated immediately",
                f"Welcome letter sent to {email}",
                "30-day follow-up call scheduled",
            ],
            "confirmation": f"Enrollment confirmed. Details sent to {email}.",
        }
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


# ── Conversation persistence ───────────────────────────────────────────────────

def _account_ids_from_messages(messages: list) -> tuple[str | None, str | None]:
    """Scan accumulated messages for the first successful lookup_account result."""
    for msg in messages:
        if msg.get("role") != "user":
            continue
        content = msg.get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if block.get("type") != "tool_result":
                continue
            try:
                data = json.loads(block.get("content", "{}"))
                if data.get("found") and data.get("account_number"):
                    db = SessionLocal()
                    try:
                        acc = (
                            db.query(Account)
                            .filter(Account.account_number == data["account_number"])
                            .first()
                        )
                        if acc:
                            return acc.id, acc.customer_id
                    finally:
                        db.close()
            except Exception:
                pass
    return None, None


def _infer_outcome(messages: list) -> InteractionOutcome:
    for msg in messages:
        content = msg.get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if block.get("type") != "tool_result":
                continue
            try:
                data = json.loads(block.get("content", "{}"))
                if data.get("success"):
                    if "plan_id" in data:
                        return InteractionOutcome.ARRANGEMENT_SET
                    if "enrollment_id" in data:
                        return InteractionOutcome.HARDSHIP_IDENTIFIED
            except Exception:
                pass
    return InteractionOutcome.NO_RESOLUTION


def _save_conversation(
    account_id: str,
    customer_id: str,
    messages: list,
    started_at: datetime,
) -> None:
    db = SessionLocal()
    try:
        duration = int((datetime.utcnow() - started_at).total_seconds())
        outcome = _infer_outcome(messages)

        interaction = Interaction(
            account_id=account_id,
            customer_id=customer_id,
            channel=Channel.INBOUND_CHAT,
            direction="inbound",
            initiated_by="customer",
            is_ai_handled=True,
            ai_agent_version="alex-v1",
            contact_status=ContactStatus.CONNECTED,
            outcome=outcome,
            duration_seconds=duration,
            fdcpa_disclosure_given=True,
            notes=json.dumps(messages, default=str),
        )
        db.add(interaction)
        db.flush()

        db.add(ComplianceEvent(
            account_id=account_id,
            interaction_id=interaction.id,
            event_type=ComplianceEventType.FDCPA_DISCLOSURE,
            recorded_by="AI_AGENT",
            channel="chat",
            description="Mini-Miranda given at session start by Alex",
            verified=True,
        ))

        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


# ── Tool dispatch ──────────────────────────────────────────────────────────────

def execute_tool(name: str, inputs: dict) -> dict:
    if name == "lookup_account":
        return db_lookup_account(
            account_number=inputs.get("account_number"),
            name=inputs.get("name"),
        )
    if name == "create_payment_plan":
        return db_create_payment_plan(
            inputs["account_number"],
            inputs["monthly_amount"],
            inputs["duration_months"],
            inputs.get("start_date", "next billing cycle"),
        )
    if name == "enroll_hardship_program":
        return db_enroll_hardship(
            inputs["account_number"],
            inputs["hardship_reason"],
            inputs["program_type"],
        )
    return {"error": f"Unknown tool: {name}"}


# ── API ────────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    messages: list
    channel: str = "chat"


class OutreachGenerateRequest(BaseModel):
    account_number: str
    name: str
    days_past_due: int
    balance: float
    risk_tier: str
    hardship_probability: float | None = None
    payment_propensity_score: int | None = None
    suggested_action: str | None = None
    last_payment_date: str | None = None
    channel: str = "email"


class OutreachDispatchRequest(BaseModel):
    account_number: str
    channel: str
    message: str


@app.get("/")
async def serve_ui():
    return FileResponse("static/index.html")


@app.post("/chat")
async def chat(request: ChatRequest):
    messages = [{"role": m["role"], "content": m["content"]} for m in request.messages]
    ch = get_config(request.channel)

    async def generate():
        current_messages = messages
        started_at = datetime.utcnow()
        saved = False

        try:
            while True:
                async with client.messages.stream(
                    model="claude-sonnet-4-6",
                    system=[
                        {
                            "type": "text",
                            "text": SYSTEM_PROMPT,
                            "cache_control": {"type": "ephemeral"},
                        },
                        {
                            "type": "text",
                            "text": ch.prompt_addendum,
                        },
                    ],
                    tools=TOOLS,
                    messages=current_messages,
                    max_tokens=ch.max_tokens,
                    thinking={"type": "disabled"},
                ) as stream:
                    async for event in stream:
                        if event.type == "content_block_delta":
                            if hasattr(event.delta, "text") and event.delta.text:
                                payload = json.dumps({"type": "text", "text": event.delta.text})
                                yield f"data: {payload}\n\n"

                    final = await stream.get_final_message()

                if final.stop_reason == "end_turn":
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    account_id, customer_id = _account_ids_from_messages(current_messages)
                    if account_id:
                        _save_conversation(account_id, customer_id, current_messages, started_at)
                        saved = True
                    break

                elif final.stop_reason == "tool_use":
                    assistant_content = []
                    for block in final.content:
                        if block.type == "text":
                            assistant_content.append({"type": "text", "text": block.text})
                        elif block.type == "tool_use":
                            assistant_content.append({
                                "type": "tool_use",
                                "id": block.id,
                                "name": block.name,
                                "input": block.input,
                            })

                    current_messages = current_messages + [
                        {"role": "assistant", "content": assistant_content}
                    ]

                    tool_results = []
                    for block in final.content:
                        if block.type == "tool_use":
                            yield f"data: {json.dumps({'type': 'tool_start', 'tool': block.name})}\n\n"

                            result = execute_tool(block.name, block.input)

                            yield f"data: {json.dumps({'type': 'tool_result', 'tool': block.name, 'data': result})}\n\n"

                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps(result),
                            })

                    current_messages = current_messages + [
                        {"role": "user", "content": tool_results}
                    ]
                else:
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    break
        finally:
            # Save on client disconnect or error if not already saved
            if not saved:
                account_id, customer_id = _account_ids_from_messages(current_messages)
                if account_id:
                    _save_conversation(account_id, customer_id, current_messages, started_at)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/channels")
async def list_channels():
    return {k: {"name": v.name, "icon": v.icon, "color": v.color} for k, v in CHANNELS.items()}


async def run_agent_sync(messages: list, channel: str = "chat") -> str:
    """Full tool-use loop, non-streaming. Returns final text response."""
    ch = get_config(channel)
    current = messages
    while True:
        resp = await client.messages.create(
            model="claude-sonnet-4-6",
            system=[
                {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": ch.prompt_addendum},
            ],
            tools=TOOLS,
            messages=current,
            max_tokens=ch.max_tokens,
            thinking={"type": "disabled"},
        )
        if resp.stop_reason == "end_turn":
            text = next((b.text for b in resp.content if b.type == "text"), "")
            return ch.format_response(text)
        if resp.stop_reason == "tool_use":
            asst = []
            for b in resp.content:
                if b.type == "text":
                    asst.append({"type": "text", "text": b.text})
                elif b.type == "tool_use":
                    asst.append({"type": "tool_use", "id": b.id, "name": b.name, "input": b.input})
            current = current + [{"role": "assistant", "content": asst}]
            results = []
            for b in resp.content:
                if b.type == "tool_use":
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": b.id,
                        "content": json.dumps(execute_tool(b.name, b.input)),
                    })
            current = current + [{"role": "user", "content": results}]
        else:
            return ""


def _lookup_by_contact(value: str) -> dict:
    """Find an account via a phone number or email address."""
    db = SessionLocal()
    try:
        pref = (
            db.query(ContactPreference)
            .filter(ContactPreference.contact_value == value)
            .first()
        )
        if not pref:
            return {"found": False}
        acc = db.query(Account).filter(Account.customer_id == pref.customer_id).first()
        if not acc:
            return {"found": False}
        return db_lookup_account(account_number=acc.account_number)
    finally:
        db.close()


def _record_inbound_interaction(
    account_data: dict,
    inbound_text: str,
    reply_text: str,
    channel: str,
) -> str | None:
    if not account_data.get("found"):
        return None
    db = SessionLocal()
    try:
        acc = (
            db.query(Account)
            .filter(Account.account_number == account_data["account_number"])
            .first()
        )
        if not acc:
            return None
        from channels import CHANNELS as CH_MAP
        from models import Channel as ChannelEnum
        ch_enum_map = {
            "sms":   ChannelEnum.INBOUND_SMS,
            "email": ChannelEnum.INBOUND_EMAIL,
            "voice": ChannelEnum.INBOUND_CALL,
            "chat":  ChannelEnum.INBOUND_CHAT,
        }
        interaction = Interaction(
            account_id=acc.id,
            customer_id=acc.customer_id,
            channel=ch_enum_map.get(channel, ChannelEnum.INBOUND_CHAT),
            direction="inbound",
            initiated_by="customer",
            is_ai_handled=True,
            ai_agent_version="alex-v1",
            contact_status=ContactStatus.CONNECTED,
            outcome=InteractionOutcome.NO_RESOLUTION,
            fdcpa_disclosure_given=True,
            notes=json.dumps({"inbound": inbound_text, "reply": reply_text}),
        )
        db.add(interaction)
        db.commit()
        return interaction.id[:8].upper()
    except Exception:
        db.rollback()
        return None
    finally:
        db.close()


class InboundSMSRequest(BaseModel):
    from_number: str
    body: str


class InboundEmailRequest(BaseModel):
    from_email: str
    subject: str = ""
    body: str


@app.post("/inbound/sms")
async def inbound_sms(request: InboundSMSRequest):
    acct = _lookup_by_contact(request.from_number)
    ctx = f"[Inbound SMS from {request.from_number}]\n" + (
        f"Account on file: {acct['account_number']} — {acct['name']}\n" if acct.get("found") else ""
    )
    messages = [{"role": "user", "content": ctx + request.body}]
    reply = await run_agent_sync(messages, channel="sms")
    interaction_id = _record_inbound_interaction(acct, request.body, reply, "sms")
    return {
        "reply": reply,
        "channel": "sms",
        "char_count": len(reply),
        "customer_found": acct.get("found", False),
        "account_number": acct.get("account_number"),
        "interaction_id": interaction_id,
    }


@app.post("/inbound/email")
async def inbound_email(request: InboundEmailRequest):
    acct = _lookup_by_contact(request.from_email)
    ctx = f"[Inbound Email from {request.from_email}]\nSubject: {request.subject}\n\n" + (
        f"Account on file: {acct['account_number']} — {acct['name']}\n\n" if acct.get("found") else ""
    )
    messages = [{"role": "user", "content": ctx + request.body}]
    reply = await run_agent_sync(messages, channel="email")
    interaction_id = _record_inbound_interaction(acct, request.body, reply, "email")
    return {
        "reply": reply,
        "channel": "email",
        "customer_found": acct.get("found", False),
        "account_number": acct.get("account_number"),
        "interaction_id": interaction_id,
    }


@app.get("/conversations/{account_number}")
async def get_conversations(account_number: str):
    db = SessionLocal()
    try:
        acc = (
            db.query(Account)
            .filter(Account.account_number == account_number.upper())
            .first()
        )
        if not acc:
            return {"found": False, "interactions": []}
        rows = []
        for i in acc.interactions:
            # Don't send raw full transcript — just a preview
            notes_raw = i.notes or ""
            if notes_raw.startswith("["):
                preview = None          # JSON transcript — skip
            elif notes_raw.startswith("{"):
                try:
                    d = json.loads(notes_raw)
                    preview = d.get("inbound", "")[:80]
                except Exception:
                    preview = notes_raw[:80]
            else:
                preview = notes_raw[:80]

            rows.append({
                "id": i.id[:8].upper(),
                "datetime": i.interaction_datetime.isoformat() if i.interaction_datetime else None,
                "channel": i.channel.value if i.channel else None,
                "direction": i.direction,
                "outcome": i.outcome.value if i.outcome else None,
                "duration_seconds": i.duration_seconds,
                "is_ai": i.is_ai_handled,
                "preview": preview,
            })
        return {"found": True, "account_number": account_number.upper(), "interactions": rows}
    finally:
        db.close()


@app.get("/outreach/candidates")
async def outreach_candidates():
    return select_candidates()


@app.post("/outreach/generate")
async def outreach_generate(request: OutreachGenerateRequest):
    channel_ctx = {
        "email": "Write a professional warm email. Format: SUBJECT: ...\n\nBODY:\n... (max 150 words total)",
        "sms":   "Write a concise SMS under 160 characters. No links. Plain text only.",
        "voice": "Write a 30-second call opening script. Natural spoken language, no stage directions.",
    }

    prompt = f"""Draft a proactive outreach message for Alex, Premier Bank's Financial Wellness Advisor.

Customer: {request.name}
Days Past Due: {request.days_past_due}
Current Balance: ${request.balance:,.2f}
Risk Assessment: {request.risk_tier}
Hardship Probability: {int((request.hardship_probability or 0) * 100)}%
Payment Propensity Score: {request.payment_propensity_score or 'N/A'}/100
Recommended Approach: {request.suggested_action or 'Proactive wellness outreach'}
Last Payment: {request.last_payment_date or 'unknown'}
Channel: {request.channel.upper()}

{channel_ctx.get(request.channel, 'Write a brief outreach message.')}

Requirements:
- Warm, empathetic — wellness advisor reaching out to help, not a collector demanding payment
- Include FDCPA disclosure: "This is an attempt to collect a debt"
- Sign as Alex from Premier Bank Financial Wellness team
- Mention specific options: payment plan, hardship program, financial counseling referral
- Never threaten, never demand — always offer help and present options"""

    async def generate():
        async with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            async for event in stream:
                if event.type == "content_block_delta":
                    if hasattr(event.delta, "text") and event.delta.text:
                        yield f"data: {json.dumps({'type': 'text', 'text': event.delta.text})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/outreach/dispatch")
async def outreach_dispatch(request: OutreachDispatchRequest):
    return record_dispatch(request.account_number, request.channel, request.message)


if __name__ == "__main__":
    import uvicorn
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY environment variable is not set.")
        exit(1)
    uvicorn.run("server:app", host="0.0.0.0", port=8001, reload=True)
