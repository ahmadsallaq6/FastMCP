"""
Configuration settings for the Streamlit frontend.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ======================
# Server Configuration
# ======================

DEFAULT_SERVER_URL = "http://localhost:8001"

# ======================
# Azure OpenAI Configuration
# ======================

AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_GPT_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_GPT_DEPLOYMENT_NAME", "gpt-4.1")

# ======================
# Tool Approval Configuration
# ======================

# Tools that require user approval before execution
# Match by substring in tool name (case-insensitive)
TOOLS_REQUIRING_APPROVAL_PATTERNS = [
    "apply_for_loan_loans_apply_post",
    "send_custom_email"
]


def tool_requires_approval(tool_name: str) -> bool:
    """Check if a tool requires user approval before execution.
    
    Args:
        tool_name: The name of the tool to check
        
    Returns:
        True if the tool requires approval, False otherwise
    """
    tool_name_lower = tool_name.lower()
    return any(pattern in tool_name_lower for pattern in TOOLS_REQUIRING_APPROVAL_PATTERNS)


# ======================
# UI Configuration
# ======================

PAGE_CONFIG = {
    "page_title": "Loans Assistant ChatBot 🏦",
    "page_icon": "🏦",
    "layout": "centered",
    "initial_sidebar_state": "expanded"
}

# Theme colors

THEME_COLORS = {
    "dark": {
        "bg_primary": "#050316",
        "bg_secondary": "#130a37",
        "bg_sidebar": "rgba(5, 3, 22, 0.85)",
        "sidebar_tint": "rgba(124, 58, 237, 0.22)",
        "content_panel_bg": "rgba(10, 7, 25, 0.9)",
        "panel_border": "rgba(255, 255, 255, 0.08)",
        "panel_shadow": "0 30px 80px rgba(0, 0, 0, 0.6)",
        "sidebar_shadow": "0 20px 60px rgba(2, 1, 15, 0.75)",
        "text_primary": "#f5f3ff",
        "text_secondary": "#c7c4e2",
        "muted_text": "#98a0c1",
        "accent": "#c084fc",
        "accent_hover": "#a855f7",
        "focus_border": "#f9f5ff",
        "border": "rgba(255, 255, 255, 0.08)",
        "card_bg": "rgba(7, 4, 20, 0.9)",
        "success": "#34d399",
        "danger": "#fb7185",
        "warning": "#fbbf24",
        "info_bg": "rgba(56, 189, 248, 0.12)",
        "user_msg_bg": "#7856ff",
        "bot_msg_bg": "rgba(3, 6, 23, 0.7)",
        "input_bg": "rgba(5, 3, 22, 0.9)",
        "input_border": "rgba(255, 255, 255, 0.15)",
        "scrollbar_track": "rgba(4, 3, 18, 0.9)",
        "scrollbar_thumb": "rgba(124, 58, 237, 0.7)",
        "chip_bg": "rgba(255, 255, 255, 0.08)",
        "primary_button_bg": "#ffffff",
        "primary_button_text": "#0f172a",
        "primary_button_shadow": "0 8px 25px rgba(255, 255, 255, 0.25)",
        "primary_button_hover_bg": "#f4f2ff",
        "primary_button_hover_text": "#0f172a",
        "primary_button_hover_shadow": "0 10px 30px rgba(255, 255, 255, 0.35)",
        "approval_button_text": "#020617",
    },
    "light": {
        "bg_primary": "#f4f6ff",
        "bg_secondary": "#ffffff",
        "bg_sidebar": "rgba(255, 255, 255, 0.9)",
        "sidebar_tint": "rgba(124, 58, 237, 0.12)",
        "content_panel_bg": "#ffffff",
        "panel_border": "rgba(15, 23, 42, 0.08)",
        "panel_shadow": "0 25px 60px rgba(15, 23, 42, 0.08)",
        "sidebar_shadow": "0 20px 45px rgba(15, 23, 42, 0.08)",
        "text_primary": "#0f172a",
        "text_secondary": "#475569",
        "muted_text": "#6b7280",
        "accent": "#7c3aed",
        "accent_hover": "#6d28d9",
        "focus_border": "#4c1d95",
        "border": "rgba(15, 23, 42, 0.08)",
        "card_bg": "#f8f7ff",
        "success": "#10b981",
        "danger": "#ef4444",
        "warning": "#f59e0b",
        "info_bg": "#eef2ff",
        "user_msg_bg": "#7c3aed",
        "bot_msg_bg": "#f3f4f6",
        "input_bg": "#f8f7ff",
        "input_border": "rgba(124, 58, 237, 0.25)",
        "scrollbar_track": "#ebe7ff",
        "scrollbar_thumb": "#c4bcff",
        "chip_bg": "rgba(124, 58, 237, 0.08)",
        "primary_button_bg": "linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%)",
        "primary_button_text": "#ffffff",
        "primary_button_shadow": "0 4px 15px rgba(124, 58, 237, 0.35)",
        "primary_button_hover_bg": "linear-gradient(135deg, #6d28d9 0%, #5b21b6 100%)",
        "primary_button_hover_text": "#ffffff",
        "primary_button_hover_shadow": "0 8px 25px rgba(124, 58, 237, 0.45)",
        "approval_button_text": "#111827",
    }
}

def get_custom_css(theme: str = "dark") -> str:
    """Generate custom CSS based on the selected theme.
    
    Args:
        theme: Either 'dark' or 'light'
        
    Returns:
        CSS string with theme-specific styles
    """
    colors = THEME_COLORS.get(theme, THEME_COLORS["dark"])
    background_gradient = (
        f"radial-gradient(circle at 15% 20%, {colors['bg_secondary']} 0%, "
        f"{colors['bg_primary']} 55%, {colors['bg_primary']} 100%)"
    )
    approval_button_text = colors.get("approval_button_text", colors["primary_button_text"])

    return f"""
    <style>
    /* ===== Base Styles ===== */
    html, body, [data-testid="stAppViewContainer"] {{
        margin: 0;
        padding: 0;
        min-height: 100vh;
        background: {background_gradient};
    }}
    
    .stApp {{
        background: transparent;
    }}
    
    [data-testid="stAppViewContainer"] > .main {{
        padding-top: 1rem;
        padding-bottom: 2.5rem;
    }}

    [data-testid="stHeader"] {{
        background: transparent !important;
        height: 3.5rem;
        padding-top: 0.25rem;
        border-bottom: none;
    }}

    [data-testid="stHeader"] > div {{
        background: transparent !important;
        box-shadow: none !important;
    }}

    [data-testid="stBottom"] {{
        background: transparent !important;
        box-shadow: none !important;
        border-top: none !important;
        padding: 0 !important;
    }}

    [data-testid="stBottom"] > div {{
        background: transparent !important;
    }}

    [data-testid="stChatInputContainer"] {{
        background: transparent !important;
    }}
    
    /* ===== Main Container ===== */
    .block-container {{
        padding: 2.5rem 3rem 2rem 3rem;
        max-width: 980px;
        margin-left: auto;
        margin-right: auto;
        background: {colors['content_panel_bg']};
        border-radius: 30px;
        border: 1px solid {colors['panel_border']};
        box-shadow: {colors['panel_shadow']};
        backdrop-filter: blur(20px);
    }}
    
    /* ===== Sidebar Styles ===== */
    [data-testid="stSidebar"] {{
        background: transparent;
        border-right: none;
    }}
    
    [data-testid="stSidebar"] > div:first-child {{
        padding: 1.5rem 1rem 2rem;
    }}
    
    [data-testid="stSidebar"] section[data-testid="stSidebarContent"] {{
        background: linear-gradient(165deg, {colors['bg_sidebar']} 0%, {colors['sidebar_tint']} 100%);
        border-radius: 28px;
        padding: 1.5rem 1.25rem 2rem;
        border: 1px solid {colors['panel_border']};
        box-shadow: {colors['sidebar_shadow']};
    }}
    
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{
        gap: 1rem;
    }}
    
    [data-testid="stSidebar"] .stMarkdown {{
        color: {colors['text_primary']};
    }}
    
    [data-testid="stSidebar"] .stCaption {{
        color: {colors['text_secondary']};
    }}

    .settings-title {{
        font-size: 1.25rem;
        font-weight: 700;
        color: {colors['text_primary']};
        margin: 0;
        display: flex;
        align-items: center;
        height: 100%;
    }}

    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"]:first-of-type > div[data-testid="column"]:nth-child(2) > div {{
        display: flex;
        align-items: center;
        justify-content: flex-end;
        padding-top: 0;
        padding-bottom: 0;
    }}

    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"]:first-of-type button {{
        width: 42px;
        height: 42px;
        border-radius: 999px;
        padding: 0;
        font-size: 1.15rem;
        background: {colors['chip_bg']};
        border: 1px solid {colors['panel_border']};
        color: {colors['text_primary']};
        box-shadow: none;
    }}

    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"]:first-of-type button:hover {{
        border-color: {colors['accent']};
        color: {colors['accent']};
        background: {colors['chip_bg']};
    }}

    /* ===== Approval Dialog ===== */
    .approval-banner {{
        display: flex;
        gap: 0.75rem;
        align-items: center;
        background: linear-gradient(135deg, rgba(250, 204, 21, 0.25) 0%, rgba(250, 204, 21, 0.08) 100%);
        border: 1px solid rgba(250, 204, 21, 0.35);
        border-radius: 16px;
        padding: 1rem 1.25rem;
        margin: 1rem 0 0.75rem;
        box-shadow: 0 15px 45px rgba(250, 204, 21, 0.18);
    }}

    .approval-banner__icon {{
        font-size: 1.5rem;
    }}

    .approval-banner__title {{
        font-weight: 700;
        color: {colors['text_primary']};
        font-size: 1rem;
    }}

    .approval-banner__subtitle {{
        color: {colors['text_secondary']};
        font-size: 0.9rem;
    }}

    .approval-json {{
        background: {colors['card_bg']};
        border: 1px solid {colors['panel_border']};
        border-radius: 16px;
        padding: 1.1rem 1.25rem;
        box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.15);
        margin-top: 0.5rem;
    }}

    .approval-metadata {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 0.75rem;
        margin: 0.5rem 0 1rem;
    }}

    .approval-chip {{
        background: {colors['card_bg']};
        border: 1px solid {colors['panel_border']};
        border-radius: 14px;
        padding: 0.65rem 0.85rem;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
    }}

    .approval-chip__label {{
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: {colors['muted_text']};
        margin-bottom: 0.15rem;
        font-weight: 600;
    }}

    .approval-chip__value {{
        font-size: 0.95rem;
        font-weight: 600;
        color: {colors['text_primary']};
        word-break: break-word;
    }}

    .approval-body {{
        background: {colors['card_bg']};
        border: 1px solid {colors['panel_border']};
        border-radius: 16px;
        padding: 1.1rem 1.25rem;
        margin-bottom: 1rem;
        line-height: 1.7;
    }}

    .approval-body__label {{
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: {colors['muted_text']};
        margin-bottom: 0.45rem;
        font-weight: 600;
    }}

    .approval-body p {{
        margin: 0 0 0.6rem;
        color: {colors['text_primary']};
    }}

    .approval-body p:last-child {{
        margin-bottom: 0;
    }}

    .approval-json__label {{
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: {colors['muted_text']};
        margin-bottom: 0.55rem;
        font-weight: 600;
    }}

    .approval-json pre {{
        margin: 0;
        color: {colors['text_primary']};
        background: transparent !important;
        font-size: 0.95rem;
    }}

    /* Tooltip styling */
    [data-baseweb="tooltip"] {{
        background: transparent !important;
    }}

    [data-baseweb="tooltip"] > div {{
        background-color: {colors['card_bg']} !important;
        color: {colors['text_primary']} !important;
        border: 1px solid {colors['panel_border']} !important;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.35) !important;
        font-weight: 600;
    }}

    [data-baseweb="tooltip"] > div > div {{
        background-color: transparent !important;
        color: {colors['text_primary']} !important;
    }}

    [data-baseweb="tooltip"]::after,
    [data-baseweb="tooltip"] > div::after {{
        background-color: {colors['card_bg']} !important;
        border: 1px solid {colors['panel_border']} !important;
    }}
    
    /* ===== Typography ===== */
    h1, h2, h3, h4, h5, h6 {{
        color: {colors['text_primary']} !important;
        font-weight: 700;
        letter-spacing: -0.5px;
    }}
    
    p, span, label {{
        color: {colors['text_primary']};
        line-height: 1.6;
    }}
    
    .stMarkdown {{
        color: {colors['text_primary']};
    }}
    
    /* ===== Main Title ===== */
    .hero-header {{
        text-align: center;
        margin-bottom: 2.5rem;
    }}
    
    .hero-chip {{
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        padding: 0.4rem 0.9rem;
        border-radius: 999px;
        font-size: 0.8rem;
        font-weight: 600;
        background: {colors['chip_bg']};
        color: {colors['accent']};
        border: 1px solid {colors['panel_border']};
        margin-bottom: 0.9rem;
    }}

    .hero-header h1 {{
        background: linear-gradient(95deg, {colors['accent']} 0%, #06b6d4 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-size: 2.7rem;
        margin-bottom: 0.35rem;
    }}

    .hero-header p {{
        color: {colors['muted_text']};
        font-weight: 500;
    }}
    
    /* ===== Chat Messages ===== */
    [data-testid="stChatMessage"] {{
        background: {colors['card_bg']};
        border-radius: 18px;
        padding: 1.35rem 1.4rem;
        margin-bottom: 1rem;
        border: 1px solid {colors['panel_border']};
        box-shadow: 0 20px 45px rgba(0, 0, 0, 0.18);
        backdrop-filter: blur(18px);
    }}
    
    [data-testid="stChatMessage"]:hover {{
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.12);
        transform: translateY(-1px);
        transition: all 0.3s ease;
    }}
    
    [data-testid="stChatMessage"] [data-testid*="user"] {{
        background: linear-gradient(135deg, {colors['user_msg_bg']} 0%, #9d4edd 100%);
        border: none;
        color: white;
    }}
    
    [data-testid="stChatMessage"] [data-testid*="user"] p {{
        color: white;
    }}
    
    /* ===== Chat Container ===== */
    .stChatMessageContainer {{
        gap: 0.75rem;
    }}
    
    /* ===== Chat Input ===== */
    .stChatInputContainer {{
        padding: 1.5rem 0 0 0;
        background: {colors['content_panel_bg']};
        position: sticky;
        bottom: 1rem;
        z-index: 20;
        backdrop-filter: blur(18px);
        border-top: 1px solid {colors['panel_border']};
        margin-top: 1rem;
        box-shadow: 0 -20px 40px rgba(0, 0, 0, 0.15);
    }}
    
    div[data-testid="stChatInput"] {{
        border: 2px solid {colors['input_border']} !important;
        border-radius: 18px !important;
        background-color: {colors['input_bg']} !important;
        color: {colors['text_primary']} !important;
        transition: all 0.3s ease !important;
        box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.08);
    }}

    div[data-testid="stChatInput"] > div {{
        background: {colors['input_bg']} !important;
        border-radius: 18px !important;
        padding: 0 !important;
    }}

    div[data-testid="stChatInput"] > div > div {{
        background: transparent !important;
        border-radius: 18px !important;
    }}
    
    div[data-testid="stChatInput"]:focus-within {{
        border-color: {colors['focus_border']} !important;
        box-shadow: 0 0 0 3px rgba(124, 58, 237, 0.25) !important;
    }}
    
    textarea[data-testid="stChatInputTextArea"],
    div[data-testid="stChatInput"] textarea {{
        color: {colors['text_primary']} !important;
        font-size: 0.95rem;
        background-color: {colors['input_bg']} !important;
        border-radius: 14px;
        padding: 0.85rem 1.1rem !important;
        caret-color: {colors['text_primary']} !important;
        border: none !important;
        outline: none !important;
    }}

    textarea[data-testid="stChatInputTextArea"]::placeholder,
    div[data-testid="stChatInput"] textarea::placeholder {{
        color: {colors['muted_text']} !important;
    }}
    
    /* ===== Buttons ===== */
    .stButton > button {{
        background: {colors['primary_button_bg']};
        color: {colors['primary_button_text']} !important;
        border: none;
        border-radius: 10px;
        padding: 0.65rem 1.5rem;
        font-weight: 600;
        font-size: 0.95rem;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: {colors['primary_button_shadow']};
        cursor: pointer;
    }}
    
    .stButton > button:hover {{
        transform: translateY(-3px);
        background: {colors['primary_button_hover_bg']};
        color: {colors['primary_button_hover_text']} !important;
        box-shadow: {colors['primary_button_hover_shadow']};
    }}
    
    .stButton > button:active {{
        transform: translateY(-1px);
    }}

    .approve-button-wrapper .stButton > button {{
        color: {approval_button_text};
    }}

    button[data-testid="baseButton-theme_toggle"] {{
        font-size: 1.1rem;
        padding: 0.35rem 0.65rem;
        margin: 0;
        display: inline-flex;
        align-items: center;
        justify-content: center;
    }}
    
    /* Secondary buttons */
    .stButton > button[kind="secondary"] {{
        background: transparent;
        border: 2px solid {colors['border']};
        color: {colors['text_primary']};
        box-shadow: none;
    }}
    
    .stButton > button[kind="secondary"]:hover {{
        border-color: {colors['accent']};
        background: rgba(124, 58, 237, 0.08);
        transform: translateY(-2px);
    }}
    
    /* ===== Text Input ===== */
    .stTextInput > div > div > input {{
        background-color: {colors['input_bg']} !important;
        border: 2px solid {colors['border']} !important;
        border-radius: 10px !important;
        color: {colors['text_primary']} !important;
        transition: all 0.3s ease !important;
        font-size: 0.95rem;
        padding: 0.65rem 1rem !important;
    }}
    
    .stTextInput > div > div > input:focus {{
        border-color: {colors['accent']} !important;
        box-shadow: 0 0 0 3px rgba(124, 58, 237, 0.15) !important;
    }}

    .stTextInput > div > div > input:disabled {{
        color: {colors['text_primary']} !important;
        background-color: {colors['input_bg']} !important;
        opacity: 0.6 !important;
        -webkit-text-fill-color: {colors['text_primary']} !important;
    }}

    /* ===== Text Area ===== */
    .stTextArea > div > div > textarea {{
        background-color: {colors['input_bg']} !important;
        border: 2px solid {colors['border']} !important;
        border-radius: 10px !important;
        color: {colors['text_primary']} !important;
        font-size: 0.95rem;
    }}

    .stTextArea > div > div > textarea:focus {{
        border-color: {colors['accent']} !important;
        box-shadow: 0 0 0 3px rgba(124, 58, 237, 0.15) !important;
    }}

    .stTextArea > div > div > textarea:disabled {{
        color: {colors['text_primary']} !important;
        background-color: {colors['input_bg']} !important;
        opacity: 0.6 !important;
        -webkit-text-fill-color: {colors['text_primary']} !important;
    }}
    
    /* ===== Select Box ===== */
    .stSelectbox > div > div {{
        background-color: {colors['input_bg']} !important;
        border: 2px solid {colors['border']} !important;
        border-radius: 10px !important;
        color: {colors['text_primary']} !important;
    }}
    
    .stSelectbox > div > div:focus-within {{
        border-color: {colors['accent']} !important;
    }}
    
    /* ===== Info/Alert Boxes ===== */
    .stAlert {{
        background: linear-gradient(135deg, {colors['info_bg']} 0%, rgba(124, 58, 237, 0.05) 100%) !important;
        border: 1px solid {colors['border']} !important;
        border-radius: 12px !important;
        border-left: 4px solid {colors['accent']} !important;
        padding: 1rem 1.25rem !important;
    }}
    
    [data-testid="stAlert"] {{
        border-radius: 12px;
    }}
    
    /* ===== JSON Display ===== */
    .stJson {{
        background-color: {colors['card_bg']} !important;
        border-radius: 10px !important;
        border: 1px solid {colors['border']} !important;
        padding: 1rem !important;
    }}
    
    /* ===== Code Blocks ===== */
    .stCodeBlock {{
        border-radius: 10px !important;
    }}
    
    pre {{
        background-color: {colors['card_bg']} !important;
        border-radius: 10px !important;
        border: 1px solid {colors['border']} !important;
        padding: 1rem !important;
    }}
    
    code {{
        background-color: {colors['card_bg']} !important;
        border-radius: 4px !important;
        padding: 0.2rem 0.6rem !important;
        color: {colors['accent']} !important;
    }}
    
    /* ===== Divider ===== */
    hr {{
        border-color: {colors['border']};
        opacity: 0.3;
        margin: 1.5rem 0;
    }}
    
    /* ===== Status Widget ===== */
    [data-testid="stStatusWidget"] {{
        background-color: {colors['card_bg']};
        border-radius: 10px;
        border: 1px solid {colors['border']};
    }}
    
    /* ===== Expander ===== */
    .streamlit-expanderHeader {{
        background-color: {colors['card_bg']};
        border-radius: 10px;
        border: 1px solid {colors['border']};
    }}
    
    .streamlit-expanderHeader:hover {{
        background-color: rgba(124, 58, 237, 0.08);
    }}
    
    /* ===== Scrollbar ===== */
    ::-webkit-scrollbar {{
        width: 10px;
        height: 10px;
    }}
    
    ::-webkit-scrollbar-track {{
        background: {colors['scrollbar_track']};
        border-radius: 5px;
    }}
    
    ::-webkit-scrollbar-thumb {{
        background: linear-gradient(180deg, {colors['scrollbar_thumb']} 0%, {colors['accent']} 100%);
        border-radius: 5px;
    }}
    
    ::-webkit-scrollbar-thumb:hover {{
        background: {colors['accent']};
    }}
    
    /* ===== Sidebar History Buttons ===== */
    [data-testid="stSidebar"] .stButton > button {{
        background: {colors['chip_bg']};
        border: 1px solid {colors['panel_border']};
        color: {colors['text_primary']};
        text-align: left;
        box-shadow: none;
        padding: 0.6rem 0.9rem;
        font-size: 0.85rem;
        width: 100%;
        border-radius: 14px;
    }}
    
    [data-testid="stSidebar"] .stButton > button:hover {{
        background: transparent;
        border-color: {colors['accent']};
        color: {colors['accent']};
        transform: none;
    }}
    
    /* ===== Animation ===== */
    @keyframes fadeIn {{
        from {{ 
            opacity: 0; 
            transform: translateY(12px); 
        }}
        to {{ 
            opacity: 1; 
            transform: translateY(0); 
        }}
    }}
    
    [data-testid="stChatMessage"] {{
        animation: fadeIn 0.4s ease-out;
    }}
    
    /* ===== Loading Spinner ===== */
    .stSpinner > div {{
        border-top-color: {colors['accent']};
    }}
    
    /* ===== General Hover Effects ===== */
    button {{
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }}
    
    input, select, textarea {{
        transition: all 0.3s ease;
    }}
    
    /* ===== Container Padding ===== */
    .stVerticalBlock {{
        gap: 1.5rem;
    }}

    /* ===== Responsive Layout Adjustments ===== */
    @media (max-width: 768px) {{
        .block-container {{
            max-width: 100%;
            padding: 1.5rem 1.25rem 1.75rem;
            margin: 0.75rem;
            border-radius: 22px;
        }}
        .hero-header h1 {{
            font-size: 2.1rem;
        }}
        .hero-header p {{
            font-size: 0.95rem;
        }}
        .hero-chip {{
            font-size: 0.72rem;
        }}
        .stMarkdown, p, span, label {{
            font-size: 0.95rem;
        }}
        .stChatInput textarea {{
            font-size: 0.9rem;
        }}
    }}
    </style>
    """

# Default CSS (for backward compatibility)
CUSTOM_CSS = get_custom_css("dark")

# ======================
# System Prompts
# ======================

SYSTEM_PROMPT = (
    "System Instructions: You are a helpful loan assistant. "
    "You have access to various tools to help customers. "
    "When the user asks a question requesting information or knowledge, "
    "use the appropriate search tool to find relevant information and provide accurate answers. "
    "Loan approvals and rejections are ultimately decided by the human user: "
    "if the user explicitly approves a loan request you must treat it as approved and may not overturn it, "
    "and if the user rejects a request you must treat it as rejected with no reversals."
)
