#!/usr/bin/env python3
"""Run the full NQ 3-month ATM put-selling study.

    python run_backtest.py            # use cached data in data/raw (downloads if missing)
    python run_backtest.py --refresh  # re-download all market data first

Outputs: results/*.csv|json (tables), reports/figures/*.png, reports/REPORT.md
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pandas as pd

from nqput import analysis as A
from nqput.backtest import MarketParams
from nqput.data import download_all, load_market_data
from nqput.volmodel import VolParams

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"
RES = ROOT / "results"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="re-download market data")
    ap.add_argument("--no-report", action="store_true", help="skip charts and markdown report")
    args = ap.parse_args()
    t0 = time.time()
    RES.mkdir(exist_ok=True)

    print("1/8 data")
    download_all(RAW, refresh=args.refresh)
    df = load_market_data(RAW)

    print("2/8 vol model + cycles")
    vp, mp = VolParams(), MarketParams()
    ctx = A.Context(df, vp, mp)
    (RES / "vol_model_fit.json").write_text(json.dumps(ctx.diag, indent=2, default=str))
    # model output only (raw vendor series are not redistributed); weekly to keep the file small
    ivs = ctx.vol[["vxn_src", "ts_ratio", "atm1m", "atm3m"]].rename(columns={"vxn_src": "iv_source"})
    ivs = ivs[ivs.index >= "1986-01-01"]
    ivs[ivs.index.weekday == 4].round(4).to_csv(RES / "implied_vol_weekly_model.csv")

    print("3/8 premium history")
    pt = A.premium_table(ctx)
    pt.to_csv(RES / "premiums_quarterly.csv", index=False)
    A.premium_by_year(pt).to_csv(RES / "premiums_by_year.csv")

    print("4/8 strategy grid")
    grid, runs = A.strategy_grid(ctx)
    grid.round(4).to_csv(RES / "strategy_grid.csv", index=False)
    grid01, _ = A.strategy_grid(ctx, start="2001-03-01")
    grid01.round(4).to_csv(RES / "strategy_grid_2001plus.csv", index=False)
    keep = {
        (A.NAKED.name, A.NO_HEDGE.name, A.FIXED.name), (A.NAKED.name, A.NO_HEDGE.name, A.RECOVER.name),
        (A.STRUCTURES[2].name, A.NO_HEDGE.name, A.RECOVER.name),
    }
    for key, res in runs.items():
        if key in keep:
            slug = "__".join(k.replace(" ", "_").replace("/", "").replace("%", "pct") for k in key)
            res.cycles.to_csv(RES / f"cycles__{slug}.csv", index=False)
    key_eq = {" | ".join(k): r.daily for k, r in runs.items()
              if k[1] == A.NO_HEDGE.name and k[2] in (A.FIXED.name, A.RECOVER.name)
              or (k[0] == A.NAKED.name and k[2] == A.FIXED.name)}
    eq = pd.DataFrame(key_eq)
    eq[eq.index.weekday == 4].round(0).to_csv(RES / "equity_weekly_key_strategies.csv")

    print("5/8 recovery sizing by start year")
    pairs = [(A.NAKED, A.NO_HEDGE, A.FIXED), (A.NAKED, A.NO_HEDGE, A.RECOVER),
             (A.STRUCTURES[2], A.NO_HEDGE, A.FIXED), (A.STRUCTURES[2], A.NO_HEDGE, A.RECOVER),
             (A.STRUCTURES[4], A.NO_HEDGE, A.RECOVER),
             (A.NAKED, A.NO_HEDGE, A.SIZINGS[2]), (A.NAKED, A.NO_HEDGE, A.SIZINGS[6])]
    sy = A.start_year_table(ctx, pairs, range(1987, 2025))
    sy.round(3).to_csv(RES / "start_year_robustness.csv", index=False)

    print("6/8 sensitivity + ladder")
    sens = A.sensitivity(df, vp, mp)
    sens.round(4).to_csv(RES / "sensitivity.csv", index=False)
    lad = A.ladder_table(df, vp, mp)
    lad.round(4).to_csv(RES / "cycle_offsets_ladder.csv", index=False)
    cal, cal_runs = A.calendar_table(df, vp, mp)
    cal.round(4).to_csv(RES / "calendar_robustness.csv", index=False)
    pao = A.premium_after_outcome(pt)
    pao.round(3).to_csv(RES / "premium_after_outcome.csv")

    print("7/8 live snapshot")
    snap = A.live_snapshot(ctx)
    (RES / "live_snapshot.json").write_text(json.dumps(snap, indent=2, default=float))

    print("8/8 start 2008 with a 50% drawdown limit (USD ledger)")
    usd = A.usd_scenario(df, vp, mp)
    usd["ledger"].to_csv(RES / "usd_ledger_2008_dd50_recover.csv", index=False)
    usd["ledger_fixed"].to_csv(RES / "usd_ledger_2008_dd50_fixed.csv", index=False)
    usd["by_year"].to_csv(RES / "usd_ledger_2008_dd50_by_year.csv")
    usd["calendars"].round(2).to_csv(RES / "usd_2008_dd50_calendars.csv", index=False)
    (RES / "usd_2008_dd50_summary.json").write_text(json.dumps(
        {"recover_dd50": usd["summary"], "fixed_dd50": usd["summary_fixed"], "recover_no_limit": usd["summary_no_limit"]},
        indent=2, default=float))

    if not args.no_report:
        from nqput import report
        report.build(ROOT, df, ctx, runs, grid, grid01, pt, sy, sens, lad, cal, cal_runs, pao, snap, usd)
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
