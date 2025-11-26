"""
FastAPI application for the Loan Assistant Banking Backend.
Provides REST endpoints for customer, account, and loan operations.
"""

from fastapi import FastAPI, HTTPException
import uuid
from typing import List
import os
import httpx
from dotenv import load_dotenv

from models import Customer, Account, LoanRequest, Loan
from database import get_db

load_dotenv()

app = FastAPI(title="Teller Banking Backend")

# Get database connection
db = get_db()


# ================
#   LIST ALL CUSTOMERS (NAME + ID ONLY)
# ================
@app.get(
    "/customers/basic",
    description="Returns a lightweight list of all customers containing only customer_id and name."
)
async def list_customers_basic():
    cursor = db.customers.find({}, {"customer_id": 1, "name": 1, "_id": 0})
    customers = await cursor.to_list(length=None)
    return customers


# ================
#   CUSTOMER LOOKUP (FULL DETAILS)
# ================
@app.get(
    "/customers/{customer_id}",
    response_model=Customer,
    description="Retrieves full customer details including personal info, income, credit score, and employment data."
)
async def get_customer(customer_id: str):
    customer = await db.customers.find_one({"customer_id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(404, "Customer not found")
    return customer


# ================
#   ACCOUNT LOOKUP
# ================
@app.get(
    "/customers/{customer_id}/accounts",
    response_model=List[Account],
    description="Returns a list of all bank accounts associated with the given customer ID."
)
async def get_accounts(customer_id: str):
    cursor = db.accounts.find({"customer_id": customer_id}, {"_id": 0})
    accounts = await cursor.to_list(length=None)
    if not accounts:
        # Check if customer exists to distinguish between no accounts and invalid customer
        if not await db.customers.find_one({"customer_id": customer_id}):
            raise HTTPException(404, "Customer not found")
        raise HTTPException(404, "Accounts not found")
    return accounts


# ================
#   LOAN REQUEST
# ================
@app.post(
    "/loans/apply",
    response_model=Loan,
    description="Creates a new loan request for the customer and performs a basic eligibility check using income and credit score."
)
async def apply_for_loan(request: LoanRequest):
    customer = await db.customers.find_one({"customer_id": request.customer_id})

    if not customer:
        raise HTTPException(404, "Customer does not exist")

    user_override = bool(getattr(request, "force_approve", False))

    if user_override:
        status = "approved"
        decision_source = "user_override"
        decision_reason = "manual approval by advisor"
    else:
        # Very simple loan eligibility check
        if customer["credit_score"] < 600:
            status = "denied"
            decision_source = "system_auto"
            decision_reason = "credit_score_below_600"
        elif request.amount > customer["annual_income"] * 0.3:
            status = "manual_review"
            decision_source = "system_auto"
            decision_reason = "amount_exceeds_30pct_income"
        else:
            status = "approved"
            decision_source = "system_auto"
            decision_reason = "meets_basic_criteria"

    # Create loan record
    new_loan = {
        "loan_id": "LN-" + str(uuid.uuid4())[:8],
        "customer_id": request.customer_id,
        "amount": request.amount,
        "status": status,
        "remaining_balance": request.amount,
        "purpose": request.purpose,
        "decision_source": decision_source,
        "decision_reason": decision_reason,
    }

    await db.loans.insert_one(new_loan)
    
    # Remove _id for response
    if "_id" in new_loan:
        del new_loan["_id"]

    return new_loan


# ================
#   EXISTING LOANS
# ================
@app.get(
    "/loans/{customer_id}",
    response_model=List[Loan],
    description="Returns all existing loans for a specific customer, including loan status and remaining balance."
)
async def get_customer_loans(customer_id: str):
    cursor = db.loans.find({"customer_id": customer_id}, {"_id": 0})
    customer_loans = await cursor.to_list(length=None)
    return customer_loans


# ================
#   DTI (DEBT-TO-INCOME RATIO)
# ================
@app.get(
    "/customers/{customer_id}/dti",
    description="Calculates the customer's Debt-to-Income ratio using monthly income and existing loan obligations. Returns risk level."
)
async def calculate_dti(customer_id: str):
    customer = await db.customers.find_one({"customer_id": customer_id})
    
    if not customer:
        raise HTTPException(404, "Customer not found")

    cursor = db.loans.find({"customer_id": customer_id})
    customer_loans = await cursor.to_list(length=None)

    monthly_income = customer["annual_income"] / 12
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
def calculate_employment_score(customer: dict) -> float:
    """Calculate employment stability score based on job type and tenure.
    
    Args:
        customer: Customer document with employment fields
        
    Returns:
        Employment score between 0.0 and 1.0
    """
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
    description="Returns the customer's employment stability score based on job type, years of employment, and business history."
)
async def get_employment_score(customer_id: str):
    customer = await db.customers.find_one({"customer_id": customer_id})

    if not customer:
        raise HTTPException(404, "Customer not found")

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


# ============================
# LINKUP WEB SEARCH ENDPOINT
# ============================
@app.get(
    "/search/web",
    description="Linkup API search for web content."
)
async def linkup_web_search(query: str):
    LINKUP_API_KEY = os.getenv("LINKUP_API_KEY")
    if not LINKUP_API_KEY:
        raise HTTPException(500, "LINKUP_API_KEY missing")

    url = "https://api.linkup.so/v1/search"

    payload = {
        "q": query,
        "outputType": "searchResults",
        "includeImages": False,
        "depth": "standard"
    }

    headers = {
        "Authorization": f"Bearer {LINKUP_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
        except Exception as e:
            raise HTTPException(500, f"Request failed: {str(e)}")

    if response.status_code != 200:
        raise HTTPException(response.status_code, response.text)

    return response.json()
