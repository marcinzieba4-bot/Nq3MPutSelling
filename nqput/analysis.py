"""Strategy grid, premium history, robustness and sensitivity analyses."""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from .backtest import (NQ_MULT, Cycle, Hedge, MarketParams, RunResult, Sizing, Structure, UnitCycle,
                       build_cycles, metrics, run_sizing, unit_cycle)
from .black76 import put_delta, put_price
from .volmodel import VolParams, atm_vol_for_tau, build_vol_inputs, strike_vol

NAKED = Structure("Naked ATM put")
STRUCTURES = [
    NAKED,
    Structure("Put spread ATM/-5%", long_otm=0.05),
    Structure("Put spread ATM/-10%", long_otm=0.10),
    Structure("Put spread ATM/-15%", long_otm=0.15),
    Structure("Put spread ATM/-20%", long_otm=0.20),
]
BENCH = Structure("Long NQ futures 1x", kind="long_futures")

NO_HEDGE = Hedge("No hedge")
HEDGES = [
    NO_HEDGE,
    Hedge("Delta hedge daily", "full", every=1),
    Hedge("Delta hedge weekly", "full", every=5),
    Hedge("50% delta hedge daily", "full", every=1, ratio=0.5),
    Hedge("Delta cap (hedge delta above entry)", "cap", every=1),
    Hedge("Stop hedge (hedge while ITM)", "itm", every=1),
]

FIXED = Sizing("Fixed 1x")
RECOVER = Sizing("Recover until whole", "recover")
SIZINGS = [
    FIXED,
    RECOVER,
    Sizing("Recover once", "recover_once"),
    Sizing("Recover, max 3x", "recover", max_mult=3.0),
    Sizing("Recover over 4 quarters", "recover", recover_quarters=4),
    Sizing("Fixed + 200d trend filter", trend_filter=True),
    Sizing("Recover + 200d trend filter", "recover", trend_filter=True),
]


class Context:
    """Holds data, vol inputs and cycles for one parameter set."""

    def __init__(self, df: pd.DataFrame, vp: VolParams | None = None, mp: MarketParams | None = None,
                 months=(3, 6, 9, 12), start="1986-03-01"):
        self.df = df
        self.vp = vp or VolParams()
        self.mp = mp or MarketParams()
        self.vol, self.diag = build_vol_inputs(df, self.vp)
        self.cycles = build_cycles(df, self.vol, months, start, self.mp)
        self._units: dict[tuple[str, str], list[UnitCycle]] = {}

    def units(self, st: Structure, hd: Hedge) -> list[UnitCycle]:
        key = (st.name, hd.name)
        if key not in self._units:
            self._units[key] = [unit_cycle(c, st, hd, self.mp, self.vp) for c in self.cycles]
        return self._units[key]

    def run(self, st: Structure, hd: Hedge, sz: Sizing, start: str | None = None) -> RunResult:
        us = self.units(st, hd)
        if start is not None:
            us = [u for u in us if u.cycle.entry >= pd.Timestamp(start)]
        name = f"{st.name} | {hd.name} | {sz.name}"
        return run_sizing(us, sz, self.mp, name)


def _fmt_metrics(m: dict, st: Structure, hd: Hedge, sz: Sizing) -> dict:
    return {"structure": st.name, "hedge": hd.name, "sizing": sz.name, **m}


def strategy_grid(ctx: Context, structures=STRUCTURES, hedges=HEDGES, sizings=SIZINGS,
                  start: str | None = None) -> tuple[pd.DataFrame, dict]:
    rows, runs = [], {}
    for st in structures:
        for hd in hedges:
            for sz in sizings:
                res = ctx.run(st, hd, sz, start)
                runs[(st.name, hd.name, sz.name)] = res
                rows.append(_fmt_metrics(metrics(res, ctx.mp), st, hd, sz))
    for sz in [FIXED]:
        res = ctx.run(BENCH, NO_HEDGE, sz, start)
        runs[(BENCH.name, NO_HEDGE.name, sz.name)] = res
        rows.append(_fmt_metrics(metrics(res, ctx.mp), BENCH, NO_HEDGE, sz))
    return pd.DataFrame(rows), runs


