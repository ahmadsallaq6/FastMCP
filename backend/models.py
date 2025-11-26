"""
Pydantic models for the Loan Assistant application.
Defines data structures for customers, accounts, loans, and requests.
"""

from pydantic import BaseModel
from typing import Literal, Optional


class Customer(BaseModel):
    """Customer profile with financial and employment information."""
    customer_id: str
    name: str
    email: str
    phone: str
    employment_status: str
    annual_income: float
    credit_score: int


class Account(BaseModel):
    """Bank account information."""
    account_id: str
    type: str
    balance: float
    currency: str


class LoanRequest(BaseModel):
    """Request payload for a new loan application."""
    customer_id: str
    amount: float
    purpose: Literal["cars", "house", "personal", "business", "other"]
    force_approve: Optional[bool] = False


class Loan(BaseModel):
    """Loan record with status and balance information."""
    loan_id: str
    customer_id: str
    amount: float
    status: str
    remaining_balance: float
    purpose: str
