"""
FastAPI application for the Loan Assistant Banking Backend.
Provides REST endpoints for customer, account, and loan operations.
"""

from fastapi import FastAPI, HTTPException
import uuid
from typing import List, Optional
import os
import httpx
import smtplib
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from twilio.rest import Client
from dotenv import load_dotenv
from fastapi.responses import StreamingResponse
from models import Customer, Account, LoanRequest, Loan, GenericEmailRequest, LoanSMSRequest, LoanEmailRequest
from database import get_db

# pdf_utils.py
import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.units import mm



# Load environment variables from the project root .env file
# This must be done early, before any functions try to read env vars
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_project_root, ".env"))



def generate_loan_contract_pdf_bytes(loan: dict, customer: dict, issuer_name: str = "Teller Bank"):
    """
    Generate a loan contract PDF and return bytes.
    loan, customer are dicts from your DB.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=20*mm, leftMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='ContractTitle', fontSize=16, leading=20, spaceAfter=12, alignment=1))  # centered
    styles.add(ParagraphStyle(name='Body', fontSize=11, leading=14))
    styles.add(ParagraphStyle(name='Small', fontSize=9, leading=11))

    elems = []

    # Title
    elems.append(Paragraph("Loan Contract", styles['ContractTitle']))
    elems.append(Spacer(1, 6))

    # Meta
    contract_date = datetime.utcnow().strftime("%Y-%m-%d")
    meta_table_data = [
        ["Contract ID:", loan.get("loan_id", "")],
        ["Date:", contract_date],
        ["Issuer:", issuer_name]
    ]
    meta_table = Table(meta_table_data, hAlign="LEFT", colWidths=[80*mm, 80*mm])
    meta_table.setStyle(TableStyle([
        ("FONTNAME", (0,0), (-1,-1), "Helvetica"),
        ("FONTSIZE", (0,0), (-1,-1), 10),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    elems.append(meta_table)
    elems.append(Spacer(1, 8))

    # Parties
    parties_text = (
        f"<b>Party A (Lender):</b> {issuer_name}<br/>"
        f"<b>Party B (Borrower):</b> {customer.get('name','')} - Customer ID: {customer.get('customer_id','')}"
    )
    elems.append(Paragraph(parties_text, styles['Body']))
    elems.append(Spacer(1, 8))

    # Loan summary table
    loan_table_data = [
        ["Loan ID", loan.get("loan_id", "")],
        ["Principal Amount (JOD)", f"{loan.get('amount', '')}"],
        ["Remaining Balance (JOD)", f"{loan.get('remaining_balance', '')}"],
        ["Status", loan.get("status", "")],
        ["Purpose", loan.get("purpose", "")],
    ]
    loan_table = Table(loan_table_data, hAlign="LEFT", colWidths=[60*mm, 100*mm])
    loan_table.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
        ("FONTNAME", (0,0), (-1,-1), "Helvetica"),
        ("FONTSIZE", (0,0), (-1,-1), 10),
        ("BACKGROUND", (0,0), (0,-1), colors.whitesmoke),
    ]))
    elems.append(loan_table)
    elems.append(Spacer(1, 12))

    # Terms / short contract body (editable)
    terms = f"""
    This Loan Contract ("Contract") is entered into on {contract_date} between {issuer_name} (the "Lender") and {customer.get('name','')} (the "Borrower").
    <br/><br/>
    1. Loan Amount: The Lender agrees to loan the Borrower the principal sum of {loan.get('amount', '')} JOD.
    <br/><br/>
    2. Repayment: The Borrower agrees to repay the outstanding balance according to the schedule agreed in the loan records. The current remaining balance is {loan.get('remaining_balance', '')} JOD.
    <br/><br/>
    3. Interest and Fees: Interest, fees, and penalties (if any) are governed by the terms previously agreed and recorded in the loan file.
    <br/><br/>
    4. Default: In the event of default, remedies shall be pursued as permitted under applicable law.
    <br/><br/>
    5. Governing Law: This Contract shall be governed by the laws applicable where the Lender operates.
    """
    # Render contract text as paragraphs (break into paragraphs)
    for p in terms.split("<br/><br/>"):
        elems.append(Paragraph(p.strip(), styles['Body']))
        elems.append(Spacer(1, 8))

    # Signatures table (placeholders)
    sign_table = Table(
        [
            ["__________________________", "__________________________"],
            ["Lender Signature", "Borrower Signature"],
            [f"Name: {issuer_name}", f"Name: {customer.get('name','')}"],
            [f"Date: {contract_date}", "Date: ____________"]
        ],
        colWidths=[80*mm, 80*mm],
        hAlign="LEFT"
    )
    sign_table.setStyle(TableStyle([
        ("ALIGN", (0,0), (-1,0), "CENTER"),
        ("FONTNAME", (0,1), (-1,-1), "Helvetica"),
        ("FONTSIZE", (0,0), (-1,-1), 10),
        ("TOPPADDING", (0,0), (-1,-1), 6),
    ]))
    elems.append(Spacer(1, 18))
    elems.append(sign_table)
    elems.append(Spacer(1, 12))

    # Footer small print
    footer = "This contract is autogenerated. For full loan terms refer to the loan agreement stored in bank records."
    elems.append(Paragraph(footer, styles['Small']))

    # Build
    doc.build(elems)

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

def send_email(to_email: str, subject: str, body: str):
    """Send an email using SMTP settings from the environment."""
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "0"))
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    sender_email = os.getenv("SENDER_EMAIL")

    if not (smtp_host and smtp_port and smtp_username and smtp_password and sender_email):
        raise HTTPException(500, "SMTP configuration missing in environment variables.")

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
    except Exception as exc:  # pragma: no cover - smtp failure
        raise HTTPException(500, f"Email send failed: {str(exc)}") from exc


# ============================
# INFOBIP SMS HELPER
# ============================
async def send_sms_infobip(to_number: str, message: str):
    base_url = os.getenv("INFOBIP_BASE_URL")
    api_key = os.getenv("INFOBIP_API_KEY")
    sender = os.getenv("INFOBIP_SENDER")

    if not base_url or not api_key or not sender:
        raise HTTPException(500, "Infobip configuration missing")

    url = f"https://{base_url}/sms/2/text/advanced"

    payload = {
        "messages": [
            {
                "from": sender,
                "destinations": [{"to": to_number}],
                "text": message
            }
        ]
    }

    headers = {
        "Authorization": f"App {api_key}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers)

    if response.status_code >= 400:
        # return info for logging/inspection
        return {"status": "failed", "http_status": response.status_code, "error": response.text}

    return {"status": "sent", "http_status": response.status_code, "response": response.json()}





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


@app.post(
    "/communications/send-email",
    description=(
        "Sends a custom email to a customer with optional loan context. "
        "LLM callers must supply the full subject and body content."
    ),
)
async def send_custom_email(request: GenericEmailRequest):
    """Send an arbitrary email to the specified customer."""
    customer = await db.customers.find_one({"customer_id": request.customer_id})
    if not customer:
        raise HTTPException(404, "Customer not found")

    loan = None
    if request.loan_id:
        loan = await db.loans.find_one({"loan_id": request.loan_id})
        if not loan:
            raise HTTPException(404, "Loan not found")

    send_email(to_email=customer["email"], subject=request.subject, body=request.body)

    response = {
        "email_sent_to": customer["email"],
        "customer_id": request.customer_id,
        "subject_preview": request.subject,
        "loan_id": request.loan_id,
    }

    if loan:
        response["loan_status"] = loan.get("status")

    return response


@app.get("/analytics/loan-summary", description="Summary of all loans in the system")
async def analytics_loan_summary():
    cursor = db.loans.find({})
    loans = await cursor.to_list(None)

    if not loans:
        return {"message": "No loans found"}

    total_loans = len(loans)
    approved = sum(1 for loan in loans if loan["status"] == "approved")
    denied = sum(1 for loan in loans if loan["status"] == "denied")
    review = sum(1 for loan in loans if loan["status"] == "manual_review")

    total_disbursed_amount = sum(loan["amount"] for loan in loans if loan["status"] == "approved")
    avg_amount = round(sum(loan["amount"] for loan in loans) / total_loans, 2)

    return {
        "total_loans": total_loans,
        "approved": approved,
        "denied": denied,
        "manual_review": review,
        "total_disbursed_amount": total_disbursed_amount,
        "average_loan_amount": avg_amount,
    }

@app.post("/loans/send-approval-sms", description="Sends a loan approval SMS to the customer using Infobip.")
async def send_loan_approval_sms(request: LoanEmailRequest):
    # Fetch customer
    customer = await db.customers.find_one({"customer_id": request.customer_id})
    if not customer:
        raise HTTPException(404, "Customer not found")

    # Fetch loan
    loan = await db.loans.find_one({"loan_id": request.loan_id})
    if not loan:
        raise HTTPException(404, "Loan not found")

    if loan["status"] != "approved":
        raise HTTPException(400, "Loan is not approved. Cannot send approval SMS.")

    # Build short SMS (same intent as email, compact)
    sms_text = (
        f"Hi {customer['name']}, your loan {loan['loan_id']} "
        f"for {loan['amount']} JOD is APPROVED. Thank you - Teller Bank."
    )

    # Ensure customer has phone number
    phone = customer.get("phone") or customer.get("mobile") or customer.get("phone_number")
    if not phone:
        raise HTTPException(400, "Customer phone number is not available")

    # Send SMS via Infobip
    sms_result = await send_sms_infobip(phone, sms_text)

    if sms_result.get("status") == "failed":
        # You can choose to log this or fallback to email. For now return failure info.
        raise HTTPException(500, f"Failed to send SMS: {sms_result.get('error')}")

    return {
        "success": True,
        "sms_sent_to": phone,
        "loan_id": loan["loan_id"],
        "sms_result": sms_result
    }


@app.get("/loans/{loan_id}/contract", description="Generate and return the loan contract PDF for the specified loan.")
async def get_loan_contract(loan_id: str):
    # Find loan
    loan = await db.loans.find_one({"loan_id": loan_id})
    if not loan:
        raise HTTPException(404, "Loan not found")

    # Find customer
    customer = await db.customers.find_one({"customer_id": loan.get("customer_id")})
    if not customer:
        raise HTTPException(404, "Customer not found")

    # Optional: check permission / only allow if loan is approved - you decide
    # if loan.get("status") != "approved":
    #     raise HTTPException(400, "Loan is not approved; contract cannot be generated.")

    pdf_bytes = generate_loan_contract_pdf_bytes(loan, customer)

    # Optionally: persist the PDF to disk or upload to S3 here
    # with open(f"/tmp/{loan_id}_contract.pdf", "wb") as f:
    #     f.write(pdf_bytes)

    # Encode as base64 for MCP tool compatibility
    import base64
    pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
    
    return {
        "loan_id": loan_id,
        "filename": f"{loan_id}_contract.pdf",
        "pdf_base64": pdf_base64,
        "message": "PDF contract generated successfully. Decode the base64 string to get the PDF file."
    }