# ----------------------------------------------------------------------------- premiums
def premium_table(ctx: Context) -> pd.DataFrame:
    """One row per quarterly roll: the estimated 3M ATM put premium and its outcome."""
    naked = ctx.units(NAKED, NO_HEDGE)
    ps10 = ctx.units(STRUCTURES[2], NO_HEDGE)
    ps20 = ctx.units(STRUCTURES[4], NO_HEDGE)
    rows = []
    for u, u10, u20 in zip(naked, ps10, ps20):
        c, i = u.cycle, u.info
        F0, K = i["F0"], i["K1"]
        prem = i["prem1_mid"]
        payoff = max(K - c.S[-1], 0.0) if not c.open else np.nan
        rows.append({
            "entry": c.entry.date(), "expiry": c.expiry.date(), "days": (c.expiry - c.entry).days,
            "status": "open" if c.open else "settled", "iv_source": c.src,
            "ndx_entry": round(c.S[0], 2), "futures_entry": round(F0, 2), "strike_atm": round(K, 2),
            "atm_iv_3m_pct": round(100 * i["iv1"], 2),
            "put_premium_pts": round(prem, 2), "put_premium_pct": round(100 * prem / F0, 3),
            "put_premium_usd_per_NQ": round(prem * NQ_MULT, 0),
            "otm10_iv_pct": round(100 * u10.info["iv2"], 2),
            "otm10_put_pts": round(u10.info["prem2_mid"], 2),
            "spread10_net_credit_pct": round(100 * u10.credit / F0, 3),
            "otm20_put_pts": round(u20.info["prem2_mid"], 2),
            "spread20_net_credit_pct": round(100 * u20.credit / F0, 3),
            "ndx_at_expiry": round(c.S[-1], 2) if not c.open else np.nan,
            "ndx_move_pct": round(100 * (c.S[-1] / c.S[0] - 1), 2),
            "expired_itm": bool(c.S[-1] < K) if not c.open else None,
            "payoff_pts": round(payoff, 2),
            "naked_pnl_pct_notional": round(100 * u.ret.sum(), 3),
            "spread10_pnl_pct_notional": round(100 * u10.ret.sum(), 3),
            "spread20_pnl_pct_notional": round(100 * u20.ret.sum(), 3),
        })
    return pd.DataFrame(rows)


def premium_by_year(pt: pd.DataFrame) -> pd.DataFrame:
    """Aggregate by EXPIRY year: the 4 quarterly puts expiring Mar/Jun/Sep/Dec of that year
    (sold Dec of the prior year .. Sep), i.e. roughly one calendar year of selling."""
    x = pt[pt.status == "settled"].copy()
    x["year"] = pd.to_datetime(x.expiry).dt.year
    g = x.groupby("year")
    out = pd.DataFrame({
        "rolls": g.size(),
        "avg_atm_iv_3m_pct": g.atm_iv_3m_pct.mean(),
        "avg_premium_pct": g.put_premium_pct.mean(),
        "avg_premium_usd_per_NQ": g.put_premium_usd_per_NQ.mean(),
        "premium_collected_pct": g.put_premium_pct.sum(),
        "expired_itm": g.expired_itm.sum().astype(int),
        "naked_pnl_pct": g.naked_pnl_pct_notional.sum(),
        "spread10_pnl_pct": g.spread10_pnl_pct_notional.sum(),
        "ndx_move_pct": g.ndx_move_pct.apply(lambda s: 100 * (np.prod(1 + s / 100) - 1)),
    })
    return out.round(2)


# ----------------------------------------------------------------------------- robustness
def start_year_table(ctx: Context, pairs, years) -> pd.DataFrame:
    rows = []
    for y in years:
        start = f"{y}-01-01"
        for st, hd, sz in pairs:
            res = ctx.run(st, hd, sz, start)
            m = metrics(res, ctx.mp)
            rows.append({"start_year": y, "strategy": f"{st.name} | {hd.name} | {sz.name}",
                         "ann_return_pct": m["ann_return_pct"], "max_dd_pct_capital": m["max_dd_pct_capital"],
                         "worst_quarter_pct": m["worst_quarter_pct"], "max_mult": m["max_mult"],
                         "ruined": m["ruined"], "final_equity": m["final_equity"]})
    return pd.DataFrame(rows)


