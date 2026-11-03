# Selling 3-month ATM puts on Nasdaq-100 futures (NQ): backtest 1986-2026

*Data through 2026-11-02. 162 settled quarterly rolls, 1986-03-21 to 2026-09-18. All option prices are **model estimates** (free historical NQ option quotes do not exist). See [Method](#1-what-was-tested) and [Limitations](#10-limitations).*

## TL;DR: what to take from this

1. **Premiums.** A 3-month ATM put on NQ paid on average **4.8% of notional** (median 4.2%, range 2.0% in 2017 to 12.4% in 2001). At today's index that is about **$26,915 per NQ contract**. Right now (VXN 30.9) the estimate is **5.6%, about $31,840 per NQ**, richer than the long-run average.
2. **Plain strategy** (sell one ATM put per $1 of notional every quarter, hold to expiry): **+6.1%/yr** on notional, 81% winning quarters. But the losses are big: worst quarter -26%, max drawdown **85% of notional** (2000-02). Sharpe 0.41, while simply holding 0.5x NQ futures (the put's average delta) had Sharpe 0.55. Almost all of the put's profit is Nasdaq beta. The volatility premium in ATM NDX options is thin: 3-month ATM implied vol was on average only 1.1 vol pts (median 2.6) above the realized vol that followed.
3. **Increasing size after an ITM loss to win it back is a martingale, and it is the main risk in the plan.** On the Mar/Jun/Sep/Dec calendar it lifted returns to 13.7%/yr. To do that it needed up to **11x size** and suffered a -95% quarter (drawdown 212% of capital). It survived 2000-02 only because the ~11x position sold in March 2001 happened to expire out of the money. The *same rule* on the Jan/Apr/Jul/Oct or Feb/May/Aug/Nov calendars **wiped out the account in 2001**. By start year it was wiped out in 5/38 start years (naked) and in 13/38 and 14/38 start years with -10%/-20% put spreads. For the naked put, every softened version (max 3x, recover once, recover over 4 quarters, 200-day trend filter) still lost more than 100% of starting capital at its worst point on at least one calendar. The mildest version, 'recover once' on a -10% put spread, stayed below that but deepened drawdowns from 36-53% to 51-85% for little or no Sharpe gain. **Don't upsize after losses.**
4. **Buying an OTM put (put spread)** is a risk dial, not an edge. With a -10% wing the worst quarter is -8% (vs -26%) and the max drawdown 36% (vs 85%), but the return halves to 3.1%/yr; Sharpe 0.42 vs 0.41. Put spreads make the martingale *worse*: the net credit is smaller, so 'recovering' needs larger multipliers.
5. **Delta hedging.** A full daily futures hedge strips out the equity premium and leaves only the thin vol premium: +0.5%/yr. That figure is fragile: it ranges from -1.4% to +2.4%/yr if true implied vol was 10% lower or higher than estimated. The one hedge that helped on every calendar is a **delta cap**: short futures only for the delta the put gains *above its entry delta* as NQ falls. It returned 5.2%/yr at Sharpe 0.50 (vs 0.41) with max drawdown 58% (vs 85%).
6. **How to get your 'recovery' without a martingale.** After a losing quarter implied vol is higher, so the *same size* already collects more: on average 6.2% of notional vs 4.5% after a win, and the next quarter averaged +2.4% vs +1.3%. Size for survival instead: the naked put lost 85% of its notional in 2000-02, so naked notional of about 0.3-0.5x equity would have cost 26-43% of the account in that scenario. Cap the tail with a -15% to -20% wing or a delta cap. Ladder entries monthly (1/3 of the size per cycle) so results do not hinge on one roll date.
7. **Today (2026-11-02).** The 3-month put sold 2026-09-18 (strike ~29,888, premium ~1,206 pts = $24,112/NQ) is **in the money**. NQ is about 28,106, the put is worth ~2,190 pts, and the mark-to-market P&L is ~-1,014 pts (-$20,281 per NQ). It has 46 days left and delta ~0.72. Under your rule, a loss at the 18-Dec expiry would trigger a bigger position. The backtest says roll at normal size, because today's rich premium already does part of the recovery.

8. **Start in 2008 with a 50% drawdown limit (section 9).** $1M from 2008-03-20, your recovery rule capped so a 45% NQ crash could not take the account more than 50% below its high: puts that expired worthless earned $2,650,667 over 53 quarters, losing quarters cost -$1,108,070, net $1,797,449. The deepest cumulated loss was -$349,612 (Dec 2008); the worst day was 46.5% below the high. Without the limit the same rule was 83% down on 2009-03-09.

## 1. What was tested

* **Trade.** At the close of each quarterly NQ expiry (3rd Friday of Mar/Jun/Sep/Dec), sell the put that expires at the next quarterly expiry (~13 weeks) with the **strike at the futures price (ATM-forward)**. Hold it to expiry. Settlement uses the NDX close on expiry day. 1 NQ option = $20 x index.
* **Size.** Base position = $1,000,000 notional (= 1.0x a $1M account; ~1.8 NQ at today's level). Sizes are fractional. Profits are not reinvested, so every quarter of 40 years counts equally. Returns, drawdowns and quarters are all in % of the $1M starting capital (= base notional).
* **Pricing.** Black-76 on the NQ future, with F = NDX x exp((r - q)T), T-bill r and q = 0.7%. Implied vol is estimated as:
  1. 30-day level = **VXN** (actual since 2001-01-23). Before that VXN is reconstructed from VIX (or VXO before 1990) and the NDX/SPX realized-vol ratio: regression R² 0.95.
  2. ATM vol = -2.30 + 0.982 x VXN. VXN is a variance-swap-style index that includes skew, so it sits above ATM. This line is calibrated on Nasdaq's **VOLQ** at-the-money NDX vol index (2019-09-30..2023-09-28, mean ATM/VXN = 0.89).
  3. 3-month ATM vol = 30-day ATM vol x **VIX3M/VIX** term-structure ratio (regression proxy before 2006, R² 0.68).
  4. Put skew: sigma(K) = sigma_ATM + 0.22/sqrt(T) x ln(F/K). For 3 months that is about +4.6 vol pts at a 10% OTM strike, and the 25-delta risk reversal is about -4.5 vols, typical for NDX.
* **Costs.** Options trade 0.5 vol pt worse than model mid (about 2-3% of the ATM premium), plus $2.50 per contract. Futures hedges cost 1 bp of notional per side. Daily mark-to-market at model mid.
* **Margin and ruin.** Margin is assumed at 10% of notional for a naked put, or the max loss for a spread. A position is cut back if equity cannot carry it. 'Wiped out' means account equity reached zero.
* **Recovery sizing (your rule).** Next size = 1 + (drawdown from equity high) / (premium per $1 of notional). If the new put expires worthless it repays the whole deficit and still earns the normal premium (the 'earn a bit'). Variants tested: *recover once* (only one upsized quarter after a base-size loss), *max 3x*, *recover over 4 quarters*, and *+ 200-day trend filter* (stand aside when NDX < 200-day average).
* **Hedges.** Full delta hedge daily or weekly, 50% hedge, *delta cap* (short futures only for delta above the entry delta), and *stop hedge* (fully delta-hedged only while the put is ITM).

## 2. Premium history

![premium history](figures/1_premium_history.png)

| Decade | Rolls | Avg 3M ATM IV % | Avg premium % of notional | Avg premium $ per NQ | Share expired ITM | Avg naked P&L % per qtr |
|---|---|---|---|---|---|---|
| 1980s | 16 | 21.0 | 4.12 | $149 | 38% | +0.68 |
| 1990s | 40 | 25.4 | 5.01 | $908 | 20% | +2.88 |
| 2000s | 40 | 30.3 | 5.99 | $2,097 | 45% | -0.64 |
| 2010s | 40 | 17.4 | 3.47 | $2,926 | 25% | +1.79 |
| 2020s | 26 | 26.1 | 5.17 | $16,132 | 31% | +2.96 |

Over all rolls: 31% expired ITM, but only 19% lost money, because the premium absorbs small dips. Average winning quarter **+4.3%**, average losing quarter **-10.2%** of notional. One loss wipes out about 2.4 wins, which is why the win rate looks great while the equity curve does not.

**Worst quarters** (% of notional):

| Sold | Expiry | IV % | Premium % | NDX move % | Naked P&L % | Spread -10% P&L % | Spread -20% P&L % |
|---|---|---|---|---|---|---|---|
| 2000-12-15 | 2001-03-16 | 51.55 | 10.09 | -35.38 | -26.21 | -6.34 | -13.74 |
| 2008-09-19 | 2008-12-19 | 27.45 | 5.45 | -30.25 | -24.95 | -7.06 | -15.64 |
| 2000-09-15 | 2000-12-15 | 40.76 | 7.99 | -30.65 | -23.67 | -6.61 | -14.47 |
| 2001-06-15 | 2001-09-21 | 54.29 | 11.08 | -33.77 | -23.28 | -6.23 | -13.43 |
| 2002-03-15 | 2002-06-21 | 38.75 | 7.96 | -30.75 | -23.11 | -6.61 | -14.47 |
| 1990-06-15 | 1990-09-21 | 18.69 | 3.78 | -23.91 | -21.70 | -7.65 | -16.80 |
| 1987-09-18 | 1987-12-18 | 20.67 | 4.05 | -23.27 | -20.46 | -7.57 | -16.62 |
| 2019-12-20 | 2020-03-20 | 14.56 | 2.89 | -19.41 | -16.79 | -7.89 | -16.95 |

Per-year detail (expiry year; premium $ per NQ is at that year's index level): [`results/premiums_by_year.csv`](../results/premiums_by_year.csv). Every roll: [`results/premiums_quarterly.csv`](../results/premiums_quarterly.csv).

| Year | Rolls | Avg IV % | Avg premium % | Avg premium $/NQ | Expired ITM | Naked P&L % (year) | NDX move % |
|---|---|---|---|---|---|---|---|
| 2015 | 4 | 16.46 | 3.28 | $2,869 | 1 | 8.67 | 5.45 |
| 2016 | 4 | 17.96 | 3.57 | $3,221 | 2 | 10.98 | 8.86 |
| 2017 | 4 | 13.26 | 2.63 | $2,902 | 0 | 10.13 | 31.57 |
| 2018 | 4 | 15.51 | 3.10 | $4,431 | 1 | -7.99 | -6.49 |
| 2019 | 4 | 19.67 | 3.87 | $5,522 | 0 | 15.08 | 43.54 |
| 2020 | 4 | 36.12 | 7.18 | $12,722 | 1 | 8.72 | 46.78 |
| 2021 | 4 | 25.92 | 5.16 | $14,012 | 0 | 20.24 | 24.04 |
| 2022 | 4 | 30.53 | 6.06 | $15,981 | 3 | -12.36 | -28.84 |
| 2023 | 4 | 23.55 | 4.63 | $12,399 | 1 | 17.82 | 47.86 |
| 2024 | 4 | 17.98 | 3.57 | $13,390 | 1 | 13.22 | 28.08 |
| 2025 | 4 | 20.60 | 4.06 | $17,816 | 1 | 7.82 | 19.05 |
| 2026 | 3 | 24.83 | 4.90 | $26,389 | 2 | 4.79 | 16.95 |

## 3. Results at fixed size

![fixed size](figures/2_fixed_size_structures.png)

| Structure | Return %/yr | Vol %/yr | Sharpe | Max DD % cap. | Worst qtr % | Qtrs up % |
|---|---|---|---|---|---|---|
| Naked ATM put | 6.1 | 14.9 | 0.41 | 85 | -26.2 | 81 |
| Put spread ATM/-5% | 1.3 | 4.3 | 0.30 | 22 | -3.7 | 74 |
| Put spread ATM/-10% | 3.1 | 7.3 | 0.42 | 36 | -7.9 | 76 |
| Put spread ATM/-15% | 4.0 | 9.5 | 0.42 | 53 | -12.5 | 78 |
| Put spread ATM/-20% | 4.4 | 11.1 | 0.40 | 65 | -17.0 | 80 |
| Long NQ futures 1x | 14.1 | 25.6 | 0.55 | 146 | -36.2 | 69 |

*Long NQ futures 1x is shown at full notional. At 0.5x (roughly the put's average delta) it returns 7.1%/yr at the same Sharpe 0.55 with max drawdown 73%.*

Since 2001 (actual VXN only):

| Structure | Return %/yr | Sharpe | Max DD % cap. | Worst qtr % |
|---|---|---|---|---|
| Naked ATM put | 7.0 | 0.49 | 49 | -25.0 |
| Put spread ATM/-5% | 1.5 | 0.34 | 12 | -3.7 |
| Put spread ATM/-10% | 3.4 | 0.45 | 24 | -7.9 |
| Put spread ATM/-15% | 4.6 | 0.46 | 33 | -12.5 |
| Put spread ATM/-20% | 5.0 | 0.44 | 39 | -17.0 |
| Long NQ futures 1x | 13.3 | 0.54 | 76 | -34.3 |

## 4. Recovery sizing: "next 3 months increase size to cover the loss"

![recovery](figures/3_recovery_sizing.png)

Same rule on the three possible 3-month roll calendars (return %/yr and max drawdown as % of starting capital):

| Structure · sizing | Mar/Jun/Sep/Dec | Jan/Apr/Jul/Oct | Feb/May/Aug/Nov |
|---|---|---|---|
| Naked ATM put · Fixed 1x | +6.1%/yr, DD 85% | +6.4%/yr, DD 76% | +7.6%/yr, DD 73% |
| Naked ATM put · Recover until whole | +13.7%/yr, DD 212% | **wiped out 2001-09** | **wiped out 2001-09** |
| Naked ATM put · Recover once | +8.0%/yr, DD 143% | +8.7%/yr, DD 83% | +10.3%/yr, DD 121% |
| Naked ATM put · Recover, max 3x | +10.3%/yr, DD 196% | +10.3%/yr, DD 187% | +11.4%/yr, DD 161% |
| Naked ATM put · Recover over 4 quarters | +8.6%/yr, DD 148% | +8.2%/yr, DD 154% | +9.6%/yr, DD 126% |
| Naked ATM put · Fixed + 200d trend filter | +5.2%/yr, DD 37% | +5.4%/yr, DD 33% | +4.8%/yr, DD 55% |
| Naked ATM put · Recover + 200d trend filter | +9.2%/yr, DD 39% | +8.5%/yr, DD 83% | +9.2%/yr, DD 159% |
| Spread -10% · Fixed 1x | +3.1%/yr, DD 36% | +1.6%/yr, DD 53% | +3.2%/yr, DD 49% |
| Spread -10% · Recover until whole | +7.5%/yr, DD 159% | **wiped out 2001-07** | **wiped out 2008-02** |
| Spread -10% · Recover once | +5.0%/yr, DD 51% | +2.1%/yr, DD 78% | +3.8%/yr, DD 85% |
| Spread -10% · Recover, max 3x | +5.2%/yr, DD 95% | +3.8%/yr, DD 129% | +5.3%/yr, DD 118% |
| Spread -10% · Recover over 4 quarters | +4.5%/yr, DD 87% | **wiped out 2006-07** | +4.7%/yr, DD 169% |
| Spread -10% · Fixed + 200d trend filter | +2.3%/yr, DD 16% | +1.6%/yr, DD 33% | +2.5%/yr, DD 20% |
| Spread -10% · Recover + 200d trend filter | +5.3%/yr, DD 24% | **wiped out 1998-10** | +5.5%/yr, DD 76% |

![start year](figures/4_recovery_by_start_year.png)

Why it fails: losses cluster. In the 2000-02 bust 6 of 11 quarterly puts lost money. Each loss raises the next size by (loss / next premium). A -25% quarter followed by a 5% premium means 6x size, and a second loss at 6x costs 150% of base notional. So two or three losses in a row compound to 10-30x size, right when volatility and gap risk are highest. Richer premiums after losses do not offset this. The rule turns a once-a-decade drawdown into an account-ending one, and survival depends on which month you happen to roll in.

## 5. Buying the OTM put

| Structure | Sizing | Return %/yr | Vol %/yr | Sharpe | Max DD % cap. | Worst qtr % | Qtrs up % | Max size x | Wiped out |
|---|---|---|---|---|---|---|---|---|---|
| Naked ATM put | Fixed 1x | 6.1 | 14.9 | 0.41 | 85 | -26.2 | 81 | 1.0 | no |
| Naked ATM put | Recover until whole | 13.7 | 35.1 | 0.39 | 212 | -95.3 | 81 | 10.9 | no |
| Naked ATM put | Recover once | 8.0 | 23.2 | 0.34 | 143 | -88.3 | 81 | 4.3 | no |
| Put spread ATM/-5% | Fixed 1x | 1.3 | 4.3 | 0.30 | 22 | -3.7 | 74 | 1.0 | no |
| Put spread ATM/-5% | Recover until whole | -4.4 | 24.8 | -0.18 | 166 | -82.0 | 70 | 29.9 | 2008-09-19 |
| Put spread ATM/-5% | Recover once | 2.6 | 6.7 | 0.39 | 36 | -10.3 | 74 | 3.8 | no |
| Put spread ATM/-10% | Fixed 1x | 3.1 | 7.3 | 0.42 | 36 | -7.9 | 76 | 1.0 | no |
| Put spread ATM/-10% | Recover until whole | 7.5 | 23.9 | 0.31 | 159 | -63.5 | 76 | 19.5 | no |
| Put spread ATM/-10% | Recover once | 5.0 | 10.7 | 0.47 | 51 | -23.8 | 76 | 4.2 | no |
| Put spread ATM/-15% | Fixed 1x | 4.0 | 9.5 | 0.42 | 53 | -12.5 | 78 | 1.0 | no |
| Put spread ATM/-15% | Recover until whole | -6.2 | 49.1 | -0.13 | 252 | -123.7 | 74 | 13.0 | 2002-06-06 |
| Put spread ATM/-15% | Recover once | 6.6 | 13.7 | 0.48 | 70 | -30.1 | 78 | 4.7 | no |
| Put spread ATM/-20% | Fixed 1x | 4.4 | 11.1 | 0.40 | 65 | -17.0 | 80 | 1.0 | no |
| Put spread ATM/-20% | Recover until whole | -6.2 | 56.9 | -0.11 | 275 | -124.9 | 76 | 13.5 | 2002-09-19 |
| Put spread ATM/-20% | Recover once | 6.4 | 16.9 | 0.38 | 105 | -45.5 | 80 | 5.0 | no |
| Long NQ futures 1x | Fixed 1x | 14.1 | 25.6 | 0.55 | 146 | -36.2 | 69 | 1.0 | no |

The wing caps the loss. The naked put's worst quarter was -26%. With -5/-10/-15/-20% wings it is -4% / -8% / -13% / -17%. Return falls about in proportion: Sharpe is 0.30 / 0.42 / 0.42 / 0.40 vs 0.41 naked. Skew makes the protective put relatively expensive (+2 to +10 vol pts over ATM), so the tightest wing (-5%) is the worst deal. Prefer -15% to -20% wings to remove the catastrophe while keeping most of the income.

## 6. Delta hedging

![hedging](figures/5_delta_hedging.png)

| Hedge | Return %/yr | Vol %/yr | Sharpe | Max DD % cap. | Worst qtr % | Qtrs up % |
|---|---|---|---|---|---|---|
| No hedge | 6.1 | 14.9 | 0.41 | 85 | -26.2 | 81 |
| Delta hedge daily | 0.5 | 2.6 | 0.19 | 17 | -6.7 | 63 |
| Delta hedge weekly | 0.7 | 3.4 | 0.20 | 14 | -9.4 | 63 |
| 50% delta hedge daily | 3.3 | 8.0 | 0.42 | 42 | -14.6 | 81 |
| Delta cap (hedge delta above entry) | 5.2 | 10.5 | 0.50 | 58 | -18.4 | 77 |
| Stop hedge (hedge while ITM) | 2.7 | 5.9 | 0.46 | 31 | -8.7 | 62 |

Sharpe ratio on each roll calendar (robustness):

| Hedge | Mar/Jun/Sep/Dec | Jan/Apr/Jul/Oct | Feb/May/Aug/Nov |
|---|---|---|---|
| No hedge | 0.41 | 0.41 | 0.50 |
| Delta hedge daily | 0.19 | 0.22 | 0.40 |
| Delta hedge weekly | 0.20 | 0.18 | 0.17 |
| 50% delta hedge daily | 0.42 | 0.42 | 0.53 |
| Delta cap (hedge delta above entry) | 0.50 | 0.45 | 0.59 |
| Stop hedge (hedge while ITM) | 0.46 | 0.36 | 0.52 |

* **Full delta hedge**: P&L ≈ ½·Γ·S²·(σ_implied² − σ_realized²). For 3-month NDX ATM options the implied-minus-realized gap averaged +1.1 vol pts (by decade: 1980s +2.5, 1990s +1.8, 2000s -0.7, 2010s +0.0, 2020s +3.8), so after costs very little is left. Hedging *put spreads* is negative because you are long the expensive skew.
* **Delta cap** keeps the original ~0.5 delta exposure (the equity premium is where the money came from) but stops the short put from getting *longer* as the market falls. That is the convexity that hurts in crashes.
* **Stop hedge** (hedge only while ITM) cuts drawdowns but whipsaws: it buys high and sells low around the strike.

## 7. Robustness and sensitivity

Return %/yr (Sharpe) under alternative assumptions:

| Scenario | Naked, fixed | Naked, recover | Spread -10%, fixed | Spread -10%, recover | Naked, delta-hedged, fixed |
|---|---|---|---|---|---|
| Base case | +6.1% (0.41) | +13.7% (0.39) | +3.1% (0.42) | +7.5% (0.31) | +0.5% (0.19) |
| Implied vol -10% | +4.2% (0.28) | +11.6% (0.24) | +2.8% (0.36) | wiped out 2008 | -1.4% (-0.57) |
| Implied vol +10% | +8.1% (0.54) | +15.3% (0.51) | +3.3% (0.47) | +7.7% (0.35) | +2.4% (0.84) |
| Flatter skew (alpha 0.15) | +6.1% (0.41) | +13.7% (0.38) | +3.9% (0.53) | +8.2% (0.39) | +0.6% (0.22) |
| Steeper skew (alpha 0.30) | +6.1% (0.42) | +13.7% (0.40) | +2.1% (0.30) | wiped out 2001 | +0.4% (0.15) |
| Zero trading costs | +6.6% (0.44) | +14.1% (0.41) | +3.9% (0.53) | +8.2% (0.38) | +1.1% (0.41) |
| Double trading costs | +5.7% (0.38) | +13.3% (0.37) | +2.3% (0.31) | wiped out 2002 | -0.1% (-0.03) |
| Cycle Jan/Apr/Jul/Oct | +6.4% (0.41) | wiped out 2001 | +1.6% (0.21) | wiped out 2001 | +0.6% (0.22) |
| Cycle Feb/May/Aug/Nov | +7.6% (0.50) | wiped out 2001 | +3.2% (0.44) | wiped out 2008 | +0.9% (0.40) |
| Only 2001+ (actual VXN) | +7.0% (0.49) | +13.6% (0.46) | +3.4% (0.45) | +7.4% (0.39) | +0.6% (0.26) |
| Only 2009+ (post-GFC) | +9.8% (0.80) | +13.6% (0.89) | +5.2% (0.72) | +8.0% (0.80) | +0.7% (0.33) |

Laddering (1/3 of the size on each monthly cycle) vs single calendars, fixed size, since 1990:

| Structure | Calendar | Return %/yr | Vol %/yr | Sharpe | Max DD % cap. |
|---|---|---|---|---|---|
| Naked ATM put | Mar/Jun/Sep/Dec | 6.5 | 14.9 | 0.44 | 85 |
| Naked ATM put | Jan/Apr/Jul/Oct | 6.8 | 15.6 | 0.43 | 76 |
| Naked ATM put | Feb/May/Aug/Nov | 8.2 | 15.5 | 0.53 | 73 |
| Naked ATM put | Ladder: 1/3 in each cycle | 7.1 | 14.9 | 0.48 | 77 |
| Put spread ATM/-10% | Mar/Jun/Sep/Dec | 3.3 | 7.4 | 0.44 | 36 |
| Put spread ATM/-10% | Jan/Apr/Jul/Oct | 2.0 | 7.7 | 0.26 | 53 |
| Put spread ATM/-10% | Feb/May/Aug/Nov | 3.5 | 7.5 | 0.46 | 49 |
| Put spread ATM/-10% | Ladder: 1/3 in each cycle | 2.9 | 7.0 | 0.41 | 46 |

Takeaways: the *level* of implied vol is the biggest unknown (±10% IV moves the naked put Sharpe from about 0.3 to 0.5 and flips the delta-hedged result's sign). The martingale's fate depends on the calendar and on small modelling choices; the fixed-size results do not.

## 8. Where we are now

As of 2026-11-02: NDX 27,990, VXN 30.9, estimated ATM IV 1M 28.0% / 3M 28.6%.

| Contract (indicative, model) | Days | NQ fut. | ATM IV | ATM put pts | % of notional | $ per NQ | -10% put pts | Spread -10% credit pts |
|---|---|---|---|---|---|---|---|---|
| 3-month (91d) ATM put | 91 | 28,220 | 28.6% | 1,592 | 5.64% | $31,840 | 701 | 891 |
| Dec-2026 quarterly (to 2026-12-18) | 46 | 28,106 | 28.3% | 1,122 | 3.99% | $22,443 | 360 | 762 |
| Mar-2027 quarterly (to 2027-03-19) | 137 | 28,338 | 28.6% | 1,951 | 6.89% | $39,024 | 989 | 962 |

Open backtest position: sold 2026-09-18, strike 29,888, expiry 2026-12-18. It is ITM by 1,782 pts, with model value 2,190 pts vs 1,206 collected.

Check these against live quotes before trading. The model ignores the current skew and term structure of NQ options specifically.

## 9. Start in 2008 with a 50% drawdown limit (in dollars)

*A $1,000,000 account from the first 2008 roll (2008-03-20). Every quarter it sells ATM puts on $1,000,000 of NQ notional (about 29 NQ in 2008, 1.7 NQ today). After a loss your rule makes the next put bigger to win the loss back, but never bigger than what a 45% NQ fall by expiry could lose without taking the account more than 50% below its high. 45% is the worst fall inside a quarter before 2008 (-36%, Oct 1987) plus a buffer for option prices jumping in a crash. Profits are not reinvested; a smaller account scales every dollar figure down in proportion (MNQ options are 1/10 of NQ).*

* **Puts that expired worthless:** 53 of 74 quarters, **$2,650,667** in total (about $50,013 per quarter).
* **Finished in the money but above breakeven:** 10 quarters, $254,849.
* **Finished in the money at a loss:** 11 quarters, **-$1,108,070** in total; the worst single quarter -$299,883.
* **Net:** $1,797,449; the account ends at $2,797,449.
* **Deepest cumulated loss** (still to win back at an expiry): **-$349,612** at the Dec 2008 expiry, back at a new high by the Jun 2011 expiry (11 quarters). On the worst day (2008-11-20) the open positions marked the account -$502,880 below its high, 46.5%: inside the 50% limit.
* The limit cut the recovery size in 18 quarters; the largest position was 2.66x the base.
* **Same limit, never upsizing:** ends at $2,456,487, deepest cumulated loss -$299,245, worst day 39.9% down.
* **Your rule without the limit:** ends at $3,426,804 but was -$896,676 (83%) down on 2009-03-09, far past 50%.
* On the other two roll calendars the limit also held: worst day 46.5% (Mar/Jun/Sep/Dec), 34.8% (Jan/Apr/Jul/Oct), 41.1% (Feb/May/Aug/Nov).

![USD ledger](figures/6_usd_2008_dd50.png)

| Year (expiries) | Quarters | Expired worthless | Profit, expired worthless | Profit, ITM above breakeven | Losses | Worst cumulated loss | Account at year end |
|---|---|---|---|---|---|---|---|
| 2008 | 3 | 1 | $52,657 | $0 | -$349,611 | -$349,612 | $703,046 |
| 2009 | 4 | 3 | $112,228 | $25,360 | $0 | -$324,251 | $840,635 |
| 2010 | 4 | 3 | $120,852 | $21,772 | $0 | -$179,781 | $983,259 |
| 2011 | 4 | 2 | $80,991 | $70,419 | $0 | -$29,989 | $1,134,668 |
| 2012 | 4 | 2 | $104,573 | $0 | -$53,138 | -$40,139 | $1,186,104 |
| 2013 | 4 | 4 | $127,641 | $0 | $0 | $0 | $1,313,744 |
| 2014 | 4 | 4 | $102,887 | $0 | $0 | $0 | $1,416,632 |
| 2015 | 4 | 3 | $114,834 | $0 | -$14,064 | -$14,064 | $1,517,401 |
| 2016 | 4 | 2 | $65,397 | $44,414 | $0 | $0 | $1,627,213 |
| 2017 | 4 | 4 | $101,306 | $0 | $0 | $0 | $1,728,520 |
| 2018 | 4 | 3 | $85,917 | $0 | -$165,867 | -$165,867 | $1,648,570 |
| 2019 | 4 | 4 | $236,964 | $0 | $0 | -$71,623 | $1,885,534 |
| 2020 | 4 | 3 | $412,678 | $0 | -$167,896 | -$167,896 | $2,130,316 |
| 2021 | 4 | 4 | $202,383 | $0 | $0 | $0 | $2,332,699 |
| 2022 | 4 | 1 | $157,029 | $8,927 | -$290,327 | -$290,327 | $2,208,329 |
| 2023 | 4 | 3 | $226,834 | $36,917 | $0 | $0 | $2,472,080 |
| 2024 | 4 | 3 | $107,453 | $24,715 | $0 | $0 | $2,604,248 |
| 2025 | 4 | 3 | $159,582 | $0 | -$40,707 | -$40,707 | $2,723,123 |
| 2026 | 3 | 1 | $78,461 | $22,325 | -$26,460 | -$26,460 | $2,797,449 |

Every quarter (USD):

| Sold | Expires | NQ puts sold | Premium collected | Outcome | Profit | Loss | Cumulated loss to win back | Account |
|---|---|---|---|---|---|---|---|---|
| 2008-03-20 | 2008-06-20 | 28.54 | $52,657 | expired worthless | $52,657 |  | $0 | $1,052,657 |
| 2008-06-20 | 2008-09-19 | 25.86 | $47,886 | in the money, loss |  | -$49,728 | -$49,728 | $1,002,929 |
| 2008-09-19 | 2008-12-19 | 34.41 | $64,235 | in the money, loss |  | -$299,883 | -$349,612 | $703,046 |
| 2008-12-19 | 2009-03-20 | 19.47 | $36,245 | in the money, still a profit | $25,360 |  | -$324,251 | $728,406 |
| 2009-03-20 | 2009-06-19 | 23.17 | $45,160 | expired worthless | $45,160 |  | -$279,091 | $773,566 |
| 2009-06-19 | 2009-09-18 | 21.27 | $33,994 | expired worthless | $33,994 |  | -$245,097 | $807,560 |
| 2009-09-18 | 2009-12-18 | 20.27 | $33,074 | expired worthless | $33,074 |  | -$212,023 | $840,635 |
| 2009-12-18 | 2010-03-19 | 21.34 | $32,242 | expired worthless | $32,242 |  | -$179,781 | $872,877 |
| 2010-03-19 | 2010-06-18 | 21.61 | $28,839 | in the money, still a profit | $21,772 |  | -$158,009 | $894,648 |
| 2010-06-18 | 2010-09-17 | 24.01 | $44,626 | expired worthless | $44,626 |  | -$113,383 | $939,275 |
| 2010-09-17 | 2010-12-17 | 25.99 | $43,984 | expired worthless | $43,984 |  | -$69,399 | $983,259 |
| 2010-12-17 | 2011-03-18 | 24.90 | $39,410 | expired worthless | $39,410 |  | -$29,989 | $1,022,668 |
| 2011-03-18 | 2011-06-17 | 27.71 | $56,757 | in the money, still a profit | $43,109 |  | $0 | $1,065,777 |
| 2011-06-17 | 2011-09-16 | 22.84 | $41,581 | expired worthless | $41,581 |  | $0 | $1,107,358 |
| 2011-09-16 | 2011-12-16 | 21.72 | $55,087 | in the money, still a profit | $27,310 |  | $0 | $1,134,668 |
| 2011-12-16 | 2012-03-16 | 22.38 | $48,261 | expired worthless | $48,261 |  | $0 | $1,182,929 |
| 2012-03-16 | 2012-06-15 | 18.46 | $37,738 | in the money, loss |  | -$12,999 | -$12,999 | $1,169,931 |
| 2012-06-15 | 2012-09-21 | 25.32 | $56,312 | expired worthless | $56,312 |  | $0 | $1,226,243 |
| 2012-09-21 | 2012-12-21 | 17.50 | $27,322 | in the money, loss |  | -$40,139 | -$40,139 | $1,186,104 |
| 2012-12-21 | 2013-03-15 | 25.90 | $47,287 | expired worthless | $47,287 |  | $0 | $1,233,391 |
| 2013-03-15 | 2013-06-21 | 17.89 | $23,727 | expired worthless | $23,727 |  | $0 | $1,257,117 |
| 2013-06-21 | 2013-09-20 | 17.40 | $33,426 | expired worthless | $33,426 |  | $0 | $1,290,544 |
| 2013-09-20 | 2013-12-20 | 15.53 | $23,201 | expired worthless | $23,201 |  | $0 | $1,313,744 |
| 2013-12-20 | 2014-03-21 | 14.18 | $24,781 | expired worthless | $24,781 |  | $0 | $1,338,526 |
| 2014-03-21 | 2014-06-20 | 13.71 | $30,601 | expired worthless | $30,601 |  | $0 | $1,369,127 |
| 2014-06-20 | 2014-09-19 | 13.17 | $21,965 | expired worthless | $21,965 |  | $0 | $1,391,092 |
| 2014-09-19 | 2014-12-19 | 12.22 | $25,540 | expired worthless | $25,540 |  | $0 | $1,416,632 |
| 2014-12-19 | 2015-03-20 | 11.70 | $30,804 | expired worthless | $30,804 |  | $0 | $1,447,436 |
| 2015-03-20 | 2015-06-19 | 11.23 | $27,724 | expired worthless | $27,724 |  | $0 | $1,475,160 |
| 2015-06-19 | 2015-09-18 | 11.10 | $26,286 | in the money, loss |  | -$14,064 | -$14,064 | $1,461,096 |
| 2015-09-18 | 2015-12-18 | 15.44 | $56,306 | expired worthless | $56,306 |  | $0 | $1,517,401 |
| 2015-12-18 | 2016-03-18 | 11.09 | $37,425 | in the money, still a profit | $15,633 |  | $0 | $1,533,034 |
| 2016-03-18 | 2016-06-17 | 11.35 | $36,031 | in the money, still a profit | $28,781 |  | $0 | $1,561,816 |
| 2016-06-17 | 2016-09-16 | 11.44 | $37,364 | expired worthless | $37,364 |  | $0 | $1,599,179 |
| 2016-09-16 | 2016-12-16 | 10.39 | $28,033 | expired worthless | $28,033 |  | $0 | $1,627,213 |
| 2016-12-16 | 2017-03-17 | 10.18 | $26,065 | expired worthless | $26,065 |  | $0 | $1,653,278 |
| 2017-03-17 | 2017-06-16 | 9.24 | $18,767 | expired worthless | $18,767 |  | $0 | $1,672,045 |
| 2017-06-16 | 2017-09-15 | 8.79 | $32,265 | expired worthless | $32,265 |  | $0 | $1,704,310 |
| 2017-09-15 | 2017-12-15 | 8.34 | $24,209 | expired worthless | $24,209 |  | $0 | $1,728,520 |
| 2017-12-15 | 2018-03-16 | 7.72 | $22,781 | expired worthless | $22,781 |  | $0 | $1,751,301 |
| 2018-03-16 | 2018-06-15 | 7.10 | $32,398 | expired worthless | $32,398 |  | $0 | $1,783,699 |
| 2018-06-15 | 2018-09-21 | 6.87 | $30,738 | expired worthless | $30,738 |  | $0 | $1,814,437 |
| 2018-09-21 | 2018-12-21 | 6.62 | $34,128 | in the money, loss |  | -$165,867 | -$165,867 | $1,648,570 |
| 2018-12-21 | 2019-03-15 | 15.30 | $94,244 | expired worthless | $94,244 |  | -$71,623 | $1,742,814 |
| 2019-03-15 | 2019-06-21 | 13.52 | $57,394 | expired worthless | $57,394 |  | -$14,228 | $1,800,209 |
| 2019-06-21 | 2019-09-20 | 9.11 | $48,654 | expired worthless | $48,654 |  | $0 | $1,848,862 |
| 2019-09-20 | 2019-12-20 | 6.37 | $36,672 | expired worthless | $36,672 |  | $0 | $1,885,534 |
| 2019-12-20 | 2020-03-20 | 5.75 | $27,876 | in the money, loss |  | -$167,896 | -$167,896 | $1,717,638 |
| 2020-03-20 | 2020-06-19 | 16.71 | $275,608 | expired worthless | $275,608 |  | $0 | $1,993,246 |
| 2020-06-19 | 2020-09-18 | 5.00 | $60,586 | expired worthless | $60,586 |  | $0 | $2,053,832 |
| 2020-09-18 | 2020-12-18 | 4.58 | $76,484 | expired worthless | $76,484 |  | $0 | $2,130,316 |
| 2020-12-18 | 2021-03-19 | 3.93 | $54,945 | expired worthless | $54,945 |  | $0 | $2,185,262 |
| 2021-03-19 | 2021-06-18 | 3.89 | $62,555 | expired worthless | $62,555 |  | $0 | $2,247,816 |
| 2021-06-18 | 2021-09-17 | 3.56 | $42,458 | expired worthless | $42,458 |  | $0 | $2,290,274 |
| 2021-09-17 | 2021-12-17 | 3.27 | $42,425 | expired worthless | $42,425 |  | $0 | $2,332,699 |
| 2021-12-17 | 2022-03-18 | 3.17 | $54,588 | in the money, loss |  | -$31,353 | -$31,353 | $2,301,347 |
| 2022-03-18 | 2022-06-17 | 5.48 | $85,503 | in the money, loss |  | -$258,974 | -$290,327 | $2,042,373 |
| 2022-06-17 | 2022-09-16 | 10.17 | $157,029 | expired worthless | $157,029 |  | -$133,297 | $2,199,402 |
| 2022-09-16 | 2022-12-16 | 11.13 | $162,269 | in the money, still a profit | $8,927 |  | -$124,370 | $2,208,329 |
| 2022-12-16 | 2023-03-17 | 11.56 | $138,201 | expired worthless | $138,201 |  | $0 | $2,346,530 |
| 2023-03-17 | 2023-06-16 | 3.96 | $53,025 | expired worthless | $53,025 |  | $0 | $2,399,555 |
| 2023-06-16 | 2023-09-15 | 3.28 | $40,034 | in the money, still a profit | $36,917 |  | $0 | $2,436,472 |
| 2023-09-15 | 2023-12-15 | 3.25 | $35,608 | expired worthless | $35,608 |  | $0 | $2,472,080 |
| 2023-12-15 | 2024-03-15 | 2.97 | $30,174 | expired worthless | $30,174 |  | $0 | $2,502,254 |
| 2024-03-15 | 2024-06-21 | 2.77 | $37,500 | expired worthless | $37,500 |  | $0 | $2,539,754 |
| 2024-06-21 | 2024-09-20 | 2.51 | $31,375 | in the money, still a profit | $24,715 |  | $0 | $2,564,469 |
| 2024-09-20 | 2024-12-20 | 2.50 | $39,779 | expired worthless | $39,779 |  | $0 | $2,604,248 |
| 2024-12-20 | 2025-03-21 | 2.33 | $39,534 | in the money, loss |  | -$40,707 | -$40,707 | $2,563,541 |
| 2025-03-21 | 2025-06-20 | 5.00 | $81,722 | expired worthless | $81,722 |  | $0 | $2,645,263 |
| 2025-06-20 | 2025-09-19 | 2.29 | $40,927 | expired worthless | $40,927 |  | $0 | $2,686,191 |
| 2025-09-19 | 2025-12-19 | 2.01 | $36,933 | expired worthless | $36,933 |  | $0 | $2,723,123 |
| 2025-12-19 | 2026-03-20 | 1.96 | $37,322 | in the money, loss |  | -$26,460 | -$26,460 | $2,696,663 |
| 2026-03-20 | 2026-06-18 | 3.13 | $78,461 | expired worthless | $78,461 |  | $0 | $2,775,124 |
| 2026-06-18 | 2026-09-18 | 1.63 | $54,657 | in the money, still a profit | $22,325 |  | $0 | $2,797,449 |
| 2026-09-18 | 2026-12-18 | 1.67 | $39,348 | open (marked to market) |  | -$33,928 | -$33,928 | $2,763,521 |

CSV: [`results/usd_ledger_2008_dd50_recover.csv`](../results/usd_ledger_2008_dd50_recover.csv) (fixed-size version: `usd_ledger_2008_dd50_fixed.csv`).

## 10. Limitations

* Premiums are reconstructed from VXN/VIX, not traded quotes. Error is probably ±10% of premium, and larger before 2001 (VXN proxy) and before 1990 (VXO-based). NQ options did not exist before ~1999-2000; earlier years are a hypothetical on the index.
* Settlement uses the expiry-day close. Real quarterly NQ options settle to the Friday-morning SOQ, and early exercise of American-style quarterlies is ignored.
* The skew is a fixed parametric shape. In real crashes the skew and the term structure move, which matters for spread marks and hedge ratios (but not for expiry payoffs).
* Returns are excess of cash: collateral would also earn T-bill interest (~3% avg). Taxes are ignored.
* Margin is approximate. SPAN margin can jump in a crash, and that is exactly when the martingale needs more of it.

## 11. Reproduce

```bash
pip install -r requirements.txt
python run_backtest.py --refresh   # downloads data, ~30 s
```

Outputs: `results/*.csv` (grid of 200+ strategy variants, premium history, sensitivities), `reports/figures/*.png`, and this report.
