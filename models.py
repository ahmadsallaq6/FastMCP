from pydantic import BaseModel
from typing import Optional, List, Literal

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
    purpose: Literal["cars", "house", "personal", "business", "other"]

class Loan(BaseModel):
    loan_id: str
    customer_id: str
    amount: float
    status: str
    remaining_balance: float
    purpose: str


class GenericEmailRequest(BaseModel):
    customer_id: str
    subject: str
    body: str
    loan_id: Optional[str] = None


class LoanSMSRequest(BaseModel):
    customer_id: str
    loan_id: str


