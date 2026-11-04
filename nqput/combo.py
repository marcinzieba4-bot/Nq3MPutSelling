"""Put selling with the -5% hedge, combined with the NQ "pyramid up" strategy (repo NQPyramidingUP).

Both strategies are measured the same way: US dollars per $100k unit, profits never reinvested, daily
closes. Calmar = average profit per year / worst peak-to-trough drawdown, both in dollars.

Capital in use on a day = margin of the open positions + the drawdown from the strategy's own high, i.e.
what an account has to hold that day. In one shared account the margins add up, but the drawdown is the
drawdown of the combined P&L, so one strategy's gains can cover the other's losses.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

PYRAMID = {"pyr7": "sell 20-delta 7-day calls", "pyr0": "no calls"}
PYR_LABEL = {"pyr7": "Pyramid + weekly calls", "pyr0": "Pyramid, no calls"}
PUT_LABEL = {"rec": "Puts, recovery rule", "fix": "Puts, fixed size"}
PYR_MARGIN = 0.055      # of the NQ notional held: about $3k per MNQ, as the pyramid study assumes
PUT_MARGIN = 0.10       # of the put notional while the put is open (as in the rest of this study)
NQ_POINT = 20.0
RUN_CAPITAL = 1e12      # recovery_campaigns runs on "unlimited" capital; P&L = equity - this
KS = (0, 0.5, 1, 2, 3, 5, 8)


def load_pyramid(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Daily equity (cumulative $ per $100k unit) and the trade list of the pyramid study."""
    eq = pd.read_csv(path / "equity_daily.csv", index_col=0)
    eq.index = pd.to_datetime(eq.index, utc=True).tz_convert(None).normalize()
    tr = pd.read_csv(path / "trades.csv")
    for c in ("entry_time", "exit_time"):
        tr[c] = pd.to_datetime(tr[c], utc=True, errors="coerce").dt.tz_convert(None)
    return eq, tr


def pyramid_reference(path: Path, version: str = "sell 20-delta 7-day calls @ 0.9 x VXN") -> dict:
    """The pyramid study's own statistics (intraday data, from 2 Jan 2008) for the version used here."""
    f = path / "summary.csv"
    if not f.exists():
        return {}
    t = pd.read_csv(f).set_index("version")
    if version not in t.index:
        return {}
    r = t.loc[version]
    return {"avg_per_year": float(r.avg_per_year), "max_drawdown": float(r.max_drawdown), "calmar": float(r.calmar)}


def _held_contracts(trades: pd.DataFrame, idx: pd.DatetimeIndex) -> pd.Series:
    """NQ contracts (fractional, per $100k unit) held at each daily close."""
    end = idx[-1] + pd.Timedelta(days=1)
    held = np.zeros(len(idx))
    for r in trades.itertuples():
        a = r.entry_time.normalize()
        b = r.exit_time.normalize() if pd.notna(r.exit_time) else end
        held[(idx >= a) & (idx < b)] += r.contracts
    return pd.Series(held, index=idx)


def _put_notional(run, idx: pd.DatetimeIndex) -> pd.Series:
    """Put notional open at each daily close (the expiring put is replaced on the same day)."""
    n = np.zeros(len(idx))
    for r in run.cycles.itertuples():
        m = (idx >= r.entry) & (idx <= r.expiry)
        n[m] = np.maximum(n[m], r.notional)
    return pd.Series(n, index=idx)


def build_frame(eq: pd.DataFrame, trades: pd.DataFrame, put_runs: dict, ndx: pd.Series) -> pd.DataFrame:
    """Aligned business-day frame: cumulative $ P&L and $ notional of each leg, per $100k unit.

    Starts at the first put roll (both strategies sit at $0 then) and ends at the earlier last date.
    """
    first = min(r.daily.index[0] for r in put_runs.values())
    last = min([eq.index[-1]] + [r.daily.index[-1] for r in put_runs.values()])
    idx = pd.bdate_range(max(first, eq.index[0]), last)

    def align(s: pd.Series) -> pd.Series:
        return s.reindex(s.index.union(idx)).ffill().reindex(idx).fillna(0.0)

    out = pd.DataFrame(index=idx)
    out.index.name = "date"
    for k, col in PYRAMID.items():
        s = align(eq[col])
        out[k] = s - s.iloc[0]
    for k, run in put_runs.items():
        out[f"puts_{k}"] = align(run.daily - RUN_CAPITAL)
        out[f"notional_{k}"] = _put_notional(run, idx)
    nd = ndx.dropna()
    off = 1.0 - nd / nd.rolling(252, min_periods=1).max()      # below the 52-week high, full history
    out["ndx"] = align(nd)
    out["ndx_off_high"] = align(off)
    out["notional_pyr"] = _held_contracts(trades, idx) * out.ndx * NQ_POINT
    return out


