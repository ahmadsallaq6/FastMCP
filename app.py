from fastapi import FastAPI, HTTPException
import uuid
from models import Customer, Account, LoanRequest, Loan
from typing import List
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import httpx
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from twilio.rest import Client

def send_sms(to_number: str, message: str):
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_PHONE_NUMBER")

    if not account_sid or not auth_token or not from_number:
        raise HTTPException(500, "Twilio configuration missing in environment variables.")

    try:
        client = Client(account_sid, auth_token)
        client.messages.create(
            body=message,
            from_=from_number,
            to=to_number
        )
        print("SMS sent successfully")
    except Exception as e:
        raise HTTPException(500, f"SMS send failed: {str(e)}")



def send_email(to_email: str, subject: str, body: str):
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT"))
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    sender_email = os.getenv("SENDER_EMAIL")

    # Email structure
    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = to_email
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.sendmail(sender_email, to_email, msg.as_string())
            print("Email sent successfully")
    except Exception as e:
        raise HTTPException(500, f"Email send failed: {str(e)}")



load_dotenv()

app = FastAPI(title="Teller Banking Backend")

# MongoDB Connection
def get_db():
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        # Fallback for local dev if .env is missing
        mongo_uri = "mongodb://localhost:27017/"
    
    client = AsyncIOMotorClient(mongo_uri)
    return client["loan_assistant_db"]

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
        # If customer exists but has no accounts, return empty list (or 404 as per original logic)
        # Original logic raised 404 "Accounts not found" if customer_id not in db (which was keyed by customer_id)
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

    # Very simple loan eligibility check
    if customer["credit_score"] < 600:
        status = "denied"
    elif request.amount > customer["annual_income"] * 0.3:
        status = "manual_review"
    else:
        status = "approved"

    # Create loan record
    new_loan = {
        "loan_id": "LN-" + str(uuid.uuid4())[:8],
        "customer_id": request.customer_id,
        "amount": request.amount,
        "status": status,
        "remaining_balance": request.amount,
        "purpose": request.purpose
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
@app.get("/search/web", description="Linkup API search")
async def linkup_web_search(query: str):
    LINKUP_API_KEY = os.getenv("LINKUP_API_KEY")
    if not LINKUP_API_KEY:
        raise HTTPException(500, "LINKUP_API_KEY missing")

    # NEW Linkup endpoint (working in 2025)
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


from pydantic import BaseModel

class LoanEmailRequest(BaseModel):
    customer_id: str
    loan_id: str

@app.post("/loans/{customer_id}/notify")
async def notify_customer_loan_status(customer_id: str):
    # Find customer
    customer = await db.customers.find_one({"customer_id": customer_id})
    if not customer:
        raise HTTPException(404, "Customer not found")

    # Find latest loan
    loan = await db.loans.find_one(
        {"customer_id": customer_id},
        sort=[("_id", -1)]
    )
    if not loan:
        raise HTTPException(404, "No loan found for this customer")

    # Build email
    subject = f"Loan Status Update - Loan {loan['loan_id']}"
    message = f"""
Hello {customer['name']},

Your loan application status is: {loan['status'].upper()}.

Loan Amount: ${loan['amount']}
Loan ID: {loan['loan_id']}

Thank you,
Teller Bank
"""

    # Send email
    send_email(
        to_email=customer["email"],
        subject=subject,
        body=message
    )

    return {
        "email_sent_to": customer["email"],
        "loan_status": loan["status"]
    }


@app.post(
    "/loans/send-approval-email",
    description="Sends a loan approval notification email to the customer. This sends an actual email to the customer's registered email address with their loan approval details. Use this after a loan has been approved."
)
async def send_loan_approval_email(request: LoanEmailRequest):
    """Send a loan approval email to the customer"""
    # Find customer
    customer = await db.customers.find_one({"customer_id": request.customer_id})
    if not customer:
        raise HTTPException(404, "Customer not found")

    # Find loan
    loan = await db.loans.find_one({"loan_id": request.loan_id})
    if not loan:
        raise HTTPException(404, "Loan not found")

    if loan["status"] != "approved":
        raise HTTPException(400, "Loan is not approved. Cannot send approval email.")

    # Build approval email
    subject = "Loan Approval Notification"
    message = f"""Dear {customer['name']},

Congratulations! Your loan application for the amount of {loan['amount']} ({loan.get('purpose', 'personal purpose')}) has been approved. The funds are now available, and your initial remaining balance is {loan['remaining_balance']}.

Loan Details:
- Loan ID: {loan['loan_id']}
- Approved Amount: ${loan['amount']}
- Status: {loan['status'].upper()}
- Purpose: {loan.get('purpose', 'Not specified')}

If you have any questions or need further assistance regarding your loan, please don't hesitate to contact us.

Thank you for choosing our services.

Best regards,
Teller Bank Team"""

    try:
        # Send email
        send_email(
            to_email=customer["email"],
            subject=subject,
            body=message
        )
        return {
            "success": True,
            "message": f"Approval email sent successfully to {customer['email']}",
            "email_sent_to": customer["email"],
            "loan_id": loan["loan_id"]
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to send email: {str(e)}")


@app.post(
    "/loans/send-rejection-email",
    description="Sends a loan rejection notification email to the customer. This sends an actual email to the customer's registered email address with the rejection details and reason."
)
async def send_loan_rejection_email(request: LoanEmailRequest):
    """Send a loan rejection email to the customer"""
    # Find customer
    customer = await db.customers.find_one({"customer_id": request.customer_id})
    if not customer:
        raise HTTPException(404, "Customer not found")

    # Find loan
    loan = await db.loans.find_one({"loan_id": request.loan_id})
    if not loan:
        raise HTTPException(404, "Loan not found")

    if loan["status"] != "denied":
        raise HTTPException(400, "Loan was not denied. Cannot send rejection email.")

    # Build rejection email
    subject = "Loan Application Status - Denied"
    message = f"""Dear {customer['name']},

Thank you for your loan application. Unfortunately, we are unable to approve your loan request at this time.

Loan Details:
- Loan ID: {loan['loan_id']}
- Applied Amount: ${loan['amount']}
- Status: DENIED
- Purpose: {loan.get('purpose', 'Not specified')}

Reason for Denial:
Your application did not meet our lending criteria based on the following factors:
- Credit Score: {customer.get('credit_score', 'N/A')}
- Annual Income: ${customer.get('annual_income', 'N/A')}
- Debt-to-Income Ratio: Based on your current financial profile

We encourage you to reapply in the future when your financial situation improves. If you have any questions regarding this decision, please contact our customer service team.

Thank you for considering us.

Best regards,
Teller Bank Team"""

    try:
        # Send email
        send_email(
            to_email=customer["email"],
            subject=subject,
            body=message
        )
        return {
            "success": True,
            "message": f"Rejection email sent successfully to {customer['email']}",
            "email_sent_to": customer["email"],
            "loan_id": loan["loan_id"]
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to send email: {str(e)}")



@app.get("/analytics/loan-summary", description="Summary of all loans in the system")
async def analytics_loan_summary():
    cursor = db.loans.find({})
    loans = await cursor.to_list(None)

    if not loans:
        return {"message": "No loans found"}

    total_loans = len(loans)
    approved = sum(1 for l in loans if l["status"] == "approved")
    denied = sum(1 for l in loans if l["status"] == "denied")
    review = sum(1 for l in loans if l["status"] == "manual_review")

    total_disbursed_amount = sum(l["amount"] for l in loans if l["status"] == "approved")
    avg_amount = round(sum(l["amount"] for l in loans) / total_loans, 2)

    return {
        "total_loans": total_loans,
        "approved": approved,
        "denied": denied,
        "manual_review": review,
        "total_disbursed_amount": total_disbursed_amount,
        "average_loan_amount": avg_amount
    }









class LoanSMSRequest(BaseModel):
    customer_id: str
    loan_id: str


@app.post("/loans/send-status-sms", description="Send SMS to customer with loan status")
async def send_loan_status_sms(request: LoanSMSRequest):

    # Fetch customer
    customer = await db.customers.find_one({"customer_id": request.customer_id})
    if not customer:
        raise HTTPException(404, "Customer not found")

    # Fetch loan
    loan = await db.loans.find_one({"loan_id": request.loan_id})
    if not loan:
        raise HTTPException(404, "Loan not found")

    # SMS Body
    sms_message = (
        f"Teller Bank Update:\n"
        f"Loan ID: {loan['loan_id']}\n"
        f"Status: {loan['status'].upper()}\n"
        f"Amount: ${loan['amount']}"
    )

    # Ensure customer has phone number
    phone = customer.get("phone") or customer.get("mobile") or customer.get("phone_number")
    if not phone:
        raise HTTPException(400, "Customer does not have a phone number registered")

    # Send SMS
    send_sms(phone, sms_message)

    return {
        "success": True,
        "sms_sent_to": phone,
        "loan_status": loan["status"]
    }


@app.post("/loans/send-approval-sms", description="Send SMS to customer when loan is approved")
async def send_loan_approval_sms(request: LoanSMSRequest):
    """
    Send an SMS notification when a loan application is approved.
    """
    # Fetch customer
    customer = await db.customers.find_one({"customer_id": request.customer_id})
    if not customer:
        raise HTTPException(404, "Customer not found")

    # Fetch loan
    loan = await db.loans.find_one({"loan_id": request.loan_id})
    if not loan:
        raise HTTPException(404, "Loan not found")

    # Verify loan is approved
    if loan["status"] != "approved":
        raise HTTPException(400, f"Loan status is {loan['status']}, not approved")

    # SMS Body
    sms_message = (
        f"Great news! Your loan application has been APPROVED!\n\n"
        f"Loan ID: {loan['loan_id']}\n"
        f"Amount: ${loan['amount']}\n"
        f"Status: APPROVED\n\n"
        f"Please log in to your account to review terms and next steps.\n"
        f"Thank you for choosing Teller Bank!"
    )

    # Ensure customer has phone number
    phone = customer.get("phone") or customer.get("mobile") or customer.get("phone_number")
    if not phone:
        raise HTTPException(400, "Customer does not have a phone number registered")

    # Send SMS
    send_sms(phone, sms_message)

    return {
        "success": True,
        "message": f"Approval SMS sent successfully to {phone}",
        "sms_sent_to": phone,
        "loan_id": loan["loan_id"]
    }


@app.post("/loans/send-rejection-sms", description="Send SMS to customer when loan is rejected")
async def send_loan_rejection_sms(request: LoanSMSRequest):
    """
    Send an SMS notification when a loan application is rejected.
    """
    # Fetch customer
    customer = await db.customers.find_one({"customer_id": request.customer_id})
    if not customer:
        raise HTTPException(404, "Customer not found")

    # Fetch loan
    loan = await db.loans.find_one({"loan_id": request.loan_id})
    if not loan:
        raise HTTPException(404, "Loan not found")

    # Verify loan is denied
    if loan["status"] != "denied":
        raise HTTPException(400, f"Loan status is {loan['status']}, not denied")

    # SMS Body
    sms_message = (
        f"Loan Application Update\n\n"
        f"Loan ID: {loan['loan_id']}\n"
        f"Status: DENIED\n"
        f"Amount Requested: ${loan['amount']}\n\n"
        f"Unfortunately, your loan application was not approved at this time.\n"
        f"Please contact our support team for more information.\n"
        f"Thank you for applying to Teller Bank."
    )

    # Ensure customer has phone number
    phone = customer.get("phone") or customer.get("mobile") or customer.get("phone_number")
    if not phone:
        raise HTTPException(400, "Customer does not have a phone number registered")

    # Send SMS
    send_sms(phone, sms_message)

    return {
        "success": True,
        "message": f"Rejection SMS sent successfully to {phone}",
        "sms_sent_to": phone,
        "loan_id": loan["loan_id"]
    }

