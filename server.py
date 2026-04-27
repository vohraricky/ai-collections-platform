import json
import os
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from anthropic import AsyncAnthropic

from mock_data import lookup_customer, create_payment_plan_record, enroll_hardship_record

app = FastAPI(title="Collections AI Agent")
client = AsyncAnthropic()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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


def execute_tool(name: str, inputs: dict) -> dict:
    if name == "lookup_account":
        return lookup_customer(
            account_number=inputs.get("account_number"),
            name=inputs.get("name"),
        )
    elif name == "create_payment_plan":
        return create_payment_plan_record(
            inputs["account_number"],
            inputs["monthly_amount"],
            inputs["duration_months"],
            inputs.get("start_date", "next billing cycle"),
        )
    elif name == "enroll_hardship_program":
        return enroll_hardship_record(
            inputs["account_number"],
            inputs["hardship_reason"],
            inputs["program_type"],
        )
    return {"error": f"Unknown tool: {name}"}


class ChatRequest(BaseModel):
    messages: list


@app.get("/")
async def serve_ui():
    return FileResponse("static/index.html")


@app.post("/chat")
async def chat(request: ChatRequest):
    messages = [{"role": m["role"], "content": m["content"]} for m in request.messages]

    async def generate():
        current_messages = messages

        while True:
            async with client.messages.stream(
                model="claude-sonnet-4-6",
                system=[
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                tools=TOOLS,
                messages=current_messages,
                max_tokens=1024,
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
                break

            elif final.stop_reason == "tool_use":
                # Build assistant content dict for history
                assistant_content = []
                for block in final.content:
                    if block.type == "text":
                        assistant_content.append({"type": "text", "text": block.text})
                    elif block.type == "tool_use":
                        assistant_content.append(
                            {
                                "type": "tool_use",
                                "id": block.id,
                                "name": block.name,
                                "input": block.input,
                            }
                        )

                current_messages = current_messages + [
                    {"role": "assistant", "content": assistant_content}
                ]

                tool_results = []
                for block in final.content:
                    if block.type == "tool_use":
                        yield f"data: {json.dumps({'type': 'tool_start', 'tool': block.name})}\n\n"

                        result = execute_tool(block.name, block.input)

                        yield f"data: {json.dumps({'type': 'tool_result', 'tool': block.name, 'data': result})}\n\n"

                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps(result),
                            }
                        )

                current_messages = current_messages + [
                    {"role": "user", "content": tool_results}
                ]
            else:
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                break

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    import uvicorn
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY environment variable is not set.")
        exit(1)
    uvicorn.run("server:app", host="0.0.0.0", port=8001, reload=True)
