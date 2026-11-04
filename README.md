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

## From 2008: win back every loss in one quarter ($100k base, USD)

Every quarter sells ATM puts on $100k of NQ notional from 2008-03-20; profits are not reinvested. After a loss the next put is sized so that, if it expires OTM, its premium repays the whole cumulated loss plus the normal premium. No capital or drawdown limit. Ledger: [`results/recovery_2008_ledger.csv`](results/recovery_2008_ledger.csv), campaigns: [`results/recovery_2008_campaigns.csv`](results/recovery_2008_campaigns.csv), report section 9.

| | Recovery rule | Fixed size |
|---|---|---|
| Normal P&L when the put expires OTM (premium on $100k, average) | $4,216 | same |
| Total P&L, 2008 to 2026 | $242,680 | $151,765 |
| Worst cumulated loss at an expiry | -$53,140 | -$29,924 |
| Worst cumulated loss on any day (marked to market) | -$104,425 | -$40,304 |
| Biggest position | 7.94x = $793,846 notional | $100,000 |

### Same rule with a 10% OTM long put, or a delta hedge after a 2.5% / 5% fall

| Variant (from 2008, $100k base) | Normal P&L if OTM | Total P&L | Worst cumulated loss (expiry) | Worst on any day | Biggest size |
|---|---|---|---|---|---|
| Naked ATM put | $4,216 | $242,680 | -$53,140 | -$104,425 | 7.9x |
| ATM put + long put 10% lower | $2,560 | $143,297 | -$30,756 | -$87,417 | 10.1x |
| Naked + delta hedge below -2.5% | $4,216 | $156,789 | -$26,235 | -$28,573 | 4.2x |
| Naked + delta hedge below -5% | $4,216 | $196,170 | -$93,927 | -$95,288 | 12.4x |
| Naked + delta hedge from -2.5% to expiry | $4,216 | $121,751 | -$49,858 | -$55,131 | 14.8x |
| Naked + delta hedge from -5% to expiry | $4,216 | $187,442 | -$20,414 | -$22,614 | 6.7x |
| Spread -10% + delta hedge below -5% | $2,560 | $117,066 | -$41,272 | -$43,925 | 12.9x |

Robustness across all roll calendars and a 1990 start: [`results/recovery_variants_robustness.csv`](results/recovery_variants_robustness.csv). Premiums are estimated per quarter from that day's implied volatility (not fixed, not traded quotes).

### Inside "hedge from -5% until expiry"

Once NQ closes 5% below the strike, the put is delta-hedged with NQ futures every day until expiry (more futures if NQ keeps falling, bought back as it rises; never net short). Per $100k at fixed size since 2008: in the 10 quarters where NQ then rebounded above the strike, the hedge cost -$71,312 (sell low, buy back high); in the 11 quarters where NQ stayed down it saved $51,248; net -$55,488, the price of the protection. At the same worst-day loss, a bigger fixed size beat the recovery rule in 4 of 6 tests ([`results/h5_equal_risk.csv`](results/h5_equal_risk.csv)); report section 9.2 has the full breakdown. Calmar ratio (annual P&L / max drawdown) from 2008: 0.42 with the recovery rule, 0.40 at fixed size (naked put 0.12 / 0.19); median across all calendars and starts about 0.2 ([`results/calmar_by_test.csv`](results/calmar_by_test.csv)). Reinvesting after each fully won-back series (base = 1x account): standard Calmar (CAGR / max % drawdown) from 2008 rises from 0.28 to 0.44 with the recovery rule (CAGR 5.9% to 10.4%), but from 1990 the worst drawdown grows to 58-85% ([`results/reinvest_study.csv`](results/reinvest_study.csv), report section 9.3). Tried improvements (report section 9.4, [`results/improvement_summary.csv`](results/improvement_summary.csv)): selling OTM calls, buying a -15%/-20% put, and switching to long NQ after a 40% account or market drawdown. None beat the baseline across the six tests; a -20% put at fixed size trimmed the worst drawdown (34% to 28%) for less growth.

### Combined with the NQ pyramid strategy (one account)

The pyramid strategy from the `NQPyramidingUP` repo (70% recovery entries, +20% reset, weekly 20-delta calls) is long NQ only while the market rallies, and sits flat after a fall, when these puts need the most capital. Both are measured per $100k unit, never reinvested, on daily closes from 20 Mar 2008 to 2 Nov 2026. Calmar of one pyramid unit plus k units of the -5%-hedged puts with the recovery rule:

| Put units per pyramid unit | 0 | 1 | 2 | 3 | ~4.75 (best) |
|---|---:|---:|---:|---:|---:|
| Profit per year | $75,535 | $85,366 | $95,197 | $105,028 | $122,233 |
| Worst drawdown | -$173,862 | -$181,396 | -$189,962 | -$199,658 | -$217,019 |
| Calmar | 0.43 | 0.47 | 0.50 | 0.53 | 0.56 |
| Peak capital in use, one account | $208,270 | $242,241 | $295,241 | $384,123 | $540,400 |
| Same, two separate accounts | $208,270 | $297,601 | $386,931 | $476,262 | $632,591 |

Fixed-size puts barely move Calmar (0.44 to 0.46). Near its 52-week high the pyramid holds about $556k of NQ per unit, but only $88-150k once NDX is 5% or more below it. So one account needs 19-24% less capital than two, though profit per dollar of peak capital does not improve (36% alone, 35% / 32% combined). Both lost together in choppy corrections (2010, 2015-16, 2025), but not in the long bear markets (2008, 2022), when the pyramid sat flat. Report section 10, [`results/combo_pyramid_mix.csv`](results/combo_pyramid_mix.csv), and the daily series of both strategies in [`results/combo_pyramid_daily.csv`](results/combo_pyramid_daily.csv). The pyramid inputs are in `data/external/nqpyramidingup/`.

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
| `nqput/combo.py` | combination with the NQ pyramid strategy (inputs in `data/external/nqpyramidingup/`) |
| `nqput/report.py` | charts and `reports/REPORT.md` |
| `results/` | all output tables (CSV/JSON): every roll's premium, 200+ strategy variants, robustness |
| `tests/` | synthetic-data checks (delta-hedged P&L ≈ vega × (IV − RV), payoff identity, sizing rule) |

All results are hypothetical and model-based. This is not investment advice.