def _years(s: pd.Series) -> float:
    return (s.index[-1] - s.index[0]).days / 365.25


def stats(pnl: pd.Series, margin: pd.Series) -> dict:
    hwm = pnl.cummax().clip(lower=0.0)
    dd = hwm - pnl
    cap = margin + dd
    avg = pnl.iloc[-1] / _years(pnl)
    return {"profit_per_year": avg, "worst_drawdown": dd.max(), "drawdown_trough": dd.idxmax().date(),
            "calmar": avg / dd.max(), "peak_capital": cap.max(), "peak_capital_date": cap.idxmax().date(),
            "return_on_peak_capital": avg / cap.max()}


def _legs(F: pd.DataFrame, p: str, q: str, put_margin: float, pyr_margin: float):
    return F[p], F.notional_pyr * pyr_margin, F[f"puts_{q}"], F[f"notional_{q}"] * put_margin


def mix_table(F: pd.DataFrame, ks=KS, put_margin: float = PUT_MARGIN, pyr_margin: float = PYR_MARGIN) -> pd.DataFrame:
    """One pyramid unit + k put units (each $100k, never reinvested), for each pyramid and put version."""
    rows = []
    for p in PYRAMID:
        for q in PUT_LABEL:
            a, ma, b, mb = _legs(F, p, q, put_margin, pyr_margin)
            sa, sb = stats(a, ma), stats(b, mb)
            grid = np.arange(0.0, 15.01, 0.25)
            k_best = float(grid[int(np.argmax([stats(a + k * b, ma + k * mb)["calmar"] for k in grid]))])
            k_eq = sa["worst_drawdown"] / sb["worst_drawdown"]
            picks = [(float(k), "") for k in ks] + [(k_eq, "equal worst drawdown"), (k_best, "best Calmar")]
            for k, why in sorted(picks, key=lambda x: x[0]):
                s = stats(a + k * b, ma + k * mb)
                separate = sa["peak_capital"] + k * sb["peak_capital"]
                rows.append({"pyramid": PYR_LABEL[p], "puts": PUT_LABEL[q], "put_units": round(k, 2), "note": why,
                             **s, "peak_capital_if_separate": separate,
                             "capital_saved_by_one_account": 1 - s["peak_capital"] / separate})
    return pd.DataFrame(rows)


def standalone(F: pd.DataFrame, put_margin: float = PUT_MARGIN, pyr_margin: float = PYR_MARGIN) -> pd.DataFrame:
    rows = []
    for p in PYRAMID:
        rows.append({"strategy": PYR_LABEL[p], **stats(F[p], F.notional_pyr * pyr_margin)})
    for q in PUT_LABEL:
        rows.append({"strategy": PUT_LABEL[q] + " (-5% hedge)", **stats(F[f"puts_{q}"], F[f"notional_{q}"] * put_margin)})
    return pd.DataFrame(rows)


STATES = [(-1e-9, 0.05, "NDX within 5% of its 52-week high"), (0.05, 0.10, "5-10% below"),
          (0.10, 0.20, "10-20% below"), (0.20, 1.0, "more than 20% below")]


