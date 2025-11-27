"""
Dashboard module for the Loans Assistant application.
Displays comprehensive statistics and visualizations of loan and customer data.
"""

import json
import os
import sys
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from collections import Counter
from typing import Dict, List, Any, Tuple, Optional, Literal

from config import THEME_COLORS

# Ensure backend package is importable for database connectivity
BACKEND_PATH = os.path.join(os.path.dirname(__file__), "..", "backend")
if BACKEND_PATH not in sys.path:
    sys.path.insert(0, BACKEND_PATH)

try:
    from database import get_mongo_client, get_mongo_collection
except ModuleNotFoundError:
    get_mongo_client = None
    get_mongo_collection = None

# Fallback data paths for JSON files
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def load_json_data(filename: str) -> Any:
    """Load JSON data from the data directory (fallback)."""
    filepath = os.path.join(DATA_DIR, filename)
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception as e:
        return None


def get_mongodb_data() -> Tuple[Dict, List, Dict]:
    """Fetch data from MongoDB collections."""
    customers = {}
    loans = []
    accounts = {}
    
    if get_mongo_client is None:
        return customers, loans, accounts
    
    client = get_mongo_client()
    if client is None:
        return customers, loans, accounts
    
    try:
        db = client["loan_assistant_db"]
        
        # Fetch customers
        customers_cursor = db.customers.find({}, {"_id": 0})
        for cust in customers_cursor:
            cust_id = cust.get("customer_id")
            if cust_id:
                customers[cust_id] = cust
        
        # Fetch loans
        loans_cursor = db.loans.find({}, {"_id": 0})
        loans = list(loans_cursor)
        
        # Fetch accounts - group by customer_id
        accounts_cursor = db.accounts.find({}, {"_id": 0})
        for acct in accounts_cursor:
            cust_id = acct.get("customer_id")
            if cust_id:
                if cust_id not in accounts:
                    accounts[cust_id] = []
                accounts[cust_id].append(acct)
        
    except Exception as e:
        st.warning(f"Error fetching from MongoDB: {e}")
        return customers, loans, accounts
    
    return customers, loans, accounts


def get_dashboard_data() -> Tuple[Dict, List, Dict]:
    """Load dashboard data from MongoDB, with JSON fallback."""
    # Try MongoDB first
    customers, loans, accounts = get_mongodb_data()
    
    # Check if we got data from MongoDB
    if customers or loans or accounts:
        return customers, loans, accounts
    
    # Fallback to JSON files
    st.info("📁 Using JSON file data (MongoDB not available)")
    
    customers = load_json_data("customers.json") or {}
    loans_data = load_json_data("loans.json") or {"loans": []}
    accounts = load_json_data("accounts.json") or {}
    
    loans = loans_data.get("loans", []) if isinstance(loans_data, dict) else loans_data
    
    return customers, loans, accounts


def get_plotly_theme() -> Dict:
    """Get Plotly theme configuration matching the app's light theme."""
    colors = THEME_COLORS["light"]
    
    return {
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {
            "color": colors["text_primary"],
            "family": "system-ui, -apple-system, sans-serif"
        },
        "colorway": [
            "#7c3aed",  # Primary purple
            "#06b6d4",  # Cyan
            "#10b981",  # Green
            "#f59e0b",  # Amber
            "#ef4444",  # Red
            "#8b5cf6",  # Violet
            "#ec4899",  # Pink
            "#14b8a6",  # Teal
        ],
        "gridcolor": "rgba(124, 58, 237, 0.1)",
    }


def create_metric_card(label: str, value: str, delta: Optional[str] = None, delta_color: Literal["normal", "inverse", "off"] = "normal") -> None:
    """Create a styled metric card."""
    st.metric(label=label, value=value, delta=delta, delta_color=delta_color)


