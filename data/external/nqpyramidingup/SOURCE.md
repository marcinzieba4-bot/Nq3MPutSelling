# Inputs from the NQ pyramid study

Copied unchanged from `marcinzieba4-bot/NQPyramidingUP`, branch `claude/peaceful-sagan-8ooc7x`,
commit `bd90a7c` ("Chosen version (recovery 70% / +20% reset) with 20-delta calls at $100k per unit"),
folder `results/best_calls/`.

* `equity_daily.csv`: cumulative P&L in USD per $100k unit (never reinvested), daily, 2008-01-02 to
  2026-11-02, for "no calls", "sell 20-delta 30-day calls" and "sell 20-delta 7-day calls" (calls priced
  at 0.9 x VXN, the base case).
* `trades.csv`: every pyramid trade of the 7-day-calls run, with fractional NQ contracts per $100k unit
  (used to rebuild the position, and so the margin, held each day).
* `summary.csv`: that study's own statistics (on its intraday data), for reference.

Used by `nqput/combo.py` (step 9 of `run_backtest.py`). Replace these files to update the combination.
