"""Backtest engine: short 3-month ATM puts on NQ futures, rolled at quarterly expiries.

Mechanics
---------
* Entry at the close of each quarterly expiry (3rd Friday of Mar/Jun/Sep/Dec, or an
  offset cycle), into the option expiring at the next cycle expiry (~13 weeks).
* Underlying = the NQ future for that expiry, modelled as F = NDX * exp((r - q) * tau);
  ATM strike = F at entry. Options are priced with Black-76 on the estimated
  implied-vol surface (see volmodel.py). Settlement at expiry = NDX close.
* Every cycle is first simulated for ONE unit of notional (1 x index at entry) giving
  a daily P&L path; sizing (fixed or loss-recovery "martingale") then scales whole
  cycles, which is exact because P&L is linear in size within a cycle.
* Daily mark-to-market at model mid; option trades pay a half-spread in vol points
  plus commission; futures hedges pay a cost in bp of notional per side.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .black76 import put_delta, put_price
from .volmodel import VolParams, atm_vol_for_tau, strike_vol

NQ_MULT = 20.0  # $ per index point for one NQ future / option


# ----------------------------------------------------------------------------- params
@dataclass
class MarketParams:
    div_yield: float = 0.007           # NDX dividend yield used for futures carry
    opt_slip_vol: float = 0.005        # half bid/ask paid on each option trade (0.5 vol pt)
    opt_comm_pts: float = 0.125        # $2.50 per NQ option = 0.125 index pts
    fut_cost_bp: float = 1.0           # futures hedge cost per side (spread + fees), bp of notional
    capital: float = 1_000_000.0       # starting account equity
    base_notional: float = 1_000_000.0 # notional of the base trade (= 1.0x account)
    margin_naked: float = 0.10         # margin per $ notional for a naked short put (SPAN-like)


@dataclass(frozen=True)
class Structure:
    name: str
    long_otm: float | None = None      # long put strike = K_short * (1 - long_otm); None = naked
    short_moneyness: float = 0.0       # K_short = F0 * (1 - short_moneyness); 0 = ATM
    kind: str = "short_put"            # short_put | long_futures (benchmark)


@dataclass(frozen=True)
class Hedge:
    name: str = "no hedge"
    mode: str = "none"                 # none | full | cap | itm
    every: int = 1                     # rebalance every N trading days (1 = daily, 5 = weekly)
    ratio: float = 1.0                 # fraction of delta hedged (full mode)
    band: float = 0.0                  # only trade when |target - current| > band
    itm_trigger: float = 0.0           # itm mode: hedge only while F < K * (1 - trigger)


@dataclass(frozen=True)
class Sizing:
    name: str = "fixed 1x"
    mode: str = "fixed"                # fixed | recover | recover_once
    recover_quarters: int = 1          # spread the recovery of the deficit over N quarters
    max_mult: float = np.inf           # cap on the size multiplier
    extra_profit: float = 0.0          # extra target as fraction of deficit
    trend_filter: bool = False         # only sell when NDX > 200-day average at the roll


# ----------------------------------------------------------------------------- calendar
def third_friday(year: int, month: int) -> pd.Timestamp:
    d = pd.Timestamp(year=year, month=month, day=15)
    return d + pd.Timedelta(days=(4 - d.weekday()) % 7)


def expiry_dates(dates: pd.DatetimeIndex, months: tuple[int, ...], start: str, end_extra: int = 1
                 ) -> list[pd.Timestamp]:
    """Cycle expiries: 3rd Friday of `months`, moved to the previous trading day if it was a
    holiday. Includes `end_extra` future expiries after the data ends (open position)."""
    out: list[pd.Timestamp] = []
    last = dates[-1]
    extra = 0
    for y in range(pd.Timestamp(start).year, last.year + 2):
        for m in sorted(months):
            tf = third_friday(y, m)
            if tf < pd.Timestamp(start):
                continue
            if tf <= last:
                pos = dates.searchsorted(tf, side="right") - 1
                out.append(dates[pos])
            elif extra < end_extra:
                out.append(tf)
                extra += 1
    return out


# ----------------------------------------------------------------------------- cycles
@dataclass
class Cycle:
    entry: pd.Timestamp
    expiry: pd.Timestamp
    open: bool                         # expiry after the last data date (live position)
    dates: pd.DatetimeIndex
    S: np.ndarray
    F: np.ndarray
    tau: np.ndarray                    # years to expiry
    r: np.ndarray
    atm: np.ndarray                    # ATM vol for the remaining maturity each day
    src: str                           # IV source at entry
    trend_up: bool = True              # NDX close above its 200-day average at entry

    @property
    def F0(self) -> float:
        return float(self.F[0])


def build_cycles(df: pd.DataFrame, vol: pd.DataFrame, months=(3, 6, 9, 12), start="1986-03-01",
                 mp: MarketParams | None = None) -> list[Cycle]:
    mp = mp or MarketParams()
    dates = df.index
    exps = expiry_dates(dates, months, start)
    ma200 = df.ndx.rolling(200, min_periods=150).mean()
    cycles: list[Cycle] = []
    for e0, e1 in zip(exps[:-1], exps[1:]):
        if e0 > dates[-1]:
            break
        i0 = dates.get_loc(e0)
        i1 = dates.get_loc(e1) if e1 <= dates[-1] else len(dates) - 1
        sl = slice(i0, i1 + 1)
        d = dates[sl]
        tau_days = (e1 - d).days.to_numpy().astype(float)
        tau = tau_days / 365.0
        S = df.ndx.iloc[sl].to_numpy()
        r = df.rf.iloc[sl].to_numpy()
        F = S * np.exp((r - mp.div_yield) * tau)
        atm = atm_vol_for_tau(vol.atm1m.iloc[sl].to_numpy(), vol.atm3m.iloc[sl].to_numpy(), tau_days)
        if np.isnan(atm).any() or np.isnan(S).any() or np.isnan(r).any():
            if cycles:
                raise ValueError(f"missing inputs inside cycle {e0.date()}..{e1.date()}")
            continue  # inputs not available yet at the very start
        cycles.append(Cycle(entry=e0, expiry=e1, open=e1 > dates[-1], dates=d, S=S, F=F, tau=tau, r=r,
                            atm=atm, src=str(vol.vxn_src.iloc[i0]),
                            trend_up=bool(df.ndx.iloc[i0] > ma200.iloc[i0])))
    return cycles


def _option_path(c: Cycle, K: float, vp: VolParams):
    sig = strike_vol(c.atm, c.F, K, c.tau, vp)
    V = put_price(c.F, K, c.tau, c.r, sig)
    D = put_delta(c.F, K, c.tau, c.r, sig)
    return V, D, sig


# ----------------------------------------------------------------------------- unit paths
@dataclass
class UnitCycle:
    cycle: Cycle
    ret: np.ndarray                    # daily P&L per $1 of notional (unit notional = F0)
    credit: float                      # net premium received, index pts (after costs)
    info: dict = field(default_factory=dict)
    margin_frac: float = 0.10          # margin per $ notional
    premium_frac: float = 0.0          # credit / F0


def unit_cycle(c: Cycle, st: Structure, hd: Hedge, mp: MarketParams, vp: VolParams) -> UnitCycle:
    n = len(c.dates)
    F0 = c.F0
    if st.kind == "long_futures":
        pnl = np.zeros(n)
        pnl[1:] = np.diff(c.F)
        pnl[0] -= F0 * mp.fut_cost_bp / 1e4
        return UnitCycle(c, pnl / F0, 0.0, {"S_T": c.S[-1]}, margin_frac=mp.margin_naked, premium_frac=0.0)

    K1 = F0 * (1 - st.short_moneyness)
    V1, D1, sig1 = _option_path(c, K1, vp)
    bid1 = put_price(F0, K1, c.tau[0], c.r[0], max(sig1[0] - mp.opt_slip_vol, vp.vol_floor))
    credit = bid1 - mp.opt_comm_pts
    mtm = -V1.copy()
    dport = -D1.copy()
    info = {"K1": K1, "iv1": sig1[0], "prem1_mid": V1[0], "prem1_bid": bid1}
    if st.long_otm is not None:
        K2 = K1 * (1 - st.long_otm)
        V2, D2, sig2 = _option_path(c, K2, vp)
        ask2 = put_price(F0, K2, c.tau[0], c.r[0], sig2[0] + mp.opt_slip_vol)
        credit -= ask2 + mp.opt_comm_pts
        mtm += V2
        dport += D2
        info.update({"K2": K2, "iv2": sig2[0], "prem2_mid": V2[0], "prem2_ask": ask2})
        max_loss = (K1 - K2) - credit
        margin_frac = min(mp.margin_naked, max(max_loss, 0.0) / F0)
    else:
        margin_frac = mp.margin_naked

    # --- futures delta hedge (position held from close t to close t+1) ---
    h = np.zeros(n)
    if hd.mode != "none":
        d0 = dport[0]
        cur = 0.0
        # a settled cycle needs no hedge decision on expiry day; an open one keeps hedging
        for t in range(n if c.open else n - 1):
            if t % hd.every == 0:
                if hd.mode == "full":
                    tgt = -hd.ratio * dport[t]
                elif hd.mode == "cap":      # never let delta grow above the entry delta
                    tgt = -max(0.0, dport[t] - d0) * hd.ratio
                elif hd.mode == "itm":      # hedge fully only while the short put is ITM
                    tgt = -dport[t] if c.F[t] < K1 * (1 - hd.itm_trigger) else 0.0
                else:
                    raise ValueError(hd.mode)
                if abs(tgt - cur) > hd.band or tgt == 0.0:
                    cur = tgt
            h[t] = cur
        # last day: futures settle with the options (no trade cost)
    trades = np.abs(np.diff(np.concatenate([[0.0], h])))
    if not c.open and n > 1:
        trades[-1] = 0.0  # hedge futures cash-settle together with the options
    hedge_cost = trades * c.F * mp.fut_cost_bp / 1e4
    hedge_pnl = np.zeros(n)
    hedge_pnl[1:] = h[:-1] * np.diff(c.F)

    pnl = np.zeros(n)
    pnl[0] = credit + mtm[0]
    pnl[1:] = np.diff(mtm)
    pnl += hedge_pnl - hedge_cost

    info.update({
        "S0": c.S[0], "F0": F0, "S_T": c.S[-1], "atm_iv": c.atm[0], "credit": credit,
        "payoff": -mtm[-1] if not c.open else np.nan,
        "hedge_pnl": hedge_pnl.sum(), "hedge_cost": hedge_cost.sum(),
        "hedge_trades": trades.sum(), "pnl_pts": pnl.sum(),
        "entry_delta": dport[0],
    })
    return UnitCycle(c, pnl / F0, credit, info, margin_frac=margin_frac, premium_frac=credit / F0)


# ----------------------------------------------------------------------------- sizing
@dataclass
class RunResult:
    name: str
    daily: pd.Series                   # equity ($) by date
    cycles: pd.DataFrame               # one row per cycle
    ruined: pd.Timestamp | None


def run_sizing(units: list[UnitCycle], sz: Sizing, mp: MarketParams, name: str = "") -> RunResult:
    E = mp.capital
    hwm = E
    N0 = mp.base_notional
    rows = []
    pieces = []
    ruined = None
    prev_pnl, prev_was_recovery = 0.0, False
    for u in units:
        c = u.cycle
        deficit = max(0.0, hwm - E)
        p = max(u.premium_frac, 1e-4)
        if sz.mode == "fixed":
            m = 1.0
        elif sz.mode == "recover":       # chase the whole drawdown until equity is back at its high
            m = 1.0 + deficit * (1 + sz.extra_profit) / (N0 * p * sz.recover_quarters)
        elif sz.mode == "recover_once":  # one upsized quarter after a losing base-size quarter
            loss = -prev_pnl if (prev_pnl < 0 and not prev_was_recovery) else 0.0
            m = 1.0 + loss * (1 + sz.extra_profit) / (N0 * p)
        else:
            raise ValueError(sz.mode)
        m = min(m, sz.max_mult)
        if sz.trend_filter and not c.trend_up:
            m = 0.0
        m_wanted = m
        m_margin = E / (N0 * u.margin_frac) if E > 0 else 0.0
        m = max(0.0, min(m, m_margin))
        dollars = m * N0 * u.ret
        eq = E + np.cumsum(dollars)
        if (eq <= 0).any():
            k = int(np.argmax(eq <= 0))
            eq = eq[: k + 1]
            ruined = c.dates[k]
        pieces.append(pd.Series(eq, index=c.dates[: len(eq)]))
        pnl = eq[-1] - E
        rows.append({
            "entry": c.entry, "expiry": c.expiry, "open": c.open, "iv_src": c.src,
            "mult": m, "mult_wanted": m_wanted, "margin_capped": m < m_wanted - 1e-9,
            "notional": m * N0, "nq_contracts": m * N0 / (u.cycle.F0 * NQ_MULT),
            "premium_usd": m * N0 * u.premium_frac, "deficit_before": deficit,
            "pnl_usd": pnl, "pnl_pct_cap": pnl / mp.capital, "equity": eq[-1],
            "S0": c.S[0], "S_T": c.S[-1], "F0": c.F0, "K1": u.info.get("K1"),
            "itm": (c.S[-1] < u.info.get("K1", np.inf)) if not c.open else None,
        })
        prev_pnl, prev_was_recovery = pnl, m > 1.0 + 1e-9
        E = eq[-1]
        hwm = max(hwm, E)
        if ruined is not None:
            break
    daily = pd.concat(pieces)
    daily = daily.groupby(level=0).last()  # roll day: keep end-of-day equity after both legs
    return RunResult(name, daily, pd.DataFrame(rows), ruined)


# ----------------------------------------------------------------------------- metrics
def metrics(res: RunResult, mp: MarketParams, completed_only: bool = True) -> dict:
    eq = res.daily
    cyc = res.cycles
    if completed_only:
        last_closed = cyc.loc[~cyc.open, "expiry"].max()
        eq = eq[eq.index <= last_closed]
        cyc = cyc[~cyc.open]
    C0 = mp.capital
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    dpnl = eq.diff().dropna() / C0
    peak = eq.cummax()
    dd = (peak - eq) / C0
    dd_rel = (peak - eq) / peak
    q = cyc.pnl_pct_cap
    ann_ret = (eq.iloc[-1] - C0) / C0 / years
    vol = dpnl.std() * np.sqrt(252)
    out = {
        "strategy": res.name,
        "start": eq.index[0].date(), "end": eq.index[-1].date(), "quarters": len(cyc),
        "final_equity": eq.iloc[-1],
        "ann_return_pct": 100 * ann_ret,
        "ann_vol_pct": 100 * vol,
        "sharpe": ann_ret / vol if vol > 0 else np.nan,
        "max_dd_pct_capital": 100 * dd.max(),
        "max_dd_pct_peak": 100 * dd_rel.max(),
        "calmar": ann_ret / dd.max() if dd.max() > 0 else np.nan,
        "worst_quarter_pct": 100 * q.min(),
        "best_quarter_pct": 100 * q.max(),
        "pct_quarters_up": 100 * (q > 0).mean(),
        "losing_quarters": int((q < 0).sum()),
        "max_consec_losses": int(_max_run(q.to_numpy() < 0)),
        "cvar5_quarter_pct": 100 * q.nsmallest(max(1, int(round(len(q) * 0.05)))).mean(),
        "max_mult": cyc.mult.max(),
        "avg_mult": cyc.mult.mean(),
        "margin_capped_q": int(cyc.margin_capped.sum()),
        "ruined": str(res.ruined.date()) if res.ruined is not None else "",
    }
    return out


def _max_run(mask: np.ndarray) -> int:
    best = cur = 0
    for v in mask:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best
