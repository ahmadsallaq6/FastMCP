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
#   CUSTOMER LOOKUP
# ================
@app.get("/customers/{customer_id}", response_model=Customer)
def get_customer(customer_id: str):
    db = load_json("data/customers.json")
    if customer_id not in db:
        raise HTTPException(404, "Customer not found")
    return db[customer_id]


# ================
#   ACCOUNT LOOKUP
# ================
@app.get("/customers/{customer_id}/accounts", response_model=List[Account])
def get_accounts(customer_id: str):
    db = load_json("data/accounts.json")
    if customer_id not in db:
        raise HTTPException(404, "Accounts not found")
    return db[customer_id]


# ================
#   LOAN REQUEST
# ================
@app.post("/loans/apply", response_model=Loan)
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
@app.get("/loans/{customer_id}", response_model=List[Loan])
def get_customer_loans(customer_id: str):
    loans = load_json("data/loans.json")["loans"]
    customer_loans = [l for l in loans if l["customer_id"] == customer_id]
    return customer_loans
