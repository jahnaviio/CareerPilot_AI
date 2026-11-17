"""CareerPilot design system: one set of tokens, one stylesheet, used by every page.

Tokens: deep-navy sidebar (#0B1437), light workspace (#F6F7FB), violet accent (#5B4FE5), blue secondary (#2F6BFF),
semantic green/amber/red for evidence states. Spacing scale 4/8/12/16/24/32. Radius 12 (cards) / 999 (chips)."""
from __future__ import annotations

import streamlit as st

TOKENS = {"navy": "#0B1437", "navy2": "#141E4A", "bg": "#F6F7FB", "surface": "#FFFFFF", "ink": "#0F172A", "muted": "#64748B",
          "line": "#E6E8F0", "accent": "#5B4FE5", "accent_soft": "#EEEDFE", "blue": "#2F6BFF", "blue_soft": "#E8F0FF",
          "green": "#12805C", "green_soft": "#E4F6EE", "amber": "#9A6700", "amber_soft": "#FFF4D6", "red": "#B42318", "red_soft": "#FDECEA"}

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"], .stApp {{ font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif; color: {TOKENS['ink']}; }}
.stApp {{ background: {TOKENS['bg']}; }}
#MainMenu, footer, [data-testid="stToolbar"] {{ visibility: hidden; height: 0; }}
.block-container {{ padding: 2rem 2.5rem 4rem; max-width: 1180px; }}
h1, h2, h3, h4 {{ letter-spacing: -0.015em; color: {TOKENS['ink']}; }}
h1 {{ font-size: 1.75rem; font-weight: 700; margin-bottom: .25rem; }}
h2 {{ font-size: 1.25rem; font-weight: 650; }}
h3 {{ font-size: 1.05rem; font-weight: 650; }}
p, li {{ line-height: 1.55; }}

