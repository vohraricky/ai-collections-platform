from datetime import datetime

CUSTOMERS = {
    "ACC001": {
        "name": "Sarah Johnson",
        "email": "sarah.j@email.com",
        "phone": "(555) 010-1001",
        "balance": 2847.50,
        "minimum_due": 142.38,
        "days_past_due": 37,
        "credit_limit": 5000.00,
        "interest_rate": 24.99,
        "last_payment": {"date": "Nov 15, 2025", "amount": 150.00},
        "payment_history": "Excellent — 8 years, first missed payment",
        "account_opened": "Jan 2017",
        "hardship_enrolled": False,
        "notes": "Reliable payer with no prior hardship flags.",
        "risk_tier": "Low",
        "suggested_action": "Proactive empathy — strong retention candidate",
    },
    "ACC002": {
        "name": "Marcus Thompson",
        "email": "marcus.t@email.com",
        "phone": "(555) 010-1002",
        "balance": 7234.20,
        "minimum_due": 361.71,
        "days_past_due": 68,
        "credit_limit": 8000.00,
        "interest_rate": 22.49,
        "last_payment": {"date": "Sep 30, 2025", "amount": 200.00},
        "payment_history": "Fair — 3 years, 2 previous late payments",
        "account_opened": "Mar 2022",
        "hardship_enrolled": False,
        "notes": "Mentioned recent job change in prior call.",
        "risk_tier": "Medium",
        "suggested_action": "Explore hardship program — 2 months delinquent",
    },
    "ACC003": {
        "name": "Elena Rodriguez",
        "email": "elena.r@email.com",
        "phone": "(555) 010-1003",
        "balance": 4512.80,
        "minimum_due": 225.64,
        "days_past_due": 22,
        "credit_limit": 6000.00,
        "interest_rate": 19.99,
        "last_payment": {"date": "Nov 1, 2025", "amount": 300.00},
        "payment_history": "Excellent — 12 years, clean record",
        "account_opened": "Feb 2013",
        "hardship_enrolled": False,
        "notes": "Mentioned family medical expenses in last interaction.",
        "risk_tier": "Low",
        "suggested_action": "Early intervention — premium customer worth retaining",
    },
}

_payment_plans = {}
_hardship_enrollments = {}


def lookup_customer(account_number=None, name=None):
    if account_number:
        key = account_number.upper().strip()
        if key in CUSTOMERS:
            return {"found": True, "account_number": key, **CUSTOMERS[key]}

    if name:
        for acc_num, customer in CUSTOMERS.items():
            if name.lower().strip() in customer["name"].lower():
                return {"found": True, "account_number": acc_num, **customer}

    return {
        "found": False,
        "message": "Customer not found.",
        "demo_accounts": [
            "ACC001 — Sarah Johnson (37 days past due, $2,847 balance)",
            "ACC002 — Marcus Thompson (68 days past due, $7,234 balance)",
            "ACC003 — Elena Rodriguez (22 days past due, $4,512 balance)",
        ],
    }


def create_payment_plan_record(account_number, monthly_amount, duration_months, start_date="next billing cycle"):
    key = account_number.upper().strip()
    customer = CUSTOMERS.get(key)
    if not customer:
        return {"success": False, "error": "Account not found"}

    plan_id = f"PP-{key}-{datetime.now().strftime('%Y%m%d%H%M')}"
    total = round(monthly_amount * duration_months, 2)

    _payment_plans[plan_id] = {
        "account": key,
        "monthly_amount": monthly_amount,
        "duration_months": duration_months,
        "start_date": start_date,
        "created": datetime.now().isoformat(),
    }

    return {
        "success": True,
        "plan_id": plan_id,
        "customer": customer["name"],
        "monthly_payment": f"${monthly_amount:,.2f}",
        "duration": f"{duration_months} months",
        "start_date": start_date,
        "total_to_pay": f"${total:,.2f}",
        "current_balance": f"${customer['balance']:,.2f}",
        "confirmation": f"Payment plan {plan_id} created. Confirmation sent to {customer['email']}.",
    }


def enroll_hardship_record(account_number, hardship_reason, program_type):
    key = account_number.upper().strip()
    customer = CUSTOMERS.get(key)
    if not customer:
        return {"success": False, "error": "Account not found"}

    programs = {
        "reduced_interest": {
            "label": "Reduced Interest",
            "detail": "Interest rate reduced to 0% for 12 months",
            "benefit": f"Estimated savings: ${customer['balance'] * customer['interest_rate'] / 100:,.0f}",
        },
        "fee_waiver": {
            "label": "Fee Waiver",
            "detail": "All late fees and penalty charges waived immediately",
            "benefit": "Immediate account relief applied",
        },
        "payment_deferral": {
            "label": "Payment Deferral",
            "detail": "90-day payment deferral — no penalties during deferral period",
            "benefit": "No payments required for 3 months",
        },
        "full_hardship": {
            "label": "Full Hardship Package",
            "detail": "0% interest + all fees waived + 60-day deferral",
            "benefit": "Maximum relief for severe financial hardship",
        },
    }

    prog = programs.get(program_type, {"label": program_type, "detail": "Custom relief program", "benefit": "Tailored support"})
    enrollment_id = f"HP-{key}-{datetime.now().strftime('%Y%m%d%H%M')}"

    _hardship_enrollments[enrollment_id] = {
        "account": key,
        "reason": hardship_reason,
        "program": program_type,
        "enrolled": datetime.now().isoformat(),
    }
    CUSTOMERS[key]["hardship_enrolled"] = True

    return {
        "success": True,
        "enrollment_id": enrollment_id,
        "customer": customer["name"],
        "program": prog["label"],
        "details": prog["detail"],
        "benefit": prog["benefit"],
        "reason_on_file": hardship_reason,
        "next_steps": [
            "Account updated immediately",
            f"Welcome letter sent to {customer['email']}",
            "30-day follow-up call scheduled",
        ],
        "confirmation": f"Enrollment {enrollment_id} confirmed.",
    }
