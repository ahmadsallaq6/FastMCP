from pydantic import BaseModel
from typing import Optional, List

class Customer(BaseModel):
    customer_id: str
    name: str
    email: str
    phone: str
    employment_status: str
    annual_income: float
    credit_score: int

class Account(BaseModel):
    account_id: str
    type: str
    balance: float
    currency: str

class LoanRequest(BaseModel):
    customer_id: str
    amount: float
    purpose: str

class Loan(BaseModel):
    loan_id: str
    customer_id: str
    amount: float
    status: str
    remaining_balance: float