def sensitivity(df: pd.DataFrame, base_vp: VolParams, base_mp: MarketParams) -> pd.DataFrame:
    """Re-run key strategies under alternative assumptions."""
    combos = [
        (NAKED, NO_HEDGE, FIXED), (NAKED, NO_HEDGE, RECOVER),
        (STRUCTURES[2], NO_HEDGE, FIXED), (STRUCTURES[2], NO_HEDGE, RECOVER),
        (NAKED, HEDGES[1], FIXED),
    ]
    scenarios = [
        ("Base case", {}, {}, (3, 6, 9, 12), "1986-03-01"),
        ("Implied vol -10%", {"iv_scale": 0.9}, {}, (3, 6, 9, 12), "1986-03-01"),
        ("Implied vol +10%", {"iv_scale": 1.1}, {}, (3, 6, 9, 12), "1986-03-01"),
        ("Flatter skew (alpha 0.15)", {"skew_alpha": 0.15}, {}, (3, 6, 9, 12), "1986-03-01"),
        ("Steeper skew (alpha 0.30)", {"skew_alpha": 0.30}, {}, (3, 6, 9, 12), "1986-03-01"),
        ("Zero trading costs", {}, {"opt_slip_vol": 0.0, "opt_comm_pts": 0.0, "fut_cost_bp": 0.0},
         (3, 6, 9, 12), "1986-03-01"),
        ("Double trading costs", {}, {"opt_slip_vol": 0.01, "opt_comm_pts": 0.25, "fut_cost_bp": 2.0},
         (3, 6, 9, 12), "1986-03-01"),
        ("Cycle Jan/Apr/Jul/Oct", {}, {}, (1, 4, 7, 10), "1986-01-01"),
        ("Cycle Feb/May/Aug/Nov", {}, {}, (2, 5, 8, 11), "1986-01-01"),
        ("Only 2001+ (actual VXN)", {}, {}, (3, 6, 9, 12), "2001-03-01"),
        ("Only 2009+ (post-GFC)", {}, {}, (3, 6, 9, 12), "2009-03-01"),
    ]
    rows = []
    for name, vkw, mkw, months, start in scenarios:
        vp = replace(base_vp, **vkw)
        mp = replace(base_mp, **mkw)
        ctx = Context(df, vp, mp, months, start)
        for st, hd, sz in combos:
            m = metrics(ctx.run(st, hd, sz), mp)
            rows.append({"scenario": name, "strategy": f"{st.name} | {hd.name} | {sz.name}",
                         **{k: m[k] for k in ["start", "quarters", "ann_return_pct", "ann_vol_pct", "sharpe",
                                              "max_dd_pct_capital", "worst_quarter_pct", "max_mult", "ruined"]}})
    return pd.DataFrame(rows)


