"""
MCP Server that wraps the FastAPI app.
Converts FastAPI endpoints into MCP tools using FastMCP.

Run with: fastmcp run backend/mcp_server.py --transport sse --port 8000
"""

from fastmcp import FastMCP
from app import app
import base64
from fastapi import HTTPException

# Convert FastAPI app to MCP server
mcp = FastMCP.from_fastapi(app=app)

# Override the PDF endpoint to return base64 encoded data instead of binary
@mcp.tool()
async def get_loan_contract_loans(loan_id: str) -> dict:
    """Generate and return the loan contract PDF for the specified loan as base64."""
    from app import db, generate_loan_contract_pdf_bytes
    
    # Find loan
    loan = await db.loans.find_one({"loan_id": loan_id})
    if not loan:
        raise HTTPException(404, "Loan not found")

    # Find customer
    customer = await db.customers.find_one({"customer_id": loan.get("customer_id")})
    if not customer:
        raise HTTPException(404, "Customer not found")

    # Generate PDF bytes
    pdf_bytes = generate_loan_contract_pdf_bytes(loan, customer)
    
    # Encode as base64 so it can be transmitted as text
    pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
    
    return {
        "loan_id": loan_id,
        "filename": f"{loan_id}_contract.pdf",
        "pdf_base64": pdf_base64,
        "message": "PDF contract generated successfully. Decode the base64 string to get the PDF file."
    }

if __name__ == "__main__":
    mcp.run()