def calculate_loan_statistics(loans: List[Dict]) -> Dict:
    """Calculate comprehensive loan statistics."""
    if not loans:
        return {
            "total": 0,
            "approved": 0,
            "denied": 0,
            "active": 0,
            "pending": 0,
            "total_amount": 0,
            "total_remaining": 0,
            "avg_loan_amount": 0,
            "status_counts": {},
        }
    
    status_counts = Counter()
    total_amount = 0
    total_remaining = 0
    approved_count = 0
    denied_count = 0
    
    for loan in loans:
        status = loan.get("status", "unknown").lower()
        status_counts[status] += 1
        total_amount += loan.get("amount", 0)
        total_remaining += loan.get("remaining_balance", 0)
        
        # Count approved/denied based on the 'approved' boolean field
        approved_field = loan.get("approved")
        if approved_field is True:
            approved_count += 1
        elif approved_field is False:
            denied_count += 1
    
    return {
        "total": len(loans),
        "approved": approved_count,
        "denied": denied_count,
        "active": status_counts.get("active", 0),
        "pending": status_counts.get("pending", 0) + status_counts.get("pending_review", 0) + status_counts.get("manual_review", 0),
        "total_amount": total_amount,
        "total_remaining": total_remaining,
        "avg_loan_amount": total_amount / len(loans) if loans else 0,
        "status_counts": dict(status_counts),
    }


def calculate_customer_statistics(customers: Dict, loans: List[Dict]) -> Dict:
    """Calculate comprehensive customer statistics."""
    if not customers:
        return {
            "total": 0,
            "employed": 0,
            "self_employed": 0,
            "unemployed": 0,
            "avg_credit_score": 0,
            "avg_income": 0,
            "with_risk_flags": 0,
            "customers_with_loans": 0,
        }
    
    employment_counts = Counter()
    total_credit_score = 0
    total_income = 0
    with_risk_flags = 0
    
    for cust_id, customer in customers.items():
        emp_status = customer.get("employment_status", "Unknown")
        employment_counts[emp_status] += 1
        total_credit_score += customer.get("credit_score", 0)
        total_income += customer.get("annual_income", 0)
        if customer.get("risk_flags"):
            with_risk_flags += 1
    
    # Count unique customers with loans
    customers_with_loans = len(set(loan.get("customer_id") for loan in loans))
    
    return {
        "total": len(customers),
        "employed": employment_counts.get("Employed", 0),
        "self_employed": employment_counts.get("Self-Employed", 0),
        "unemployed": employment_counts.get("Unemployed", 0),
        "avg_credit_score": total_credit_score / len(customers) if customers else 0,
        "avg_income": total_income / len(customers) if customers else 0,
        "with_risk_flags": with_risk_flags,
        "customers_with_loans": customers_with_loans,
        "employment_counts": dict(employment_counts),
    }


def calculate_account_statistics(accounts: Dict) -> Dict:
    """Calculate account statistics."""
    if not accounts:
        return {
            "total_accounts": 0,
            "total_balance": 0,
            "account_types": {},
        }
    
    total_accounts = 0
    total_balance = 0
    account_types = Counter()
    
    for cust_id, acct_list in accounts.items():
        for account in acct_list:
            total_accounts += 1
            total_balance += account.get("balance", 0)
            account_types[account.get("type", "Unknown")] += 1
    
    return {
        "total_accounts": total_accounts,
        "total_balance": total_balance,
        "account_types": dict(account_types),
    }