def ladder_table(df: pd.DataFrame, vp: VolParams, mp: MarketParams) -> pd.DataFrame:
    """Fixed-size results for each monthly offset of the 3-month cycle and for a 1/3-each ladder."""
    fams = {"Mar/Jun/Sep/Dec": (3, 6, 9, 12), "Jan/Apr/Jul/Oct": (1, 4, 7, 10), "Feb/May/Aug/Nov": (2, 5, 8, 11)}
    rows, eqs = [], {}
    for st in [NAKED, STRUCTURES[2]]:
        daily = []
        for fname, months in fams.items():
            ctx = Context(df, vp, mp, months, "1990-01-01")
            res = ctx.run(st, NO_HEDGE, FIXED)
            m = metrics(res, mp)
            rows.append({"structure": st.name, "cycle": fname, **{k: m[k] for k in [
                "start", "ann_return_pct", "ann_vol_pct", "sharpe", "max_dd_pct_capital", "worst_quarter_pct"]}})
            daily.append(res.daily.diff().fillna(res.daily.iloc[0] - mp.capital))
        lad = pd.concat(daily, axis=1).fillna(0).sum(axis=1) / 3.0
        lad = lad[lad.index >= max(d.index[0] for d in daily)]
        eq = mp.capital + lad.cumsum()
        yrs = (eq.index[-1] - eq.index[0]).days / 365.25
        ann = (eq.iloc[-1] - mp.capital) / mp.capital / yrs
        vol = (eq.diff().dropna() / mp.capital).std() * np.sqrt(252)
        dd = ((eq.cummax() - eq) / mp.capital).max()
        rows.append({"structure": st.name, "cycle": "Ladder: 1/3 in each cycle", "start": eq.index[0].date(),
                     "ann_return_pct": 100 * ann, "ann_vol_pct": 100 * vol, "sharpe": ann / vol,
                     "max_dd_pct_capital": 100 * dd, "worst_quarter_pct": np.nan})
        eqs[st.name] = eq
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- live snapshot
def live_snapshot(ctx: Context) -> dict:
    """Status of the open position and indicative premium for a new 3M ATM put now."""
    df, vol, vp, mp = ctx.df, ctx.vol, ctx.vp, ctx.mp
    last = df.index[-1]
    S, r = float(df.ndx.iloc[-1]), float(df.rf.iloc[-1])
    a1, a3 = float(vol.atm1m.iloc[-1]), float(vol.atm3m.iloc[-1])
    out = {"as_of": str(last.date()), "ndx": S, "vxn": float(df.vxn.iloc[-1]), "atm_iv_1m": a1, "atm_iv_3m": a3,
           "ts_ratio": float(vol.ts_ratio.iloc[-1])}
    open_c = [c for c in ctx.cycles if c.open]
    if open_c:
        c = open_c[0]
        u = ctx.units(NAKED, NO_HEDGE)[-1]
        K = u.info["K1"]
        tau = (c.expiry - last).days / 365.0
        F = S * np.exp((r - mp.div_yield) * tau)
        sig = float(strike_vol(np.array([c.atm[-1]]), np.array([F]), K, np.array([tau]), vp)[0])
        out["open_position"] = {
            "entry": str(c.entry.date()), "expiry": str(c.expiry.date()), "strike": K,
            "premium_pts": u.info["prem1_mid"], "premium_usd_per_NQ": u.info["prem1_mid"] * NQ_MULT,
            "futures_now": F, "days_left": int(round(tau * 365)), "iv_now": sig,
            "put_value_now_pts": float(put_price(F, K, tau, r, sig)),
            "pnl_to_date_pts": float(u.ret.sum() * u.cycle.F0),
            "delta_now": float(-put_delta(F, K, tau, r, sig)),
            "intrinsic_pts": max(K - F, 0.0),
        }
    quotes = []
    for label, days in [("3-month (91d) ATM put", 91), ("Dec-2026 quarterly (to 2026-12-18)", (pd.Timestamp("2026-12-18") - last).days),
                        ("Mar-2027 quarterly (to 2027-03-19)", (pd.Timestamp("2027-03-19") - last).days)]:
        tau = days / 365.0
        F = S * np.exp((r - mp.div_yield) * tau)
        atm = float(atm_vol_for_tau(np.array([a1]), np.array([a3]), np.array([float(days)]))[0])
        p = float(put_price(F, F, tau, r, atm * vp.iv_scale))
        k10 = F * 0.9
        s10 = float(strike_vol(np.array([atm]), np.array([F]), k10, np.array([tau]), vp)[0])
        p10 = float(put_price(F, k10, tau, r, s10))
        quotes.append({"contract": label, "days": days, "futures": F, "atm_iv": atm, "atm_put_pts": p,
                       "atm_put_pct": p / F, "atm_put_usd_per_NQ": p * NQ_MULT,
                       "otm10_put_pts": p10, "spread10_credit_pts": p - p10, "otm10_iv": s10})
    out["indicative_quotes"] = quotes
    return out


CALENDARS = {"Mar/Jun/Sep/Dec": ((3, 6, 9, 12), "1986-03-01"),
             "Jan/Apr/Jul/Oct": ((1, 4, 7, 10), "1986-01-01"),
             "Feb/May/Aug/Nov": ((2, 5, 8, 11), "1986-01-01")}


def calendar_table(df: pd.DataFrame, vp: VolParams, mp: MarketParams):
    """Every sizing rule and hedge on all three 3-month roll calendars (timing-luck check)."""
    rows, runs = [], {}
    for cal, (months, start) in CALENDARS.items():
        ctx = Context(df, vp, mp, months, start)
        combos = [(st, NO_HEDGE, sz) for st in [NAKED, STRUCTURES[2]] for sz in SIZINGS]
        combos += [(NAKED, hd, FIXED) for hd in HEDGES[1:]]
        combos += [(BENCH, NO_HEDGE, FIXED)]
        for st, hd, sz in combos:
            res = ctx.run(st, hd, sz)
            runs[(cal, st.name, hd.name, sz.name)] = res
            m = metrics(res, mp)
            rows.append({"calendar": cal, "structure": st.name, "hedge": hd.name, "sizing": sz.name,
                         **{k: m[k] for k in ["start", "ann_return_pct", "ann_vol_pct", "sharpe",
                                              "max_dd_pct_capital", "worst_quarter_pct", "max_mult", "ruined"]}})
    return pd.DataFrame(rows), runs


