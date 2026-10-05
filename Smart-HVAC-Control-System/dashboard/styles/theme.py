"""
Dashboard Theme Configuration
==============================

Premium dark theme with modern aesthetics for the HVAC monitoring dashboard.
"""

# Color palette
COLORS = {
    # Primary palette
    "bg_primary": "#0a0e1a",
    "bg_secondary": "#111827",
    "bg_card": "#1a1f35",
    "bg_card_hover": "#222842",

    # Accent colors
    "accent_blue": "#3b82f6",
    "accent_cyan": "#06b6d4",
    "accent_emerald": "#10b981",
    "accent_amber": "#f59e0b",
    "accent_red": "#ef4444",
    "accent_purple": "#8b5cf6",

    # Text
    "text_primary": "#f1f5f9",
    "text_secondary": "#94a3b8",
    "text_muted": "#64748b",

    # Comfort zone colors
    "zone_cold": "#3b82f6",       # Blue — heating needed
    "zone_comfort": "#10b981",     # Green — comfortable
    "zone_hot": "#ef4444",         # Red — cooling needed
    "zone_deadband": "#1e293b",    # Dark — idle zone

    # HVAC state colors
    "hvac_cooling": "#06b6d4",
    "hvac_heating": "#f97316",
    "hvac_idle": "#4b5563",
    "hvac_off": "#1e293b",

    # Gradients
    "gradient_cool": ["#06b6d4", "#3b82f6"],
    "gradient_warm": ["#f97316", "#ef4444"],
    "gradient_energy": ["#10b981", "#f59e0b", "#ef4444"],
}

# Plotly layout template
PLOTLY_LAYOUT = {
    "paper_bgcolor": COLORS["bg_primary"],
    "plot_bgcolor": COLORS["bg_secondary"],
    "font": {
        "family": "Inter, system-ui, sans-serif",
        "color": COLORS["text_primary"],
        "size": 13,
    },
    "xaxis": {
        "gridcolor": "#1e293b",
        "zerolinecolor": "#334155",
    },
    "yaxis": {
        "gridcolor": "#1e293b",
        "zerolinecolor": "#334155",
    },
    "margin": {"l": 60, "r": 20, "t": 40, "b": 40},
    "legend": {
        "bgcolor": "rgba(0,0,0,0)",
        "font": {"color": COLORS["text_secondary"]},
    },
}

# Streamlit page config
PAGE_CONFIG = {
    "page_title": "Smart HVAC Control System",
    "page_icon": "🌡️",
    "layout": "wide",
    "initial_sidebar_state": "expanded",
}

# CSS for premium styling
CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* Main app background */
    .stApp {
        background: linear-gradient(135deg, #0a0e1a 0%, #111827 50%, #0f172a 100%);
        font-family: 'Inter', system-ui, sans-serif;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #111827 0%, #0a0e1a 100%);
        border-right: 1px solid #1e293b;
    }

    /* Metric cards */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #1a1f35 0%, #111827 100%);
        border: 1px solid #1e293b;
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.3);
    }

    [data-testid="stMetricLabel"] {
        color: #94a3b8 !important;
        font-weight: 500;
    }

    [data-testid="stMetricValue"] {
        color: #f1f5f9 !important;
        font-weight: 700;
    }

    /* Headers */
    h1, h2, h3 {
        color: #f1f5f9 !important;
        font-weight: 600 !important;
    }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        padding: 8px 24px;
        transition: all 0.2s ease;
    }

    .stButton > button:hover {
        background: linear-gradient(135deg, #60a5fa 0%, #3b82f6 100%);
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(59,130,246,0.4);
    }

    /* Slider */
    .stSlider > div > div {
        color: #94a3b8;
    }

    /* Selectbox */
    .stSelectbox > div > div {
        background: #1a1f35;
        border-color: #334155;
        color: #f1f5f9;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background: #111827;
        border-radius: 12px;
        padding: 4px;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        color: #94a3b8;
        font-weight: 500;
    }

    .stTabs [aria-selected="true"] {
        background: #3b82f6 !important;
        color: white !important;
    }

    /* Divider */
    hr {
        border-color: #1e293b;
    }

    /* Scrollbar */
    ::-webkit-scrollbar {
        width: 6px;
    }
    ::-webkit-scrollbar-track {
        background: #0a0e1a;
    }
    ::-webkit-scrollbar-thumb {
        background: #334155;
        border-radius: 3px;
    }
</style>
"""