def render_kpi_section(loan_stats: Dict, customer_stats: Dict, account_stats: Dict) -> None:
    """Render the KPI metrics section with styled cards."""
    st.markdown("""
        <div style="margin-bottom: 1rem;">
            <h3 style="margin: 0; color: #0f172a;">📊 Key Performance Indicators</h3>
            <p style="color: #6b7280; font-size: 0.9rem; margin-top: 0.25rem;">Real-time overview of your banking operations</p>
        </div>
    """, unsafe_allow_html=True)
    
    # First row - Main metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("""
            <div class="dashboard-card">
                <div class="card-icon">👥</div>
                <div class="card-content">
                    <div class="card-value">{}</div>
                    <div class="card-label">Total Customers</div>
                </div>
            </div>
        """.format(customer_stats["total"]), unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
            <div class="dashboard-card">
                <div class="card-icon">📋</div>
                <div class="card-content">
                    <div class="card-value">{}</div>
                    <div class="card-label">Total Loans</div>
                </div>
            </div>
        """.format(loan_stats["total"]), unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
            <div class="dashboard-card success">
                <div class="card-icon">✅</div>
                <div class="card-content">
                    <div class="card-value">{}</div>
                    <div class="card-label">Approved Loans</div>
                </div>
            </div>
        """.format(loan_stats["approved"]), unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
            <div class="dashboard-card danger">
                <div class="card-icon">❌</div>
                <div class="card-content">
                    <div class="card-value">{}</div>
                    <div class="card-label">Denied Loans</div>
                </div>
            </div>
        """.format(loan_stats["denied"]), unsafe_allow_html=True)
    
    # Second row - Financial metrics
    col5, col6, col7, col8 = st.columns(4)
    
    with col5:
        st.markdown("""
            <div class="dashboard-card info">
                <div class="card-icon">🏃</div>
                <div class="card-content">
                    <div class="card-value">{}</div>
                    <div class="card-label">Active Loans</div>
                </div>
            </div>
        """.format(loan_stats["active"]), unsafe_allow_html=True)
    
    with col6:
        st.markdown("""
            <div class="dashboard-card">
                <div class="card-icon">💰</div>
                <div class="card-content">
                    <div class="card-value">${:,.0f}</div>
                    <div class="card-label">Total Loan Volume</div>
                </div>
            </div>
        """.format(loan_stats["total_amount"]), unsafe_allow_html=True)
    
    with col7:
        st.markdown("""
            <div class="dashboard-card">
                <div class="card-icon">📈</div>
                <div class="card-content">
                    <div class="card-value">${:,.0f}</div>
                    <div class="card-label">Outstanding Balance</div>
                </div>
            </div>
        """.format(loan_stats["total_remaining"]), unsafe_allow_html=True)
    
    with col8:
        st.markdown("""
            <div class="dashboard-card">
                <div class="card-icon">🏦</div>
                <div class="card-content">
                    <div class="card-value">{}</div>
                    <div class="card-label">Total Accounts</div>
                </div>
            </div>
        """.format(account_stats["total_accounts"]), unsafe_allow_html=True)