def premium_after_outcome(pt: pd.DataFrame) -> pd.DataFrame:
    """Is the next premium richer after a losing quarter? (natural 'recovery' without upsizing)"""
    x = pt.copy()
    x["prev_loss"] = x.naked_pnl_pct_notional.shift(1) < 0
    x = x.iloc[1:]
    g = x.groupby("prev_loss")
    return pd.DataFrame({"rolls": g.size(), "avg_premium_pct": g.put_premium_pct.mean(),
                         "avg_atm_iv_pct": g.atm_iv_3m_pct.mean(),
                         "next_q_naked_pnl_pct": g.naked_pnl_pct_notional.mean(),
                         "next_q_win_rate_pct": g.naked_pnl_pct_notional.apply(lambda s: 100 * (s > 0).mean())}
                        ).rename(index={False: "after a winning quarter", True: "after a losing quarter"})


def vrp_stats(ctx: Context) -> dict:
    """Implied 3M ATM vol at entry vs realized vol over the following quarter (settled cycles)."""
    rows = []
    for c in ctx.cycles:
        if c.open:
            continue
        lr = np.diff(np.log(c.S))
        rv = np.sqrt((lr ** 2).sum() / c.tau[0])
        rows.append({"year": c.entry.year, "iv": c.atm[0], "rv": rv})
    x = pd.DataFrame(rows)
    x["gap"] = 100 * (x.iv - x.rv)
    dec = x.groupby(x.year // 10 * 10).gap.mean()
    return {"mean_gap": float(x.gap.mean()), "median_gap": float(x.gap.median()),
            "share_iv_above": float((x.gap > 0).mean()), "by_decade": {int(k): float(v) for k, v in dec.items()}}


# ----------------------------------------------------------------------------- USD ledger (drawdown-limited)
DD50_RECOVER = Sizing("Recover, 50% drawdown limit", "recover", dd_limit=0.5, dd_stress=0.45)
DD50_FIXED = Sizing("Fixed, 50% drawdown limit", "fixed", dd_limit=0.5, dd_stress=0.45)


def usd_ledger(ctx: Context, st: Structure, sz: Sizing, start: str) -> tuple[pd.DataFrame, dict]:
    """Quarter-by-quarter dollar ledger: premium kept when the put expires worthless, losses when it
    finishes in the money, and the cumulated loss still to win back (equity high minus equity)."""
    res = ctx.run(st, NO_HEDGE, sz, start)
    c = res.cycles.copy()
    rows, hwm = [], ctx.mp.capital
    for _, r in c.iterrows():
        pnl = r.pnl_usd
        if r.open:
            outcome = "open (marked to market)"
        elif r.S_T >= r.K1:
            outcome = "expired worthless"
        elif pnl >= 0:
            outcome = "in the money, still a profit"
        else:
            outcome = "in the money, loss"
        if not r.open:
            hwm = max(hwm, r.equity)
        rows.append({
            "entry": r.entry.date(), "expiry": r.expiry.date(), "status": "open" if r.open else "settled",
            "nq_contracts": round(r.nq_contracts, 2), "size_x": round(r.mult, 2),
            "limit_applied": "yes" if r.dd_capped else "",
            "premium_usd": round(r.premium_usd), "outcome": outcome,
            "profit_usd": round(pnl) if pnl >= 0 else None,
            "loss_usd": round(pnl) if pnl < 0 else None,
            "cum_loss_usd": round(min(0.0, r.equity - hwm)), "account_usd": round(r.equity),
        })
    led = pd.DataFrame(rows)
    s = led[led.status == "settled"]
    eq = res.daily
    mtm_dd = eq.cummax() - eq
    worst_i = s.cum_loss_usd.idxmin()
    summary = {
        "start_capital": ctx.mp.capital, "base_notional": ctx.mp.base_notional,
        "first_roll": str(s.entry.iloc[0]), "last_expiry": str(s.expiry.iloc[-1]), "quarters": len(s),
        "final_account": float(s.account_usd.iloc[-1]),
        "net_profit": float(s.account_usd.iloc[-1] - ctx.mp.capital),
        "profit_worthless": float(s.loc[s.outcome == "expired worthless", "profit_usd"].sum()),
        "n_worthless": int((s.outcome == "expired worthless").sum()),
        "profit_itm_small": float(s.loc[s.outcome == "in the money, still a profit", "profit_usd"].sum()),
        "n_itm_small": int((s.outcome == "in the money, still a profit").sum()),
        "losses": float(s.loss_usd.sum()), "n_losses": int(s.loss_usd.notna().sum()),
        "avg_profit_worthless": float(s.loc[s.outcome == "expired worthless", "profit_usd"].mean()),
        "worst_quarter_loss": float(s.loss_usd.min()),
        "deepest_cum_loss": float(s.cum_loss_usd.min()), "deepest_cum_loss_at": str(s.expiry[worst_i]),
        "deepest_mtm_loss": float(-mtm_dd.max()), "deepest_mtm_loss_on": str(mtm_dd.idxmax().date()),
        "deepest_mtm_dd_pct": float(100 * ((eq.cummax() - eq) / eq.cummax()).max()),
        "deepest_mtm_dd_on": str(((eq.cummax() - eq) / eq.cummax()).idxmax().date()),
        "max_size_x": float(s.size_x.max()), "quarters_limited": int((s.limit_applied == "yes").sum()),
    }
    # longest stretch below the equity high, in quarters
    run = best = 0
    for v in s.cum_loss_usd:
        run = run + 1 if v < 0 else 0
        best = max(best, run)
    summary["longest_underwater_q"] = best
    return led, summary


def ledger_by_year(led: pd.DataFrame) -> pd.DataFrame:
    """Dollar ledger summed by expiry year (settled quarters only)."""
    x = led[led.status == "settled"].copy()
    x["year"] = pd.to_datetime(x.expiry).dt.year
    g = x.groupby("year")
    out = pd.DataFrame({
        "quarters": g.size(),
        "expired_worthless": g.outcome.apply(lambda s: int((s == "expired worthless").sum())),
        "profit_worthless_usd": g.apply(lambda d: d.loc[d.outcome == "expired worthless", "profit_usd"].sum(),
                                        include_groups=False),
        "profit_itm_usd": g.apply(lambda d: d.loc[d.outcome == "in the money, still a profit", "profit_usd"].sum(),
                                  include_groups=False),
        "losses_usd": g.loss_usd.sum(),
        "worst_cum_loss_usd": g.cum_loss_usd.min(),
        "account_end_usd": g.account_usd.last(),
    })
    return out.round(0)


def usd_scenario(df: pd.DataFrame, vp: VolParams, mp: MarketParams, start: str = "2008-01-01") -> dict:
    """Start in 2008 with a 50% drawdown limit: ledgers and summaries (plus checks on other calendars)."""
    ctx = Context(df, vp, mp)
    led, sm = usd_ledger(ctx, NAKED, DD50_RECOVER, start)
    led_fx, sm_fx = usd_ledger(ctx, NAKED, DD50_FIXED, start)
    _, sm_nolim = usd_ledger(ctx, NAKED, RECOVER, start)
    cal_rows = []
    for cname, (months, cstart) in CALENDARS.items():
        cctx = ctx if months == (3, 6, 9, 12) else Context(df, vp, mp, months, cstart)
        for sz in [DD50_RECOVER, DD50_FIXED, RECOVER]:
            _, s2 = usd_ledger(cctx, NAKED, sz, start)
            cal_rows.append({"calendar": cname, "sizing": sz.name, "first_roll": s2["first_roll"],
                             "final_account": s2["final_account"], "deepest_cum_loss": s2["deepest_cum_loss"],
                             "deepest_mtm_dd_pct": s2["deepest_mtm_dd_pct"], "deepest_mtm_dd_on": s2["deepest_mtm_dd_on"],
                             "max_size_x": s2["max_size_x"]})
    return {"ledger": led, "summary": sm, "ledger_fixed": led_fx, "summary_fixed": sm_fx,
            "summary_no_limit": sm_nolim, "calendars": pd.DataFrame(cal_rows), "by_year": ledger_by_year(led),
            "by_year_fixed": ledger_by_year(led_fx)}
