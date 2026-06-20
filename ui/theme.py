"""
Visual theme for CareerPilot AI.

Streamlit's component styling is limited, so we inject a single CSS block
that establishes the design system: palette, card styles, badges, and the
"momentum ring" match-score indicator used throughout the app.

Design tokens (see frontend-design skill guidance):
  Background:    #F7F7FB (soft off-white)
  Surface:       #FFFFFF
  Primary:       #1A1B3A (deep indigo navy)
  Accent:        #6C5CE7 (electric violet)
  Momentum:      #FFB648 (warm amber - match score signal)
  Success:       #2ECC71
  Danger:        #FF6B6B
  Muted text:    #6B7280
"""
from __future__ import annotations

import streamlit as st

COLORS = {
    "bg": "#F7F7FB",
    "surface": "#FFFFFF",
    "primary": "#1A1B3A",
    "accent": "#6C5CE7",
    "accent_light": "#EDE9FE",
    "momentum": "#FFB648",
    "success": "#2ECC71",
    "success_light": "#E6F9EE",
    "danger": "#FF6B6B",
    "danger_light": "#FFEDED",
    "muted": "#6B7280",
    "border": "#E8E8F0",
}

_CSS = f"""
<style>
    .stApp {{
        background-color: {COLORS['bg']};
    }}

    section[data-testid="stSidebar"] {{
        background-color: {COLORS['primary']};
    }}
    section[data-testid="stSidebar"] * {{
        color: #F1F0FA !important;
    }}
    section[data-testid="stSidebar"] .stRadio label:hover {{
        color: {COLORS['momentum']} !important;
    }}

    h1, h2, h3 {{
        color: {COLORS['primary']};
        font-weight: 700;
    }}

    /* Stat card */
    .cp-stat-card {{
        background: {COLORS['surface']};
        border: 1px solid {COLORS['border']};
        border-radius: 14px;
        padding: 20px 22px;
        box-shadow: 0 1px 3px rgba(26,27,58,0.06);
    }}
    .cp-stat-label {{
        font-size: 13px;
        font-weight: 600;
        color: {COLORS['muted']};
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-bottom: 6px;
    }}
    .cp-stat-value {{
        font-size: 32px;
        font-weight: 800;
        color: {COLORS['primary']};
        line-height: 1.1;
    }}
    .cp-stat-delta {{
        font-size: 13px;
        font-weight: 600;
        margin-top: 4px;
    }}
    .cp-stat-delta.positive {{ color: {COLORS['success']}; }}
    .cp-stat-delta.neutral {{ color: {COLORS['muted']}; }}

    /* Job card */
    .cp-job-card {{
        background: {COLORS['surface']};
        border: 1px solid {COLORS['border']};
        border-radius: 14px;
        padding: 18px 20px;
        margin-bottom: 12px;
        box-shadow: 0 1px 3px rgba(26,27,58,0.05);
    }}
    .cp-job-role {{
        font-size: 16px;
        font-weight: 700;
        color: {COLORS['primary']};
        margin-bottom: 2px;
    }}
    .cp-job-company {{
        font-size: 14px;
        color: {COLORS['muted']};
        margin-bottom: 8px;
    }}

    /* Badges */
    .cp-badge {{
        display: inline-block;
        padding: 3px 10px;
        border-radius: 100px;
        font-size: 12px;
        font-weight: 600;
        margin-right: 6px;
        margin-bottom: 4px;
    }}
    .cp-badge-skill {{
        background: {COLORS['accent_light']};
        color: {COLORS['accent']};
    }}
    .cp-badge-status-applied {{ background: #EAF1FF; color: #2563EB; }}
    .cp-badge-status-interview {{ background: #FFF6E0; color: #B45309; }}
    .cp-badge-status-rejected {{ background: {COLORS['danger_light']}; color: #C0392B; }}
    .cp-badge-status-offer {{ background: {COLORS['success_light']}; color: #1E8449; }}

    /* Momentum ring (match score) */
    .cp-ring-wrap {{
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
    }}
    .cp-ring-score {{
        font-size: 20px;
        font-weight: 800;
    }}
    .cp-ring-label {{
        font-size: 11px;
        color: {COLORS['muted']};
        text-transform: uppercase;
        letter-spacing: 0.03em;
    }}

    div[data-testid="stMetricValue"] {{
        color: {COLORS['primary']};
    }}

    .cp-section-divider {{
        border: none;
        border-top: 1px solid {COLORS['border']};
        margin: 24px 0;
    }}
</style>
"""


def inject_theme() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def match_color(score: int) -> str:
    if score >= 70:
        return COLORS["success"]
    if score >= 40:
        return COLORS["momentum"]
    return COLORS["danger"]