def by_market_state(F: pd.DataFrame, put_margin: float = PUT_MARGIN, pyr_margin: float = PYR_MARGIN) -> pd.DataFrame:
    """Average margin and capital in use of each strategy, by how far NDX is below its 52-week high."""
    st = pd.cut(F.ndx_off_high, [s[0] for s in STATES] + [STATES[-1][1]], labels=[s[2] for s in STATES])

    def dd(s):
        return s.cummax().clip(lower=0.0) - s
    x = pd.DataFrame({
        "share_of_days": 1.0,
        "pyramid_notional": F.notional_pyr,
        "pyramid_margin": F.notional_pyr * pyr_margin,
        "puts_rec_margin": F.notional_rec * put_margin,
        "puts_fix_margin": F.notional_fix * put_margin,
        "pyramid_capital_in_use": F.notional_pyr * pyr_margin + dd(F.pyr7),
        "puts_rec_capital_in_use": F.notional_rec * put_margin + dd(F.puts_rec),
        "puts_fix_capital_in_use": F.notional_fix * put_margin + dd(F.puts_fix),
    })
    t = x.groupby(st, observed=False).mean()
    t["share_of_days"] = st.value_counts(normalize=True).reindex(t.index)
    t.index.name = "market"
    return t


def _episodes(s: pd.Series, n: int) -> list[tuple]:
    """The n largest drawdown episodes (high -> lowest point before the next high)."""
    hwm = s.cummax().clip(lower=0.0)
    dd = hwm - s
    grp = (s >= hwm).cumsum()
    eps = []
    for _, seg in dd.groupby(grp):
        if seg.max() > 0:
            eps.append((seg.index[0], seg.idxmax(), seg.max()))
    return sorted(eps, key=lambda e: -e[2])[:n]


def overlap_table(F: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    """Worst drawdowns of each strategy and what the other one did over the same dates."""
    rows = []
    for lead, others in [("pyr7", ("puts_rec", "puts_fix")), ("puts_rec", ("pyr7",)), ("puts_fix", ("pyr7",))]:
        for a, b, v in _episodes(F[lead], n):
            r = {"strategy": {"pyr7": PYR_LABEL["pyr7"], "puts_rec": PUT_LABEL["rec"],
                              "puts_fix": PUT_LABEL["fix"]}[lead],
                 "from": a.date(), "to": b.date(), "drawdown": -v,
                 "ndx_move": F.ndx[b] / F.ndx[a] - 1}
            for o in ("pyr7", "puts_rec", "puts_fix"):
                r[f"{o}_same_dates"] = F[o][b] - F[o][a] if o in others else np.nan
            rows.append(r)
    return pd.DataFrame(rows)


def by_year(F: pd.DataFrame, put_margin: float = PUT_MARGIN, pyr_margin: float = PYR_MARGIN) -> pd.DataFrame:
    y = F.index.year
    end = F.groupby(y).last()
    pnl = end[["pyr7", "puts_rec", "puts_fix"]].diff()
    pnl.iloc[0] = end[["pyr7", "puts_rec", "puts_fix"]].iloc[0]
    t = pnl.rename(columns={"pyr7": "pyramid_pnl", "puts_rec": "puts_rec_pnl", "puts_fix": "puts_fix_pnl"})
    t["one_to_one_rec_pnl"] = t.pyramid_pnl + t.puts_rec_pnl
    t["ndx_move"] = F.ndx.groupby(y).last() / F.ndx.groupby(y).first() - 1
    t["pyramid_peak_margin"] = (F.notional_pyr * pyr_margin).groupby(y).max()
    t["puts_rec_peak_margin"] = (F.notional_rec * put_margin).groupby(y).max()
    t.index.name = "year"
    return t


def run(eq: pd.DataFrame, trades: pd.DataFrame, put_runs: dict, ndx: pd.Series) -> dict:
    F = build_frame(eq, trades, put_runs, ndx)
    mix = mix_table(F)
    corr_m = F[["pyr7", "puts_rec", "puts_fix"]].resample("ME").last().diff().dropna().corr()
    # the fixed-size put always carries the same margin, so only the recovery rule's margin can co-move
    margin_corr = float((F.notional_pyr * PYR_MARGIN).corr(F.notional_rec * PUT_MARGIN))
    return {"frame": F, "mix": mix, "mix_margin6": mix_table(F, ks=(1, 2), put_margin=0.06),
            "standalone": standalone(F), "states": by_market_state(F), "overlap": overlap_table(F),
            "by_year": by_year(F), "monthly_corr": corr_m, "margin_corr": margin_corr,
            "period": (F.index[0].date(), F.index[-1].date(), _years(F.pyr7))}