/* ---------- sidebar ---------- */
[data-testid="stSidebar"] {{ background: {TOKENS['navy']}; border-right: 0; }}
[data-testid="stSidebar"] * {{ color: #E7EAFB; }}
[data-testid="stSidebar"] hr {{ border-color: rgba(255,255,255,.1); }}
[data-testid="stSidebar"] .stRadio > div {{ gap: 4px; }}
[data-testid="stSidebar"] .stRadio label {{ background: transparent; border-radius: 10px; padding: 10px 12px; width: 100%; cursor: pointer;
    transition: background .15s ease; font-weight: 500; }}
[data-testid="stSidebar"] .stRadio label:hover {{ background: rgba(255,255,255,.07); }}
[data-testid="stSidebar"] .stRadio label[data-checked="true"], [data-testid="stSidebar"] .stRadio label:has(input:checked) {{ background: rgba(124,111,255,.22); box-shadow: inset 3px 0 0 #8F84FF; }}
[data-testid="stSidebar"] .stRadio label > div:first-child, [data-testid="stSidebar"] [data-baseweb="radio"] > div:first-child {{ display: none !important; }}
[data-testid="stSidebar"] [data-testid="stExpander"] {{ background: rgba(255,255,255,.05); border: 1px solid rgba(255,255,255,.14); }}
[data-testid="stSidebar"] [data-testid="stExpander"] summary, [data-testid="stSidebar"] [data-testid="stExpander"] summary * {{ color: #E7EAFB !important; }}
[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stCaptionContainer"] * {{ color: #A9B1D9 !important; }}
[data-testid="stSidebar"] input {{ background: rgba(255,255,255,.08) !important; color: #fff !important; border-color: rgba(255,255,255,.2) !important; }}
[data-testid="stSidebar"] .stButton > button {{ background: rgba(255,255,255,.08); color: #fff; border: 1px solid rgba(255,255,255,.14); }}
[data-testid="stSidebar"] .stButton > button:hover {{ background: rgba(255,255,255,.14); border-color: rgba(255,255,255,.3); }}
.cp-brand {{ display:flex; align-items:center; gap:10px; padding: 4px 4px 14px; }}
.cp-logo {{ width: 32px; height: 32px; border-radius: 9px; background: linear-gradient(135deg,#7C6FFF,#2F6BFF); display:grid; place-items:center; font-weight:700; color:#fff; font-size: 15px; }}
.cp-brand-name {{ font-weight: 650; font-size: 1.02rem; color:#fff; }}
.cp-sb-note {{ font-size: .74rem; color: #A9B1D9 !important; line-height: 1.45; }}

/* ---------- cards & text ---------- */
.cp-card {{ background: {TOKENS['surface']}; border: 1px solid {TOKENS['line']}; border-radius: 12px; padding: 18px 20px; margin-bottom: 12px;
    box-shadow: 0 1px 2px rgba(15,23,42,.04); transition: box-shadow .18s ease, border-color .18s ease; }}
.cp-card:hover {{ box-shadow: 0 4px 16px rgba(15,23,42,.07); border-color: #D8DBEA; }}
.cp-title {{ font-weight: 650; font-size: 1.02rem; margin: 0 0 2px; }}
.cp-sub {{ color: {TOKENS['muted']}; font-size: .86rem; }}
.cp-lead {{ color: {TOKENS['muted']}; font-size: .98rem; margin-bottom: 1.1rem; max-width: 70ch; }}
.cp-eyebrow {{ text-transform: uppercase; letter-spacing: .08em; font-size: .7rem; font-weight: 650; color: {TOKENS['accent']}; margin-bottom: 4px; }}
.cp-row {{ display:flex; gap: 16px; align-items:flex-start; justify-content: space-between; }}
.cp-meta {{ display:flex; flex-wrap:wrap; gap: 6px 14px; color:{TOKENS['muted']}; font-size:.82rem; margin: 6px 0 10px; }}
.cp-section-label {{ font-size: .72rem; font-weight: 650; letter-spacing:.06em; text-transform: uppercase; color: {TOKENS['muted']}; margin: 10px 0 6px; }}

/* ---------- chips ---------- */
.cp-chip {{ display:inline-block; padding: 3px 10px; border-radius: 999px; font-size: .76rem; font-weight: 550; margin: 0 6px 6px 0; border: 1px solid transparent; }}
.cp-chip.neutral {{ background:#F1F3F9; color:#334155; }}
.cp-chip.good {{ background:{TOKENS['green_soft']}; color:{TOKENS['green']}; }}
.cp-chip.warn {{ background:{TOKENS['amber_soft']}; color:{TOKENS['amber']}; }}
.cp-chip.bad {{ background:{TOKENS['red_soft']}; color:{TOKENS['red']}; }}
.cp-chip.accent {{ background:{TOKENS['accent_soft']}; color:{TOKENS['accent']}; }}
.cp-chip.blue {{ background:{TOKENS['blue_soft']}; color:{TOKENS['blue']}; }}

/* ---------- notices / empty / hero ---------- */
.cp-notice {{ border-radius: 10px; padding: 12px 14px; font-size: .88rem; margin: 8px 0 14px; border: 1px solid; }}
.cp-notice.info {{ background:{TOKENS['blue_soft']}; border-color:#CFE0FF; color:#1D3F99; }}
.cp-notice.warn {{ background:{TOKENS['amber_soft']}; border-color:#F3DFA0; color:#6B4A00; }}
.cp-notice.error {{ background:{TOKENS['red_soft']}; border-color:#F6CBC6; color:#7A1A12; }}
.cp-notice.success {{ background:{TOKENS['green_soft']}; border-color:#BFE5D3; color:#0B5B41; }}
.cp-empty {{ text-align:center; padding: 44px 24px; background:#fff; border:1px dashed #D5D9E8; border-radius: 14px; margin: 8px 0 16px; }}
.cp-empty .t {{ font-weight:650; font-size:1.05rem; margin-bottom:4px; }}
.cp-empty .d {{ color:{TOKENS['muted']}; font-size:.92rem; max-width: 52ch; margin: 0 auto; }}
.cp-hero {{ background: linear-gradient(135deg, {TOKENS['navy']} 0%, #1B2A6B 100%); color:#fff; border-radius: 16px; padding: 34px 34px 30px; margin-bottom: 20px; }}
.cp-hero h1 {{ color:#fff; font-size: 1.9rem; max-width: 22ch; }}
.cp-hero p {{ color:#C9D0F5; max-width: 60ch; margin: 8px 0 0; }}
.cp-steps {{ display:grid; grid-template-columns: repeat(auto-fit,minmax(200px,1fr)); gap: 12px; margin: 14px 0 6px; }}
.cp-step {{ background:#fff; border:1px solid {TOKENS['line']}; border-radius: 12px; padding: 14px 16px; }}
.cp-step b {{ display:block; margin-bottom: 2px; }}
.cp-step span {{ color:{TOKENS['muted']}; font-size:.86rem; }}

/* ---------- meters ---------- */
.cp-bar {{ height: 8px; border-radius: 999px; background:#ECEEF6; overflow:hidden; }}
.cp-bar > i {{ display:block; height:100%; border-radius:999px; background: linear-gradient(90deg,{TOKENS['accent']},{TOKENS['blue']}); transition: width .5s ease; }}
.cp-stack {{ display:flex; height:10px; border-radius:999px; overflow:hidden; background:#ECEEF6; gap:2px; }}
.cp-stack i {{ display:block; height:100%; }}
.cp-kv {{ display:flex; justify-content:space-between; font-size:.82rem; color:{TOKENS['muted']}; margin: 8px 0 4px; }}
.cp-stat {{ background:#fff; border:1px solid {TOKENS['line']}; border-radius: 12px; padding: 12px 14px; }}
.cp-stat .n {{ font-size: 1.5rem; font-weight: 700; line-height: 1.1; }}
.cp-stat .l {{ font-size: .76rem; color:{TOKENS['muted']}; font-weight:550; }}

/* ---------- controls ---------- */
.stButton > button, .stDownloadButton > button, [data-testid="stBaseLinkButton-secondary"], [data-testid="stBaseLinkButton-primary"] {{
    border-radius: 10px; font-weight: 550; transition: all .15s ease; border: 1px solid {TOKENS['line']}; }}
.stButton > button[kind="primary"], [data-testid="stBaseLinkButton-primary"] {{ background: {TOKENS['accent']}; border-color: {TOKENS['accent']}; color:#fff; }}
.stButton > button[kind="primary"]:hover, [data-testid="stBaseLinkButton-primary"]:hover {{ background:#4A3FD0; border-color:#4A3FD0; color:#fff; }}
.stButton > button:focus-visible, a:focus-visible {{ outline: 2px solid {TOKENS['accent']}; outline-offset: 2px; }}
[data-testid="stExpander"] {{ background:#fff; border:1px solid {TOKENS['line']}; border-radius: 12px; }}
[data-testid="stExpander"] summary {{ font-weight: 550; }}
[data-baseweb="tab-list"] {{ gap: 4px; border-bottom: 1px solid {TOKENS['line']}; }}
[data-baseweb="tab"] {{ font-weight: 550; padding: 8px 14px; }}
[data-testid="stFileUploader"] section {{ border-radius: 12px; border: 1.5px dashed #C9CEE3; background:#fff; }}

/* ---------- responsive ---------- */
@media (max-width: 768px) {{
  .block-container {{ padding: 1.1rem 1rem 3rem; }}
  .cp-hero {{ padding: 22px 20px; border-radius: 14px; }}
  .cp-hero h1 {{ font-size: 1.45rem; }}
  .cp-row {{ flex-direction: column; gap: 8px; }}
  h1 {{ font-size: 1.45rem; }}
}}
@media (prefers-reduced-motion: reduce) {{ * {{ transition: none !important; animation: none !important; }} }}
</style>
"""


def inject() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
