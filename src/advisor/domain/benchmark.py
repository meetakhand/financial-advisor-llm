"""Benchmarking — turnkey ETF proxies per model portfolio.

Approach: one benchmark proxy per portfolio. AOM / AOR / AOA are iShares Core
Allocation ETFs whose glide-path mirrors the Morningstar Target Risk indexes.
This keeps benchmarking to a single quote per portfolio (cheap under AV free
tier), while still giving a legitimate peer comparison.

Custom-blend construction is documented in corpus/client_portfolio_reference.md
but not evaluated live — captured as ``blend_description`` for the Report.
"""
from __future__ import annotations

from dataclasses import dataclass

from advisor.domain.models import MODEL_ASSUMPTIONS


@dataclass(frozen=True)
class BenchmarkProxy:
    model: str
    proxy_ticker: str
    proxy_name: str
    alt_ticker: str | None
    blend_description: str
    illustrative_return: float   # long-run expected annual return, illustrative


BENCHMARK_PROXIES: dict[str, BenchmarkProxy] = {
    "Moderate": BenchmarkProxy(
        model="Moderate",
        proxy_ticker="AOM",
        proxy_name="iShares Core Moderate Allocation ETF",
        alt_ticker="VBIAX",
        blend_description=(
            "60% equity (MSCI ACWI or CRSP US Total Market) + 40% fixed income "
            "(Bloomberg US Aggregate Bond Index)"
        ),
        illustrative_return=0.065,
    ),
    "Growth": BenchmarkProxy(
        model="Growth",
        proxy_ticker="AOR",
        proxy_name="iShares Core Growth Allocation ETF",
        alt_ticker=None,
        blend_description=(
            "60% CRSP US Total Market + 20% FTSE Global All-Cap ex-US + 20% "
            "Bloomberg US Aggregate Bond Index"
        ),
        illustrative_return=0.085,
    ),
    "Aggressive": BenchmarkProxy(
        model="Aggressive",
        proxy_ticker="AOA",
        proxy_name="iShares Core Aggressive Allocation ETF",
        alt_ticker=None,
        blend_description=(
            "S&P 500 + Nasdaq-100 (via QQQ) + Russell 2000 (small-caps) with "
            "10% Bloomberg US Aggregate Bond Index"
        ),
        illustrative_return=0.100,
    ),
}


@dataclass(frozen=True)
class BenchmarkResult:
    model: str
    proxy_ticker: str
    proxy_name: str
    portfolio_expected_return: float
    benchmark_expected_return: float
    excess_return: float            # portfolio - benchmark (illustrative alpha)
    tracking_error_est: float       # rough std-dev of excess, illustrative
    blend_description: str


def run_benchmarking(model_name: str) -> BenchmarkResult:
    if model_name not in BENCHMARK_PROXIES:
        raise ValueError(f"Unknown model for benchmarking: {model_name}")
    proxy = BENCHMARK_PROXIES[model_name]
    portfolio_ret = MODEL_ASSUMPTIONS[model_name]["expected_return"]
    portfolio_vol = MODEL_ASSUMPTIONS[model_name]["volatility"]
    excess = portfolio_ret - proxy.illustrative_return
    # Illustrative tracking error: ~15% of portfolio vol. Not a live measurement.
    te_est = round(portfolio_vol * 0.15, 4)
    return BenchmarkResult(
        model=model_name,
        proxy_ticker=proxy.proxy_ticker,
        proxy_name=proxy.proxy_name,
        portfolio_expected_return=round(portfolio_ret, 4),
        benchmark_expected_return=round(proxy.illustrative_return, 4),
        excess_return=round(excess, 4),
        tracking_error_est=te_est,
        blend_description=proxy.blend_description,
    )
