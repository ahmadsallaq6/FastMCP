from fastapi import FastAPI, HTTPException
import json
import uuid
from models import Customer, Account, LoanRequest, Loan
from typing import List

app = FastAPI(title="Teller Banking Backend")

# Utility to load JSON
def load_json(path):
    with open(path, "r") as f:
        return json.load(f)

# Utility to save JSON
def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)


# ================
#   LIST ALL CUSTOMERS (NAME + ID ONLY)
# ================
@app.get(
    "/customers/basic",
    description="Returns a lightweight list of all customers containing only customer_id and name."
)
def list_customers_basic():
    customers = load_json("data/customers.json")

    if not isinstance(customers, dict):
        raise HTTPException(500, "Invalid customers.json structure")

    result = [
        {
            "customer_id": data.get("customer_id"),
            "name": data.get("name")
        }
        for data in customers.values()
    ]

    return result


# ================
#   CUSTOMER LOOKUP (FULL DETAILS)
# ================
@app.get(
    "/customers/{customer_id}",
    response_model=Customer,
    description="Retrieves full customer details including personal info, income, credit score, and employment data."
)
def get_customer(customer_id: str):
    db = load_json("data/customers.json")
    if customer_id not in db:
        raise HTTPException(404, "Customer not found")
    return db[customer_id]


# ================
#   ACCOUNT LOOKUP
# ================
@app.get(
    "/customers/{customer_id}/accounts",
    response_model=List[Account],
    description="Returns a list of all bank accounts associated with the given customer ID."
)
def get_accounts(customer_id: str):
    db = load_json("data/accounts.json")
    if customer_id not in db:
        raise HTTPException(404, "Accounts not found")
    return db[customer_id]


# ================
#   LOAN REQUEST
# ================
@app.post(
    "/loans/apply",
    response_model=Loan,
    description="Creates a new loan request for the customer and performs a basic eligibility check using income and credit score."
)
def apply_for_loan(request: LoanRequest):
    customers = load_json("data/customers.json")

    if request.customer_id not in customers:
        raise HTTPException(404, "Customer does not exist")

    customer = customers[request.customer_id]

    # Very simple loan eligibility check
    if customer["credit_score"] < 600:
        status = "denied"
    elif request.amount > customer["annual_income"] * 0.3:
        status = "manual_review"
    else:
        status = "approved"

    # Create loan record
    loans = load_json("data/loans.json")

    new_loan = {
        "loan_id": "LN-" + str(uuid.uuid4())[:8],
        "customer_id": request.customer_id,
        "amount": request.amount,
        "status": status,
        "remaining_balance": request.amount
    }

    loans["loans"].append(new_loan)
    save_json("data/loans.json", loans)

    return new_loan


# ================
#   EXISTING LOANS
# ================
@app.get(
    "/loans/{customer_id}",
    response_model=List[Loan],
    description="Returns all existing loans for a specific customer, including loan status and remaining balance."
)
def get_customer_loans(customer_id: str):
    loans = load_json("data/loans.json")["loans"]
    customer_loans = [l for l in loans if l["customer_id"] == customer_id]
    return customer_loans


# ================
#   DTI (DEBT-TO-INCOME RATIO)
# ================
@app.get(
    "/customers/{customer_id}/dti",
    description="Calculates the customer's Debt-to-Income ratio using monthly income and existing loan obligations. Returns risk level."
)
def calculate_dti(customer_id: str):
    customers = load_json("data/customers.json")
    loans = load_json("data/loans.json")["loans"]

    if customer_id not in customers:
        raise HTTPException(404, "Customer not found")

    customer = customers[customer_id]

    monthly_income = customer["annual_income"] / 12
    customer_loans = [l for l in loans if l["customer_id"] == customer_id]

    existing_monthly_debt = sum(l["remaining_balance"] / 12 for l in customer_loans)

    if monthly_income <= 0:
        dti = None
        status = "invalid_income"
    else:
        dti = existing_monthly_debt / monthly_income

        if dti <= 0.35:
            status = "good"
        elif dti <= 0.45:
            status = "borderline"
        else:
            status = "high_risk"

    return {
        "customer_id": customer_id,
        "monthly_income": round(monthly_income, 2),
        "existing_monthly_debt": round(existing_monthly_debt, 2),
        "dti": round(dti, 4) if dti is not None else None,
        "risk_level": status,
        "total_loans_count": len(customer_loans),
    }


# ================
#   EMPLOYMENT SCORE CALCULATION
# ================
def calculate_employment_score(customer):
    emp_type = customer.get("employment_type")
    years = customer.get("years_with_employer")
    business_years = customer.get("business_years")

    if emp_type == "permanent":
        if years is not None and years >= 2:
            return 1.0
        return 0.7

    if emp_type == "contract":
        return 0.5

    if emp_type in ["part_time", "part-time"]:
        return 0.3

    if emp_type == "self_employed":
        if business_years is not None and business_years >= 3:
            return 0.6
        return 0.4

    return 0.0


# ================
#   EMPLOYMENT SCORE ENDPOINT
# ================
@app.get(
    "/customers/{customer_id}/employment_score",
    description="Returns the customer’s employment stability score based on job type, years of employment, and business history."
)
def get_employment_score(customer_id: str):
    customers = load_json("data/customers.json")

    if customer_id not in customers:
        raise HTTPException(404, "Customer not found")

    customer = customers[customer_id]
    score = calculate_employment_score(customer)

    if score >= 1.0:
        level = "excellent"
    elif score >= 0.7:
        level = "good"
    elif score >= 0.5:
        level = "medium"
    elif score >= 0.3:
        level = "low"
    else:
        level = "unstable"

    return {
        "customer_id": customer_id,
        "employment_type": customer.get("employment_type"),
        "years_with_employer": customer.get("years_with_employer"),
        "business_years": customer.get("business_years"),
        "employment_score": score,
        "stability_level": level
    }
