"""Reusable Streamlit UI components for CareerPilot AI."""
from __future__ import annotations

import streamlit as st

from ui.theme import match_color


def stat_card(label: str, value: str, delta: str | None = None, delta_positive: bool = True) -> None:
    delta_html = ""
    if delta:
        cls = "positive" if delta_positive else "neutral"
        delta_html = f'<div class="cp-stat-delta {cls}">{delta}</div>'

    st.markdown(
        f"""
        <div class="cp-stat-card">
            <div class="cp-stat-label">{label}</div>
            <div class="cp-stat-value">{value}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def match_ring_svg(score: int, size: int = 64) -> str:
    """Render a circular progress ring as inline SVG for a match score."""
    color = match_color(score)
    radius = (size - 8) / 2
    circumference = 2 * 3.14159265 * radius
    offset = circumference * (1 - score / 100)
    center = size / 2

    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">
        <circle cx="{center}" cy="{center}" r="{radius}"
                fill="none" stroke="#E8E8F0" stroke-width="6" />
        <circle cx="{center}" cy="{center}" r="{radius}"
                fill="none" stroke="{color}" stroke-width="6"
                stroke-dasharray="{circumference}" stroke-dashoffset="{offset}"
                stroke-linecap="round"
                transform="rotate(-90 {center} {center})" />
        <text x="{center}" y="{center + 5}" text-anchor="middle"
              font-size="15" font-weight="800" fill="{color}">{score}%</text>
    </svg>
    """


def status_badge_class(status: str) -> str:
    return f"cp-badge-status-{status.lower()}"


def job_card(company: str, role: str, skills: list[str], match_score: int | None = None, location: str = "") -> None:
    cols = st.columns([5, 1]) if match_score is not None else st.columns([1])

    with cols[0]:
        location_html = f' &middot; <span style="color:#6B7280;font-size:13px;">{location}</span>' if location else ""
        skill_badges = "".join(f'<span class="cp-badge cp-badge-skill">{s}</span>' for s in skills[:6])
        st.markdown(
            f"""
            <div class="cp-job-card">
                <div class="cp-job-role">{role}</div>
                <div class="cp-job-company">{company}{location_html}</div>
                <div>{skill_badges}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if match_score is not None:
        with cols[1]:
            st.markdown(
                f'<div class="cp-ring-wrap">{match_ring_svg(match_score, size=56)}</div>',
                unsafe_allow_html=True,
            )


def empty_state(title: str, body: str, icon: str = "📭") -> None:
    st.markdown(
        f"""
        <div style="text-align:center; padding: 48px 20px; color:#6B7280;">
            <div style="font-size:40px; margin-bottom:8px;">{icon}</div>
            <div style="font-size:17px; font-weight:700; color:#1A1B3A; margin-bottom:4px;">{title}</div>
            <div style="font-size:14px;">{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
