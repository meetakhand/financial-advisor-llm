# Client Portfolio Reference — Model Portfolios & Benchmarking

Source: Client portfolio data V1.0 (2026-07-12).

This document defines the three model portfolios FinAdvisor recommends
(Moderate, Growth, Aggressive) at ticker-level, along with their benchmark
proxies. Prices shown are the 2026-07-13 seed values used as a source-of-truth
floor when live market data is unavailable.

---

## Moderate Portfolio Breakdown (60/40 Baseline)

Target risk band: **Moderate**. Approximate equity/fixed-income split: 60/40.

| Asset Class            | Investment Description                                        | Ticker | Seed Price (USD) | Target Allocation |
|------------------------|---------------------------------------------------------------|--------|------------------|-------------------|
| Individual Equity      | Apple Inc. (Mega-cap Growth)                                  | AAPL   | 315.32           | 10%               |
| Individual Equity      | Microsoft Corp. (Mega-cap Tech/Stability)                     | MSFT   | 385.10           | 10%               |
| Exchange Traded Fund   | Vanguard Total Stock Market ETF (Broad US Market)             | VTI    | 372.69           | 20%               |
| Exchange Traded Fund   | Vanguard Total International Stock ETF (Global Diversification)| VXUS   | 85.34            | 10%               |
| Mutual Fund            | Vanguard 500 Index Fund Admiral Shares (Core Large Cap)       | VFIAX  | 699.22           | 10%               |
| Fixed Income (Bonds)   | iShares Core U.S. Aggregate Bond ETF (Total US Bond Market)   | AGG    | 98.08            | 15%               |
| Fixed Income (Bonds)   | Vanguard Total Bond Market Index Fund ETF (Govt/Corp mix)     | BND    | 72.77            | 15%               |
| Pension Baseline Fund  | Vanguard Target Retirement 2040 Fund (Balanced Accumulation)  | VFORX  | 42.15            | 10%               |

---

## Growth Portfolio Allocation (approx. 80/20)

Target risk band: **Growth**. Approximate equity/fixed-income split: 80/20.

| Asset Class            | Investment Description                                        | Ticker | Seed Price (USD) | Target Allocation |
|------------------------|---------------------------------------------------------------|--------|------------------|-------------------|
| Individual Equity      | Microsoft Corp. (Enterprise/Cloud Growth)                     | MSFT   | 385.10           | 10%               |
| Individual Equity      | Alphabet Inc. Class A (Digital Advertising/AI)                | GOOGL  | 182.40           | 10%               |
| Exchange Traded Fund   | Invesco QQQ Trust (Tech & Innovation Large-Cap)               | QQQ    | 725.51           | 20%               |
| Exchange Traded Fund   | Vanguard Total International Stock ETF (Global Markets)       | VXUS   | 85.34            | 10%               |
| Index Fund (MF)        | Vanguard Total Stock Market Index Fund Admiral (Broad US)     | VTSAX  | 138.25           | 15%               |
| Growth Mutual Fund     | Fidelity Contrafund (Large-Cap Growth Focused)                | FCNTX  | 20.15            | 10%               |
| Fixed Income (Bonds)   | iShares Core U.S. Aggregate Bond ETF (Core Fixed Income)      | AGG    | 98.08            | 15%               |
| Pension Baseline Fund  | Vanguard Target Retirement 2050 Fund (Growth Horizon)         | VFIFX  | 64.80            | 10%               |

---

## Aggressive Portfolio Allocation (approx. 85/15)

Target risk band: **Aggressive**. Approximate equity/fixed-income split: 85/15.

| Asset Class            | Investment Description                                        | Ticker | Seed Price (USD) | Target Allocation |
|------------------------|---------------------------------------------------------------|--------|------------------|-------------------|
| Individual Equity      | NVIDIA Corp. (High-Growth Tech/AI)                            | NVDA   | 130.45           | 15%               |
| Individual Equity      | Amazon.com, Inc. (E-commerce/Cloud Growth)                    | AMZN   | 194.20           | 10%               |
| Exchange Traded Fund   | Invesco QQQ Trust (Tech & Growth Heavy)                       | QQQ    | 725.51           | 25%               |
| Exchange Traded Fund   | iShares Russell 2000 ETF (Small-Cap Growth)                   | IWM    | 295.99           | 10%               |
| Exchange Traded Fund   | Vanguard Total International Stock ETF                        | VXUS   | 85.34            | 10%               |
| Mutual Fund            | Vanguard 500 Index Fund Admiral Shares (Core S&P 500)         | VFIAX  | 699.22           | 15%               |
| Fixed Income (Bonds)   | Vanguard Total Bond Market Index Fund                         | VBTLX  | 9.58             | 5%                |
| Pension Baseline Fund  | Vanguard Target Retirement 2055 Fund (Aggressive Path)        | VFFVX  | 72.30            | 10%               |

---

## Benchmarking — Turnkey ETF Proxies (Option 1)

FinAdvisor uses **turnkey public-index ETF proxies** to benchmark each model
portfolio. This keeps benchmarking to a single quote per portfolio and mirrors
what a retail investor could realistically compare against.

| Model Portfolio | Benchmark Description                              | Turnkey Proxy ETF | Alt Proxy |
|-----------------|----------------------------------------------------|-------------------|-----------|
| Moderate (60/40)  | Morningstar Moderate Target Risk Index           | **AOM**           | VBIAX     |
| Growth (80/20)    | Morningstar Growth Target Risk Index             | **AOR**           | —         |
| Aggressive (85/15)| Morningstar Aggressive Target Risk Index         | **AOA**           | —         |

### Underlying Custom-Blend Composition (reference only)

FinAdvisor does not construct these blends live, but they document what each
turnkey proxy is approximating.

- **Moderate (60/40):** 60% equity (MSCI ACWI or CRSP US Total Market) + 40%
  fixed income (Bloomberg US Aggregate Bond Index, tracked by AGG).
- **Growth (80/20):** 60% CRSP US Total Market + 20% FTSE Global All-Cap
  ex-US + 20% Bloomberg US Aggregate.
- **Aggressive (85–90% equity):** S&P 500 + Nasdaq-100 (via QQQ) + Russell
  2000 (small-caps) with 10% Bloomberg US Aggregate or short-term Treasuries.

### Off-the-Shelf Peer Proxies

- **Moderate:** Vanguard Balanced Index Fund (VBIAX) or iShares Core Moderate
  Allocation ETF (AOM).
- **Growth:** iShares Core Growth Allocation ETF (AOR).
- **Aggressive:** iShares Core Aggressive Allocation ETF (AOA).

---

## Asset-Class Categories

For portfolio analysis, FinAdvisor rolls up ticker-level holdings into five
asset classes so drift and rebalancing math remain interpretable:

- **Individual Equity** — single-stock holdings (AAPL, MSFT, NVDA, GOOGL, AMZN).
- **Exchange Traded Fund (ETF)** — VTI, VXUS, QQQ, IWM, AOM, AOR, AOA.
- **Mutual Fund** — VFIAX, VTSAX, FCNTX (blended equity/fixed income treated as
  ~70% equity / 30% fixed income for allocation math).
- **Fixed Income (Bonds)** — AGG, BND, VBTLX.
- **Pension Baseline Fund** — target-date funds (VFORX, VFIFX, VFFVX) treated
  as ~60% equity / 40% fixed income for allocation math.

---

Source: Client portfolio data V1.0 (2026-07-12).
