# NQ 3-month ATM put selling: backtest (1986-2026)

This repo backtests selling a **3-month at-the-money put on Nasdaq-100 futures (NQ)** every quarter, plus the three add-ons that were asked about:

1. **Recovery sizing.** After a put finishes in the money at a loss, the next 3-month position is made bigger so it covers the loss and still earns a bit.
2. **Buying an OTM put**, which turns the trade into a put spread (-5/-10/-15/-20% wings).
3. **Delta hedging with NQ futures**: full daily or weekly hedge, 50% hedge, a "delta cap", and a stop-style hedge.

Option premiums are **estimated** from 40 years of public index data, because free historical NQ option quotes don't exist. The 30-day level comes from VXN/VIX. ATM vol is calibrated on the VOLQ ATM index. The 3-month level uses the VIX3M/VIX term structure, and the put wing uses a parametric skew. See the full report for the method and the error bounds.

**Full report with charts and tables: [`reports/REPORT.md`](reports/REPORT.md)**

## Key results (fixed size: $1M notional per quarter, % of $1M capital, 1986-2026)

| Variant | Return %/yr | Sharpe | Max drawdown | Worst quarter | Wiped out? |
|---|---|---|---|---|---|
| Naked ATM put | 6.1 | 0.41 | 85% | -26% | no |
| Put spread ATM/-10% | 3.1 | 0.42 | 36% | -8% | no |
| Put spread ATM/-20% | 4.4 | 0.40 | 65% | -17% | no |
| Naked + delta cap hedge | 5.2 | 0.50 | 58% | -18% | no |
| Naked + full daily delta hedge | 0.5 | 0.19 | 17% | -7% | no |
| Naked + recovery sizing (Mar/Jun/Sep/Dec) | 13.7 | 0.39 | 212% | -95% | survived by luck |
| Naked + recovery sizing (Jan/Apr/Jul/Oct or Feb/May/Aug/Nov) | n/a | n/a | n/a | n/a | **yes, Sep 2001** |
| Long NQ futures 0.5x (benchmark) | 7.1 | 0.55 | 73% | -18% | no |

Takeaways:

* **Premiums.** An ATM 3-month put averaged **4.8% of notional**, about $27k per NQ at today's index. The range was 2.0% (2017) to 12.4% (2001). On 2026-11-02 (VXN 30.9) the estimate is about 5.6%, roughly $32k per NQ.
* **The edge is mostly Nasdaq beta.** ATM implied vol was only about 1 vol point above the realized vol that followed, so the put earns about what 0.5x long futures earns, with worse tails.
* **Recovery sizing is a martingale.** It was wiped out in 5 of 38 start years for the naked put and in 13-14 of 38 for put spreads. On the main calendar it only survived 2000-02 because one 11x-size quarter happened to expire OTM. Don't upsize after losses. Premiums are already about 40% richer after a losing quarter, so the same size recovers faster on its own.
* **The OTM wing and the delta cap are risk dials.** The wing cuts the tail but cuts the return about in proportion. The delta cap (short futures only for delta above the entry delta) was the only tweak that improved Sharpe and drawdown on all three roll calendars.

## Run it

```bash
pip install -r requirements.txt
python run_backtest.py --refresh     # download data + full study (~30 s)
PYTHONPATH=. python tests/test_engine.py   # engine sanity checks (or: python -m pytest -q)
```

## Layout

| Path | What |
|---|---|
| `nqput/data.py` | downloads and caches FRED / Cboe / Yahoo / Nasdaq data (into `data/raw/`, not committed) |
| `nqput/volmodel.py` | implied-vol surface proxy: VXN back-fill, ATM calibration, term structure, skew |
| `nqput/black76.py` | Black-76 pricing for options on futures |
| `nqput/backtest.py` | engine: quarterly cycles, unit P&L paths, hedging, sizing rules, metrics |
| `nqput/analysis.py` | strategy grid, premium tables, start-year / calendar / sensitivity studies |
| `nqput/report.py` | charts and `reports/REPORT.md` |
| `results/` | all output tables (CSV/JSON): every roll's premium, 200+ strategy variants, robustness |
| `tests/` | synthetic-data checks (delta-hedged P&L ≈ vega × (IV − RV), payoff identity, sizing rule) |

All results are hypothetical and model-based. This is not investment advice.
