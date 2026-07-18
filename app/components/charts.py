"""Plotly wrappers — allocation donut, current-vs-target bars, projection line, risk gauge."""
from __future__ import annotations

from typing import Iterable

import plotly.graph_objects as go

# NexWealth AI palette — navy primary, coral highlight, warm neutrals.
_NAVY       = "#0F1A2C"
_NAVY_MID   = "#3F5B8F"
_NAVY_LIGHT = "#8FA7CE"
_CORAL      = "#F0664A"
_CREAM      = "#E9E1D3"

_PALETTE = {
    "Equity":        _NAVY,
    "International": _NAVY_MID,
    "Fixed Income":  _NAVY_LIGHT,
    "Pension":       "#B279A2",
    "Cash":          _CREAM,
    "custom":        _CORAL,
}


def _base_layout(fig: go.Figure, title: str) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, font=dict(color=_NAVY, size=15)),
        height=340, margin=dict(t=44, b=10, l=10, r=10),
        paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
        font=dict(color=_NAVY),
        legend=dict(font=dict(color=_NAVY)),
    )
    return fig


def allocation_donut(allocation_pct: dict[str, float], title: str = "Current allocation") -> go.Figure:
    labels = [k for k, v in allocation_pct.items() if v > 0]
    values = [allocation_pct[k] for k in labels]
    colors = [_PALETTE.get(k, "#B0B0B0") for k in labels]
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.58, sort=False,
        marker=dict(colors=colors, line=dict(color="#FFFFFF", width=2)),
        textinfo="label+percent",
    ))
    return _base_layout(fig, title)


def current_vs_target_bars(current: dict[str, float], target: dict[str, float],
                             title: str = "Current vs Target allocation") -> go.Figure:
    classes = list(target.keys()) or list(current.keys())
    fig = go.Figure()
    fig.add_bar(name="Current", x=classes, y=[current.get(c, 0.0) for c in classes],
                    marker_color=_NAVY_LIGHT)
    fig.add_bar(name="Target",  x=classes, y=[target.get(c, 0.0) for c in classes],
                    marker_color=_NAVY)
    fig.update_layout(barmode="group", yaxis_title="% of portfolio")
    return _base_layout(fig, title)


def projection_line(years: Iterable[int], projected: Iterable[float],
                      target_future: float | None = None,
                      title: str = "Projected corpus vs target") -> go.Figure:
    fig = go.Figure()
    fig.add_scatter(x=list(years), y=list(projected), mode="lines+markers",
                    name="Projected", line=dict(color=_NAVY, width=3),
                    marker=dict(color=_NAVY))
    if target_future is not None:
        fig.add_hline(y=target_future, line_dash="dash", line_color=_CORAL,
                      annotation_text=f"Target ${target_future:,.0f}",
                      annotation_position="top right",
                      annotation_font=dict(color=_CORAL))
    fig.update_layout(xaxis_title="Year", yaxis_title="Value (USD)")
    return _base_layout(fig, title)


def project_series(current_savings: float, monthly_contribution: float,
                    annual_return: float, years: int) -> tuple[list[int], list[float]]:
    """Year-end projection helper for the chart (compound + monthly SIP)."""
    xs, ys = [], []
    balance = current_savings
    for y in range(0, max(years, 0) + 1):
        xs.append(y)
        ys.append(round(balance, 2))
        balance = balance * (1 + annual_return) + monthly_contribution * 12
    return xs, ys


def risk_gauge(score: float, band: str, title: str = "Risk Score") -> go.Figure:
    """Arc gauge — matches the reference NexWealth AI Risk Profile page."""
    score = max(0.0, min(100.0, float(score)))
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number=dict(suffix="/100", font=dict(color=_NAVY, size=42)),
        gauge=dict(
            axis=dict(range=[0, 100], tickcolor=_NAVY_MID,
                        tickfont=dict(color=_NAVY_MID, size=11)),
            bar=dict(color=_NAVY, thickness=0.25),
            bgcolor="#FFFFFF",
            borderwidth=0,
            steps=[
                dict(range=[0, 34],   color=_NAVY_LIGHT),
                dict(range=[34, 74],  color=_NAVY_MID),
                dict(range=[74, 100], color=_NAVY),
            ],
            threshold=dict(
                line=dict(color=_CORAL, width=4),
                thickness=0.85, value=score,
            ),
        ),
        title=dict(text=f"<b>{title}</b> · {band}", font=dict(color=_NAVY, size=14)),
        domain=dict(x=[0, 1], y=[0, 1]),
    ))
    fig.update_layout(
        height=320, margin=dict(t=54, b=10, l=10, r=10),
        paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
        font=dict(color=_NAVY),
    )
    return fig