def render_loan_status_chart(loan_stats: Dict) -> None:
    """Render loan status distribution pie chart."""
    theme = get_plotly_theme()
    
    status_data = loan_stats["status_counts"]
    if not status_data:
        st.info("No loan data available")
        return
    
    # Capitalize status labels for display
    labels = [s.title() for s in status_data.keys()]
    values = list(status_data.values())
    
    # Custom colors for each status
    color_map = {
        "Approved": "#10b981",
        "Active": "#06b6d4",
        "Denied": "#ef4444",
        "Pending": "#f59e0b",
        "Pending_Review": "#f59e0b",
        "Unknown": "#6b7280",
    }
    colors = [color_map.get(label, "#7c3aed") for label in labels]
    
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.5,
        marker=dict(colors=colors),
        textinfo='label+percent',
        textposition='outside',
        textfont=dict(size=12, color=theme["font"]["color"]),
        hovertemplate='<b>%{label}</b><br>Count: %{value}<br>Percentage: %{percent}<extra></extra>'
    )])
    
    fig.update_layout(
        paper_bgcolor=theme["paper_bgcolor"],
        plot_bgcolor=theme["plot_bgcolor"],
        font=theme["font"],
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.15,
            xanchor="center",
            x=0.5,
            font=dict(size=11)
        ),
        margin=dict(t=20, b=60, l=20, r=20),
        height=350,
        annotations=[dict(
            text=f"<b>{loan_stats['total']}</b><br>Total",
            x=0.5, y=0.5,
            font=dict(size=16, color=theme["font"]["color"]),
            showarrow=False
        )]
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_loans_by_customer_chart(loans: List[Dict], customers: Dict) -> None:
    """Render loans distribution by customer bar chart."""
    theme = get_plotly_theme()
    
    if not loans:
        st.info("No loan data available")
        return
    
    # Count loans per customer
    loans_per_customer = Counter(loan.get("customer_id") for loan in loans)
    
    # Get customer names
    customer_names = []
    loan_counts = []
    for cust_id, count in loans_per_customer.most_common(10):
        name = customers.get(cust_id, {}).get("name", cust_id)
        customer_names.append(name)
        loan_counts.append(count)
    
    fig = go.Figure(data=[go.Bar(
        x=customer_names,
        y=loan_counts,
        marker=dict(
            color=loan_counts,
            colorscale=[[0, '#c4bcff'], [0.5, '#7c3aed'], [1, '#4c1d95']],
            line=dict(width=0)
        ),
        text=loan_counts,
        textposition='outside',
        textfont=dict(size=12, color=theme["font"]["color"]),
        hovertemplate='<b>%{x}</b><br>Loans: %{y}<extra></extra>'
    )])
    
    fig.update_layout(
        paper_bgcolor=theme["paper_bgcolor"],
        plot_bgcolor=theme["plot_bgcolor"],
        font=theme["font"],
        xaxis=dict(
            title="Customer",
            tickangle=-45,
            gridcolor=theme["gridcolor"],
            showgrid=False,
        ),
        yaxis=dict(
            title="Number of Loans",
            gridcolor=theme["gridcolor"],
            showgrid=True,
        ),
        margin=dict(t=30, b=100, l=60, r=20),
        height=350,
        bargap=0.3,
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_loan_amounts_chart(loans: List[Dict]) -> None:
    """Render loan amounts distribution histogram."""
    theme = get_plotly_theme()
    
    if not loans:
        st.info("No loan data available")
        return
    
    amounts = [loan.get("amount", 0) for loan in loans if loan.get("amount", 0) > 0]
    
    fig = go.Figure(data=[go.Histogram(
        x=amounts,
        nbinsx=15,
        marker=dict(
            color='#7c3aed',
            line=dict(color='#4c1d95', width=1)
        ),
        hovertemplate='Range: $%{x}<br>Count: %{y}<extra></extra>'
    )])
    
    fig.update_layout(
        paper_bgcolor=theme["paper_bgcolor"],
        plot_bgcolor=theme["plot_bgcolor"],
        font=theme["font"],
        xaxis=dict(
            title="Loan Amount ($)",
            gridcolor=theme["gridcolor"],
            showgrid=True,
            tickformat="$,.0f"
        ),
        yaxis=dict(
            title="Frequency",
            gridcolor=theme["gridcolor"],
            showgrid=True,
        ),
        margin=dict(t=30, b=60, l=60, r=20),
        height=300,
        bargap=0.05,
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_employment_chart(customer_stats: Dict) -> None:
    """Render employment status distribution."""
    theme = get_plotly_theme()
    
    emp_data = customer_stats.get("employment_counts", {})
    if not emp_data:
        st.info("No customer data available")
        return
    
    labels = list(emp_data.keys())
    values = list(emp_data.values())
    
    # Colors for employment status
    color_map = {
        "Employed": "#10b981",
        "Self-Employed": "#06b6d4",
        "Unemployed": "#ef4444",
    }
    colors = [color_map.get(label, "#7c3aed") for label in labels]
    
    fig = go.Figure(data=[go.Bar(
        x=labels,
        y=values,
        marker=dict(color=colors),
        text=values,
        textposition='outside',
        textfont=dict(size=14, color=theme["font"]["color"]),
        hovertemplate='<b>%{x}</b><br>Count: %{y}<extra></extra>'
    )])
    
    fig.update_layout(
        paper_bgcolor=theme["paper_bgcolor"],
        plot_bgcolor=theme["plot_bgcolor"],
        font=theme["font"],
        xaxis=dict(
            title="Employment Status",
            gridcolor=theme["gridcolor"],
            showgrid=False,
        ),
        yaxis=dict(
            title="Number of Customers",
            gridcolor=theme["gridcolor"],
            showgrid=True,
        ),
        margin=dict(t=30, b=60, l=60, r=20),
        height=300,
        bargap=0.4,
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_credit_score_distribution(customers: Dict) -> None:
    """Render credit score distribution chart."""
    theme = get_plotly_theme()
    
    if not customers:
        st.info("No customer data available")
        return
    
    credit_scores = [c.get("credit_score", 0) for c in customers.values() if c.get("credit_score", 0) > 0]
    customer_names = [c.get("name", "Unknown") for c in customers.values() if c.get("credit_score", 0) > 0]
    
    # Define score ranges and colors
    def get_score_color(score):
        if score >= 750:
            return "#10b981"  # Excellent - green
        elif score >= 700:
            return "#06b6d4"  # Good - cyan
        elif score >= 650:
            return "#f59e0b"  # Fair - amber
        else:
            return "#ef4444"  # Poor - red
    
    colors = [get_score_color(s) for s in credit_scores]
    
    fig = go.Figure(data=[go.Bar(
        x=customer_names,
        y=credit_scores,
        marker=dict(color=colors),
        text=credit_scores,
        textposition='outside',
        textfont=dict(size=12, color=theme["font"]["color"]),
        hovertemplate='<b>%{x}</b><br>Credit Score: %{y}<extra></extra>'
    )])
    
    # Add reference lines for score categories
    fig.add_hline(y=750, line_dash="dash", line_color="#10b981", annotation_text="Excellent (750+)", annotation_position="right")
    fig.add_hline(y=700, line_dash="dash", line_color="#06b6d4", annotation_text="Good (700+)", annotation_position="right")
    fig.add_hline(y=650, line_dash="dash", line_color="#f59e0b", annotation_text="Fair (650+)", annotation_position="right")
    
    fig.update_layout(
        paper_bgcolor=theme["paper_bgcolor"],
        plot_bgcolor=theme["plot_bgcolor"],
        font=theme["font"],
        xaxis=dict(
            title="Customer",
            gridcolor=theme["gridcolor"],
            showgrid=False,
        ),
        yaxis=dict(
            title="Credit Score",
            gridcolor=theme["gridcolor"],
            showgrid=True,
            range=[0, 850]
        ),
        margin=dict(t=30, b=60, l=60, r=100),
        height=350,
        bargap=0.3,
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_account_types_chart(account_stats: Dict) -> None:
    """Render account types distribution."""
    theme = get_plotly_theme()
    
    acct_types = account_stats.get("account_types", {})
    if not acct_types:
        st.info("No account data available")
        return
    
    labels = list(acct_types.keys())
    values = list(acct_types.values())
    
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.4,
        marker=dict(colors=['#7c3aed', '#06b6d4', '#10b981', '#f59e0b']),
        textinfo='label+value',
        textposition='outside',
        textfont=dict(size=12, color=theme["font"]["color"]),
        hovertemplate='<b>%{label}</b><br>Count: %{value}<br>Percentage: %{percent}<extra></extra>'
    )])
    
    fig.update_layout(
        paper_bgcolor=theme["paper_bgcolor"],
        plot_bgcolor=theme["plot_bgcolor"],
        font=theme["font"],
        showlegend=False,
        margin=dict(t=20, b=40, l=20, r=20),
        height=280,
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_loan_status_by_amount_chart(loans: List[Dict]) -> None:
    """Render loan amounts grouped by status."""
    theme = get_plotly_theme()
    
    if not loans:
        st.info("No loan data available")
        return
    
    # Group loans by status and sum amounts
    status_amounts = {}
    for loan in loans:
        status = loan.get("status", "unknown").title()
        amount = loan.get("amount", 0)
        status_amounts[status] = status_amounts.get(status, 0) + amount
    
    labels = list(status_amounts.keys())
    values = list(status_amounts.values())
    
    # Custom colors
    color_map = {
        "Approved": "#10b981",
        "Active": "#06b6d4",
        "Denied": "#ef4444",
        "Pending": "#f59e0b",
    }
    colors = [color_map.get(label, "#7c3aed") for label in labels]
    
    fig = go.Figure(data=[go.Bar(
        x=labels,
        y=values,
        marker=dict(color=colors),
        text=[f"${v:,.0f}" for v in values],
        textposition='outside',
        textfont=dict(size=12, color=theme["font"]["color"]),
        hovertemplate='<b>%{x}</b><br>Total Amount: $%{y:,.0f}<extra></extra>'
    )])
    
    fig.update_layout(
        paper_bgcolor=theme["paper_bgcolor"],
        plot_bgcolor=theme["plot_bgcolor"],
        font=theme["font"],
        xaxis=dict(
            title="Loan Status",
            gridcolor=theme["gridcolor"],
            showgrid=False,
        ),
        yaxis=dict(
            title="Total Amount ($)",
            gridcolor=theme["gridcolor"],
            showgrid=True,
            tickformat="$,.0f"
        ),
        margin=dict(t=30, b=60, l=80, r=20),
        height=300,
        bargap=0.4,
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_income_vs_loans_chart(customers: Dict, loans: List[Dict]) -> None:
    """Render scatter plot of customer income vs total loan amount."""
    theme = get_plotly_theme()
    
    if not customers or not loans:
        st.info("No data available")
        return
    
    # Calculate total loans per customer
    customer_loans = {}
    for loan in loans:
        cust_id = loan.get("customer_id")
        amount = loan.get("amount", 0)
        customer_loans[cust_id] = customer_loans.get(cust_id, 0) + amount
    
    # Build scatter data
    names = []
    incomes = []
    total_loans = []
    credit_scores = []
    
    for cust_id, customer in customers.items():
        if cust_id in customer_loans:
            names.append(customer.get("name", cust_id))
            incomes.append(customer.get("annual_income", 0))
            total_loans.append(customer_loans[cust_id])
            credit_scores.append(customer.get("credit_score", 500))
    
    if not names:
        st.info("No customer loan data available")
        return
    
    fig = go.Figure(data=[go.Scatter(
        x=incomes,
        y=total_loans,
        mode='markers+text',
        marker=dict(
            size=[max(10, s/20) for s in credit_scores],
            color=credit_scores,
            colorscale='Viridis',
            showscale=True,
            colorbar=dict(title="Credit Score"),
            line=dict(width=1, color='white')
        ),
        text=names,
        textposition='top center',
        textfont=dict(size=10, color=theme["font"]["color"]),
        hovertemplate='<b>%{text}</b><br>Income: $%{x:,.0f}<br>Total Loans: $%{y:,.0f}<extra></extra>'
    )])
    
    fig.update_layout(
        paper_bgcolor=theme["paper_bgcolor"],
        plot_bgcolor=theme["plot_bgcolor"],
        font=theme["font"],
        xaxis=dict(
            title="Annual Income ($)",
            gridcolor=theme["gridcolor"],
            showgrid=True,
            tickformat="$,.0f"
        ),
        yaxis=dict(
            title="Total Loan Amount ($)",
            gridcolor=theme["gridcolor"],
            showgrid=True,
            tickformat="$,.0f"
        ),
        margin=dict(t=30, b=60, l=80, r=20),
        height=400,
    )
    
    st.plotly_chart(fig, use_container_width=True)


def get_dashboard_css() -> str:
    """Get dashboard-specific CSS styles."""
    colors = THEME_COLORS["light"]
    
    return f"""
    <style>
    /* Dashboard Cards */
    .dashboard-card {{
        background: linear-gradient(135deg, {colors['card_bg']} 0%, #ffffff 100%);
        border: 1px solid {colors['panel_border']};
        border-radius: 16px;
        padding: 1.25rem;
        display: flex;
        align-items: center;
        gap: 1rem;
        box-shadow: 0 4px 15px rgba(124, 58, 237, 0.08);
        transition: all 0.3s ease;
        margin-bottom: 0.75rem;
    }}
    
    .dashboard-card:hover {{
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(124, 58, 237, 0.15);
    }}
    
    .dashboard-card.success {{
        border-left: 4px solid #10b981;
    }}
    
    .dashboard-card.danger {{
        border-left: 4px solid #ef4444;
    }}
    
    .dashboard-card.info {{
        border-left: 4px solid #06b6d4;
    }}
    
    .dashboard-card.warning {{
        border-left: 4px solid #f59e0b;
    }}
    
    .card-icon {{
        font-size: 2rem;
        width: 50px;
        height: 50px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: {colors['chip_bg']};
        border-radius: 12px;
    }}
    
    .card-content {{
        flex: 1;
    }}
    
    .card-value {{
        font-size: 1.75rem;
        font-weight: 700;
        color: {colors['text_primary']};
        line-height: 1.2;
    }}
    
    .card-label {{
        font-size: 0.85rem;
        color: {colors['muted_text']};
        font-weight: 500;
    }}
    
    /* Chart containers */
    .chart-container {{
        background: {colors['card_bg']};
        border: 1px solid {colors['panel_border']};
        border-radius: 16px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 4px 15px rgba(124, 58, 237, 0.05);
    }}
    
    .chart-title {{
        font-size: 1.1rem;
        font-weight: 600;
        color: {colors['text_primary']};
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }}
    
    /* Section headers */
    .section-header {{
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin: 1.5rem 0 1rem 0;
        padding-bottom: 0.75rem;
        border-bottom: 2px solid {colors['panel_border']};
    }}
    
    .section-header h3 {{
        margin: 0;
        color: {colors['text_primary']};
        font-size: 1.25rem;
    }}
    
    .section-header p {{
        margin: 0;
        color: {colors['muted_text']};
        font-size: 0.9rem;
    }}
    
    /* Stats grid */
    .stats-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1rem;
        margin-bottom: 1.5rem;
    }}
    
    /* Dashboard header */
    .dashboard-header {{
        text-align: center;
        padding: 1.5rem 0 2rem 0;
        border-bottom: 1px solid {colors['panel_border']};
        margin-bottom: 2rem;
    }}
    
    .dashboard-header h1 {{
        background: linear-gradient(95deg, {colors['accent']} 0%, #06b6d4 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-size: 2.2rem;
        margin-bottom: 0.5rem;
    }}
    
    .dashboard-header p {{
        color: {colors['muted_text']};
        font-size: 1rem;
    }}
    
    /* Tab styling override for dashboard */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 2rem;
    }}
    
    .stTabs [data-baseweb="tab"] {{
        padding: 0.75rem 1.5rem;
        font-weight: 600;
    }}
    </style>
    """


def render_dashboard() -> None:
    """Main function to render the complete dashboard."""
    # Apply dashboard-specific CSS
    st.markdown(get_dashboard_css(), unsafe_allow_html=True)
    
    # Check MongoDB connection status
    mongo_connected = False
    if get_mongo_client is not None:
        client = get_mongo_client()
        mongo_connected = client is not None
    
    # Dashboard header with data source indicator
    data_source_badge = (
        '<span style="background: #10b981; color: white; padding: 0.25rem 0.75rem; border-radius: 999px; font-size: 0.75rem; font-weight: 600; margin-left: 0.5rem;">🗄️ MongoDB</span>'
        if mongo_connected else
        '<span style="background: #f59e0b; color: white; padding: 0.25rem 0.75rem; border-radius: 999px; font-size: 0.75rem; font-weight: 600; margin-left: 0.5rem;">📁 JSON Files</span>'
    )
    
    st.markdown(f"""
        <div class="dashboard-header">
            <h1>📊 Analytics Dashboard</h1>
            <p>Comprehensive overview of customers, loans, and accounts {data_source_badge}</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Load data
    customers, loans, accounts = get_dashboard_data()
    
    # Calculate statistics
    loan_stats = calculate_loan_statistics(loans)
    customer_stats = calculate_customer_statistics(customers, loans)
    account_stats = calculate_account_statistics(accounts)
    
    # Render KPI section
    render_kpi_section(loan_stats, customer_stats, account_stats)
    
    st.markdown("---")
    
    # Charts section
    st.markdown("""
        <div class="section-header">
            <h3>📈 Loan Analytics</h3>
        </div>
    """, unsafe_allow_html=True)
    
    # First row of charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
            <div class="chart-container">
                <div class="chart-title">🥧 Loan Status Distribution</div>
            </div>
        """, unsafe_allow_html=True)
        render_loan_status_chart(loan_stats)
    
    with col2:
        st.markdown("""
            <div class="chart-container">
                <div class="chart-title">👤 Loans by Customer</div>
            </div>
        """, unsafe_allow_html=True)
        render_loans_by_customer_chart(loans, customers)
    
    # Second row of charts
    col3, col4 = st.columns(2)
    
    with col3:
        st.markdown("""
            <div class="chart-container">
                <div class="chart-title">💵 Loan Amount Distribution</div>
            </div>
        """, unsafe_allow_html=True)
        render_loan_amounts_chart(loans)
    
    with col4:
        st.markdown("""
            <div class="chart-container">
                <div class="chart-title">📊 Total Amount by Status</div>
            </div>
        """, unsafe_allow_html=True)
        render_loan_status_by_amount_chart(loans)
    
    st.markdown("---")
    
    # Customer section
    st.markdown("""
        <div class="section-header">
            <h3>👥 Customer Analytics</h3>
        </div>
    """, unsafe_allow_html=True)
    
    col5, col6 = st.columns(2)
    
    with col5:
        st.markdown("""
            <div class="chart-container">
                <div class="chart-title">💼 Employment Status</div>
            </div>
        """, unsafe_allow_html=True)
        render_employment_chart(customer_stats)
    
    with col6:
        st.markdown("""
            <div class="chart-container">
                <div class="chart-title">📈 Credit Score Distribution</div>
            </div>
        """, unsafe_allow_html=True)
        render_credit_score_distribution(customers)
    
    # Income vs Loans scatter plot
    st.markdown("""
        <div class="chart-container">
            <div class="chart-title">💰 Income vs Total Loan Amount (bubble size = credit score)</div>
        </div>
    """, unsafe_allow_html=True)
    render_income_vs_loans_chart(customers, loans)
    
    st.markdown("---")
    
    # Account section
    st.markdown("""
        <div class="section-header">
            <h3>🏦 Account Analytics</h3>
        </div>
    """, unsafe_allow_html=True)
    
    col7, col8 = st.columns([1, 2])
    
    with col7:
        st.markdown("""
            <div class="chart-container">
                <div class="chart-title">📋 Account Types</div>
            </div>
        """, unsafe_allow_html=True)
        render_account_types_chart(account_stats)
    
    with col8:
        # Summary statistics card
        st.markdown(f"""
            <div class="chart-container">
                <div class="chart-title">📊 Summary Statistics</div>
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem; margin-top: 1rem;">
                    <div style="padding: 1rem; background: rgba(124, 58, 237, 0.05); border-radius: 12px;">
                        <div style="font-size: 0.85rem; color: #6b7280;">Avg. Credit Score</div>
                        <div style="font-size: 1.5rem; font-weight: 700; color: #0f172a;">{customer_stats['avg_credit_score']:.0f}</div>
                    </div>
                    <div style="padding: 1rem; background: rgba(124, 58, 237, 0.05); border-radius: 12px;">
                        <div style="font-size: 0.85rem; color: #6b7280;">Avg. Annual Income</div>
                        <div style="font-size: 1.5rem; font-weight: 700; color: #0f172a;">${customer_stats['avg_income']:,.0f}</div>
                    </div>
                    <div style="padding: 1rem; background: rgba(124, 58, 237, 0.05); border-radius: 12px;">
                        <div style="font-size: 0.85rem; color: #6b7280;">Avg. Loan Amount</div>
                        <div style="font-size: 1.5rem; font-weight: 700; color: #0f172a;">${loan_stats['avg_loan_amount']:,.0f}</div>
                    </div>
                    <div style="padding: 1rem; background: rgba(124, 58, 237, 0.05); border-radius: 12px;">
                        <div style="font-size: 0.85rem; color: #6b7280;">Total Account Balance</div>
                        <div style="font-size: 1.5rem; font-weight: 700; color: #0f172a;">${account_stats['total_balance']:,.2f}</div>
                    </div>
                    <div style="padding: 1rem; background: rgba(239, 68, 68, 0.05); border-radius: 12px;">
                        <div style="font-size: 0.85rem; color: #6b7280;">Customers with Risk Flags</div>
                        <div style="font-size: 1.5rem; font-weight: 700; color: #ef4444;">{customer_stats['with_risk_flags']}</div>
                    </div>
                    <div style="padding: 1rem; background: rgba(16, 185, 129, 0.05); border-radius: 12px;">
                        <div style="font-size: 0.85rem; color: #6b7280;">Loan Approval Rate</div>
                        <div style="font-size: 1.5rem; font-weight: 700; color: #10b981;">{(loan_stats['approved'] / loan_stats['total'] * 100) if loan_stats['total'] > 0 else 0:.1f}%</div>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    # Refresh button
    st.markdown("---")
    col_refresh, col_spacer = st.columns([1, 3])
    with col_refresh:
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.rerun()
