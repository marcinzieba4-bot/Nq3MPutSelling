"""Charts (PNG) and the markdown report."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.ticker  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

from . import analysis as A  # noqa: E402

# reference palette (light mode)
SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
S = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
GAIN, LOSS, CRITICAL = "#2a78d6", "#e34948", "#d03b3b"
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": AXIS, "axes.linewidth": 0.8, "axes.labelcolor": INK2, "axes.titlecolor": INK,
    "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left", "axes.labelsize": 10,
    "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelsize": 9, "ytick.labelsize": 9,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
    "legend.fontsize": 9, "font.size": 10, "text.color": INK, "lines.linewidth": 2.0, "text.parse_math": False,
})


def _pct(v: float, d: int = 1) -> str:
    return f"{v:.{d}f}%"


def _money(v: float, sign: bool = False) -> str:
    s = "-" if v < 0 else ("+" if sign else "")
    return f"{s}${abs(v):,.0f}"


def _end_label(ax, s: pd.Series, text: str, color: str, dy: float = 0.0):
    ax.annotate(text, (s.index[-1], s.iloc[-1]), xytext=(6, dy), textcoords="offset points",
                color=INK2, fontsize=9, va="center")
    ax.plot([s.index[-1]], [s.iloc[-1]], "o", ms=5, color=color, mec=SURFACE, mew=1.5)


def _cum_pct(res, capital: float) -> pd.Series:
    return (res.daily - capital) / capital * 100


# ----------------------------------------------------------------------------- figures
def fig_premiums(path: Path, ctx, pt: pd.DataFrame, snap: dict):
    vol = ctx.vol
    iv = (vol.atm3m * 100).dropna()
    iv = iv[iv.index >= "1986-03-01"]
    x = pt[pt.status == "settled"].copy()
    x["entry"] = pd.to_datetime(x.entry)
    x["payoff_pct"] = x.payoff_pts / x.futures_entry * 100
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 7.2), sharex=True, gridspec_kw={"height_ratios": [1, 1.25]})
    proxy_end = vol.index[vol.vxn_src.eq("VXN actual")][0]
    a1.axvspan(iv.index[0], proxy_end, color="#f0efec", lw=0)
    a1.text(iv.index[0] + pd.Timedelta(days=1100), iv.max() * 0.97, "VXN reconstructed (proxy)", color=MUTED,
            fontsize=8.5, va="top")
    a1.text(proxy_end + pd.Timedelta(days=200), iv.max() * 0.97, "VXN actual", color=MUTED, fontsize=8.5, va="top")
    a1.plot(iv.index, iv.values, color=S[0], lw=1.2)
    a1.plot([iv.index[-1]], [iv.iloc[-1]], "o", ms=6, color=S[0], mec=SURFACE, mew=1.5)
    a1.annotate(f"now {iv.iloc[-1]:.1f}%", (iv.index[-1], iv.iloc[-1]), xytext=(-8, 16),
                textcoords="offset points", color=INK2, fontsize=9, ha="right")
    a1.set_title("Estimated 3-month ATM implied volatility of the Nasdaq-100 (%)")
    a1.set_ylim(0, None)
    w = 60
    a2.bar(x.entry, x.put_premium_pct, width=w, color=GAIN, label="Premium collected (% of notional)")
    a2.bar(x.entry, -x.payoff_pct, width=w, color=LOSS, label="Paid out at expiry (put ITM)")
    a2.axhline(0, color=AXIS, lw=0.8)
    a2.set_title("Each quarterly roll: premium in vs payout at expiry (naked ATM put, % of notional)")
    a2.legend(loc="upper center", bbox_to_anchor=(0.5, -0.07), ncol=2)
    a2.xaxis.set_major_locator(mdates.YearLocator(4))
    a2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    lo = -x.payoff_pct.max()
    a2.set_ylim(lo - 7, x.put_premium_pct.max() + 2)
    for d, lab in [("2001-06-01", "dot-com bust"), ("2008-12-01", "GFC"), ("2020-03-01", "COVID"),
                   ("1987-12-01", "1987 crash"), ("2022-06-01", "2022 bear")]:
        a2.annotate(lab, (pd.Timestamp(d), lo - 5), color=MUTED, fontsize=8.5, ha="center")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_fixed(path: Path, runs: dict, mp):
    fig, ax = plt.subplots(figsize=(11, 5.2))
    items = [
        ((A.BENCH.name, A.NO_HEDGE.name, A.FIXED.name), "Long NQ futures 0.5x (same avg delta)", S[3], 0.5),
        ((A.NAKED.name, A.NO_HEDGE.name, A.FIXED.name), "Naked ATM put", S[0], 1.0),
        ((A.STRUCTURES[4].name, A.NO_HEDGE.name, A.FIXED.name), "Put spread ATM/-20%", S[1], 1.0),
        ((A.STRUCTURES[2].name, A.NO_HEDGE.name, A.FIXED.name), "Put spread ATM/-10%", S[2], 1.0),
    ]
    offs = [8, 0, 0, -8]
    for (key, lab, col, scale), dy in zip(items, offs):
        s = _cum_pct(runs[key], mp.capital) * scale
        ax.plot(s.index, s.values, color=col, label=lab, lw=1.6)
        _end_label(ax, s, f"{lab.split(' (')[0]}  {s.iloc[-1]:+.0f}%", col, dy)
    ax.axhline(0, color=AXIS, lw=0.8)
    ax.set_title("Cumulative P&L, fixed size: $1M notional sold every quarter (% of $1M capital, not reinvested)")
    ax.set_ylabel("% of starting capital")
    ax.legend(loc="upper left")
    ax.set_xlim(None, ax.get_xlim()[1] + 2600)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_recovery(path: Path, runs: dict, cal_runs: dict, mp):
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 7.4), sharex=True, gridspec_kw={"height_ratios": [1.6, 1]})
    fixed = runs[(A.NAKED.name, A.NO_HEDGE.name, A.FIXED.name)]
    rec = runs[(A.NAKED.name, A.NO_HEDGE.name, A.RECOVER.name)]
    rec_jan = cal_runs[("Jan/Apr/Jul/Oct", A.NAKED.name, A.NO_HEDGE.name, A.RECOVER.name)]
    rec_feb = cal_runs[("Feb/May/Aug/Nov", A.NAKED.name, A.NO_HEDGE.name, A.RECOVER.name)]
    series = [(fixed, "Fixed size (Mar/Jun/Sep/Dec)", S[0]), (rec, "Recovery sizing (Mar/Jun/Sep/Dec)", S[1]),
              (rec_jan, "Recovery sizing (Jan/Apr/Jul/Oct)", S[6]), (rec_feb, "Recovery sizing (Feb/May/Aug/Nov)", S[4])]
    ruined_pts = []
    for res, lab, col in series:
        s = _cum_pct(res, mp.capital)
        a1.plot(s.index, s.values, color=col, lw=1.5, label=lab)
        if res.ruined is not None:
            a1.plot([s.index[-1]], [s.iloc[-1]], marker="X", ms=10, color=CRITICAL, mec=SURFACE, mew=1.2)
            ruined_pts.append((s.index[-1], s.iloc[-1], lab.split("(")[1].rstrip(")"), res.ruined))
    if ruined_pts:
        t, v = ruined_pts[0][0], min(p[1] for p in ruined_pts)
        names = " and ".join(p[2] for p in ruined_pts)
        a1.annotate(f"{names} calendars: account wiped out {ruined_pts[0][3]:%b %Y}", (t, v), xytext=(12, -6),
                    textcoords="offset points", fontsize=9, color=INK2)
    a1.axhline(-100, color=CRITICAL, lw=0.8)
    a1.text(pd.Timestamp("1987-01-01"), -92, "-100% = starting capital lost", color=MUTED, fontsize=8.5)
    a1.axhline(0, color=AXIS, lw=0.8)
    a1.set_title('"Increase size to cover the loss" (naked ATM put): same rule, three roll calendars')
    a1.set_ylabel("% of starting capital")
    a1.legend(loc="upper left")
    c = rec.cycles
    a2.bar(pd.to_datetime(c.entry), c.mult, width=70, color=S[1])
    a2.set_title("Position size used by the recovery rule (x base size), Mar/Jun/Sep/Dec calendar")
    a2.set_ylabel("size multiplier")
    big = c.nlargest(3, "mult")
    for _, r in big.iterrows():
        a2.annotate(f"{r.mult:.1f}x", (pd.Timestamp(r.entry), r.mult), xytext=(0, 3), textcoords="offset points",
                    ha="center", fontsize=8.5, color=INK2)
    a2.xaxis.set_major_locator(mdates.YearLocator(4))
    a2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_start_year(path: Path, sy: pd.DataFrame):
    order = [
        f"{A.NAKED.name} | {A.NO_HEDGE.name} | {A.FIXED.name}",
        f"{A.STRUCTURES[2].name} | {A.NO_HEDGE.name} | {A.FIXED.name}",
        f"{A.NAKED.name} | {A.NO_HEDGE.name} | {A.SIZINGS[2].name}",
        f"{A.NAKED.name} | {A.NO_HEDGE.name} | {A.RECOVER.name}",
        f"{A.STRUCTURES[2].name} | {A.NO_HEDGE.name} | {A.RECOVER.name}",
        f"{A.STRUCTURES[4].name} | {A.NO_HEDGE.name} | {A.RECOVER.name}",
    ]
    labels = ["Naked put, fixed size", "Put spread -10%, fixed size", "Naked put, recover once",
              "Naked put, recover until whole", "Put spread -10%, recover until whole",
              "Put spread -20%, recover until whole"]
    years = sorted(sy.start_year.unique())
    M = np.full((len(order), len(years)), np.nan)
    R = np.zeros_like(M, dtype=bool)
    for i, strat in enumerate(order):
        d = sy[sy.strategy == strat].set_index("start_year")
        for j, y in enumerate(years):
            M[i, j] = min(d.loc[y, "max_dd_pct_capital"], 150)
            R[i, j] = isinstance(d.loc[y, "ruined"], str) and len(d.loc[y, "ruined"]) > 0
    cmap = LinearSegmentedColormap.from_list("seq", SEQ)
    fig, ax = plt.subplots(figsize=(12, 3.9))
    ax.grid(False)
    im = ax.imshow(np.where(R, np.nan, M), aspect="auto", cmap=cmap, vmin=0, vmax=150)
    for i in range(len(order)):
        for j in range(len(years)):
            if R[i, j]:
                ax.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1, color=CRITICAL, lw=0))
                ax.text(j, i, "✕", ha="center", va="center", color="#ffffff", fontsize=8)
    for j in range(len(years) + 1):
        ax.axvline(j - 0.5, color=SURFACE, lw=1.2)
    for i in range(len(order) + 1):
        ax.axhline(i - 0.5, color=SURFACE, lw=2)
    ax.set_yticks(range(len(order)), labels, fontsize=9, color=INK2)
    ax.set_xticks(range(0, len(years), 2), [str(y) for y in years[::2]], fontsize=8.5)
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_title("Start in year X with $1M: max drawdown as % of starting capital (darker = deeper).  "
                 "Red ✕ = account wiped out", fontsize=11)
    cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01)
    cb.set_label("max drawdown, % (capped at 150)", color=INK2, fontsize=8.5)
    cb.outline.set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_hedging(path: Path, runs: dict, mp):
    fig, ax = plt.subplots(figsize=(11, 5.2))
    items = [(A.NO_HEDGE, "No hedge", S[0]), (A.HEDGES[4], "Delta cap (hedge only delta above entry)", S[2]),
             (A.HEDGES[5], "Stop hedge (fully hedged while ITM)", S[1]), (A.HEDGES[1], "Full delta hedge, daily", S[6])]
    offs = [0, 0, 6, -6]
    for (hd, lab, col), dy in zip(items, offs):
        s = _cum_pct(runs[(A.NAKED.name, hd.name, A.FIXED.name)], mp.capital)
        ax.plot(s.index, s.values, color=col, lw=1.6, label=lab)
        _end_label(ax, s, f"{lab.split(' (')[0]}  {s.iloc[-1]:+.0f}%", col, dy)
    ax.axhline(0, color=AXIS, lw=0.8)
    ax.set_title("Naked ATM put with different futures delta hedges (fixed size, % of $1M capital)")
    ax.set_ylabel("% of starting capital")
    ax.legend(loc="upper left")
    ax.set_xlim(None, ax.get_xlim()[1] + 2600)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_campaigns(path: Path, camp: dict):
    led, sm = camp["ledger"], camp["summary"]
    x = led[led.status == "settled"].copy()
    x["exp"] = pd.to_datetime(x.expiry)
    pnl = x.pnl_usd / 1e3
    fig, ax = plt.subplots(figsize=(11, 5.8))
    w = 62
    up = pnl >= 0
    ax.bar(x.exp[up], pnl[up], width=w, color=GAIN, label="P&L of the quarter (profit)")
    ax.bar(x.exp[~up], pnl[~up], width=w, color=LOSS, label="P&L of the quarter (loss, put finished in the money)")
    ax.fill_between(x.exp, x.cum_loss_usd / 1e3, 0, step="post", color=S[6], alpha=0.16, lw=0)
    ax.step(x.exp, x.cum_loss_usd / 1e3, where="post", color=S[6], lw=1.6, label="Cumulated loss to win back (at expiry)")
    # mark only quarters whose worst day was clearly deeper than both where they started and ended
    deep = x.worst_cum_loss_in_quarter_usd < (np.minimum(x.cum_loss_usd.shift(1).fillna(0), x.cum_loss_usd) - 5000)
    ax.plot(x.exp[deep], x.worst_cum_loss_in_quarter_usd[deep] / 1e3, linestyle="none", marker="v", ms=6,
            mfc=SURFACE, mec=S[6], mew=1.4, label="Worst point inside the quarter (marked to market)")
    ax.axhline(0, color=AXIS, lw=0.8)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"-${abs(v):,.0f}k" if v < 0 else f"${v:,.0f}k"))
    i = x.cum_loss_usd.idxmin()
    ax.annotate(f"-${abs(x.cum_loss_usd[i]) / 1e3:,.0f}k at the {x.exp[i]:%b %Y} expiry", (x.exp[i], x.cum_loss_usd[i] / 1e3),
                xytext=(16, -2), textcoords="offset points", fontsize=9, color=INK2)
    j = x.worst_cum_loss_in_quarter_usd.idxmin()
    ax.annotate(f"-${abs(x.worst_cum_loss_in_quarter_usd[j]) / 1e3:,.0f}k inside the quarter to {x.exp[j]:%b %Y}, "
                f"holding {x.size_x[j]:.1f}x size", (x.exp[j], x.worst_cum_loss_in_quarter_usd[j] / 1e3),
                xytext=(12, -4), textcoords="offset points", fontsize=9, color=INK2)
    ax.set_title(f"$100k base notional from {pd.Timestamp(sm['first_roll']):%b %Y}, every loss won back in one quarter: "
                 "P&L per quarter and cumulated loss (USD)", fontsize=11)
    ax.set_ylabel("USD")
    ax.legend(loc="lower right", ncol=1)
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_campaign_variants(path: Path, cv: dict):
    show = [("naked", "Naked ATM put", S[0]), ("spread10", "+ long put 10% lower", S[1]),
            ("naked_h25_latch", "+ delta hedge from -2.5% to expiry", S[6]),
            ("naked_h5_latch", "+ delta hedge from -5% to expiry", S[2])]
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 7.4), sharex=True, gridspec_kw={"height_ratios": [1.2, 1]})
    for vid, lab, col in show:
        run = cv["variants"][vid]["recover"]["run"]
        pnl = (run.daily - 1e12) / 1e3
        # loss to win back = P&L below the highest SETTLED total (as in the tables), marked daily
        cyc = run.cycles[~run.cycles.open]
        settled_high = pd.Series(((cyc.equity - 1e12) / 1e3).values, index=pd.to_datetime(cyc.expiry)).cummax().clip(lower=0)
        high = settled_high.reindex(pnl.index.union(settled_high.index)).ffill().reindex(pnl.index).fillna(0)
        dd = (pnl - high).clip(upper=0)
        a1.plot(pnl.index, pnl.values, color=col, lw=1.6, label=lab)
        _end_label(a1, pnl, f"${pnl.iloc[-1]:,.0f}k", col)
        a2.plot(dd.index, dd.values, color=col, lw=1.2, label=lab)
    kfmt = matplotlib.ticker.FuncFormatter(lambda v, _: f"-${abs(v):,.0f}k" if v < 0 else f"${v:,.0f}k")
    for ax in (a1, a2):
        ax.yaxis.set_major_formatter(kfmt)
        ax.axhline(0, color=AXIS, lw=0.8)
    a1.set_title("Recovery rule from 2008 on $100k base notional: total P&L (USD)")
    a2.set_title("Cumulated loss to win back on any day, marked to market (USD)")
    a1.legend(loc="upper left")
    a2.xaxis.set_major_locator(mdates.YearLocator(2))
    a2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    a1.set_xlim(None, a1.get_xlim()[1] + 500)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# ----------------------------------------------------------------------------- markdown helpers
def _md_table(df: pd.DataFrame, fmt: dict | None = None) -> str:
    fmt = fmt or {}
    cols = list(df.columns)
    out = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            f = fmt.get(c)
            if f and pd.notna(v) and v != "":
                cells.append(f(v))
            elif isinstance(v, float):
                cells.append("" if pd.isna(v) else f"{v:.2f}")
            else:
                cells.append("" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def _row(grid: pd.DataFrame, st, hd, sz) -> pd.Series:
    m = grid[(grid.structure == st) & (grid.hedge == hd) & (grid.sizing == sz)]
    return m.iloc[0]


METRIC_COLS = {"ann_return_pct": "Return %/yr", "ann_vol_pct": "Vol %/yr", "sharpe": "Sharpe",
               "max_dd_pct_capital": "Max DD % cap.", "worst_quarter_pct": "Worst qtr %",
               "pct_quarters_up": "Qtrs up %", "max_mult": "Max size x", "ruined": "Wiped out"}
FMT = {"Return %/yr": lambda v: f"{v:.1f}", "Vol %/yr": lambda v: f"{v:.1f}", "Sharpe": lambda v: f"{v:.2f}",
       "Max DD % cap.": lambda v: f"{v:.0f}", "Worst qtr %": lambda v: f"{v:.1f}", "Qtrs up %": lambda v: f"{v:.0f}",
       "Max size x": lambda v: f"{v:.1f}"}


def _metric_table(rows: pd.DataFrame, label_cols: list[str], cols=None) -> str:
    cols = cols or list(METRIC_COLS)
    t = rows[label_cols + cols].rename(columns=METRIC_COLS).rename(columns={c: c.capitalize() for c in label_cols})
    if "Wiped out" in t:
        t["Wiped out"] = t["Wiped out"].fillna("").replace("", "no")
    return _md_table(t, FMT)


# ----------------------------------------------------------------------------- build
def build(root: Path, df, ctx, runs, grid, grid01, pt, sy, sens, lad, cal, cal_runs, pao, snap, camp) -> None:
    figs = root / "reports" / "figures"
    figs.mkdir(parents=True, exist_ok=True)
    mp = ctx.mp
    fig_premiums(figs / "1_premium_history.png", ctx, pt, snap)
    fig_fixed(figs / "2_fixed_size_structures.png", runs, mp)
    fig_recovery(figs / "3_recovery_sizing.png", runs, cal_runs, mp)
    fig_start_year(figs / "4_recovery_by_start_year.png", sy)
    fig_hedging(figs / "5_delta_hedging.png", runs, mp)
    fig_campaigns(figs / "6_recovery_2008.png", camp)
    fig_campaign_variants(figs / "7_recovery_2008_variants.png", camp["variants"])
    (root / "reports" / "REPORT.md").write_text(_markdown(df, ctx, runs, grid, grid01, pt, sy, sens, lad, cal,
                                                          pao, snap, camp))


def _usd(v: float) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ""
    return f"-${abs(v):,.0f}" if v < 0 else f"${v:,.0f}"


def _campaign_section(camp: dict) -> list[str]:
    sm, fx, led, cp, cal = camp["summary"], camp["fixed_summary"], camp["ledger"], camp["campaigns"], camp["calendars"]
    L: list[str] = []
    w = L.append
    worst = led.loc[led.worst_cum_loss_in_quarter_usd.idxmin()]
    w("## 9. From 2008: win back every loss in one quarter ($100k base, in dollars)\n")
    w(f"*Every quarter sells ATM puts on $100,000 of NQ notional, starting with the first 2008 roll ({sm['first_roll']}). "
      "After a loss the next put is sized so that, if it expires out of the money, its premium repays the whole cumulated "
      "loss plus the normal quarter's premium. A campaign starts with a loss and ends when the loss is won back; the next "
      "one starts again from $100,000. Profits are not reinvested and nothing limits the size, so the worst cumulated "
      "loss is what you must be able to carry.*\n")
    w(f"* **Normal P&L when the put expires OTM** (premium on $100k): average **{_usd(sm['base_premium_avg'])}** a quarter, "
      f"from {_usd(sm['base_premium_min'])} ({sm['base_premium_min_at']}) to {_usd(sm['base_premium_max'])} "
      f"({sm['base_premium_max_at']}).")
    w(f"* {sm['quarters']} quarters: {sm['n_otm']} expired OTM, {sm['n_itm_profit']} finished in the money but above "
      f"breakeven, {sm['n_losses']} lost money ({_usd(sm['loss_total'])} in total).")
    w(f"* **Total P&L:** {_usd(sm['total_pnl'])}, about {_usd(sm['total_pnl_per_year'])} a year, not reinvested.")
    w(f"* **Worst cumulated loss:** **{_usd(sm['worst_cum_loss'])}** at the {pd.Timestamp(sm['worst_cum_loss_at']):%b %Y} "
      f"expiry. Inside the next quarter ({sm['worst_cum_loss_mtm_quarter']}) it reached **{_usd(sm['worst_cum_loss_mtm'])}** "
      f"marked to market, while the rule held {worst.size_x:.2f}x size = {_usd(worst.notional_usd)} of notional.")
    w(f"* {sm['campaigns']} campaigns; every finished one was won back within {int(cp.loc[cp.won_back.str[:2] == '20', 'quarters'].max())} "
      "quarters.")
    w(f"* **Fixed size, no recovery** (same trades at $100k every quarter): {_usd(fx['total_pnl'])} total, worst cumulated "
      f"loss {_usd(fx['worst_cum_loss'])} ({_usd(fx['worst_cum_loss_mtm'])} on the worst day).")
    w("* **Other roll calendars from 2008:** " + "; ".join(
        f"{r.calendar}: worst {_usd(r.worst_cum_loss)} at expiry, {_usd(r.worst_cum_loss_mtm)} on the worst day, "
        f"biggest position {_usd(r.max_notional)}" for r in cal.itertuples() if r.calendar != "Mar/Jun/Sep/Dec") + ".")
    w(f"* **Capital:** holding {_usd(worst.notional_usd)} of puts needs margin of roughly {_usd(0.10 * worst.notional_usd)} "
      f"(10% of notional) on top of the {_usd(sm['worst_cum_loss_mtm'])} hole: about "
      f"{_usd(abs(sm['worst_cum_loss_mtm']) + 0.10 * worst.notional_usd)} of capital per $100k of base notional.\n")
    w("![campaigns](figures/6_recovery_2008.png)\n")
    t = cp.copy()
    t["recovery_quarter_pnl_usd"] = t.recovery_quarter_pnl_usd.map(lambda v: _usd(v) if pd.notna(v) else "")
    t = t[["started", "quarters", "losing_quarters", "worst_cum_loss_usd", "worst_cum_loss_mtm_usd", "max_size_x",
           "max_notional_usd", "won_back", "recovery_quarter_pnl_usd"]]
    t.columns = ["Campaign started", "Quarters", "Losing quarters", "Worst cumulated loss (expiry)", "Worst on any day",
                 "Biggest size (x)", "Biggest notional", "Won back at expiry", "P&L of the winning quarter"]
    w("**Campaigns** (from the first loss until it is won back):\n")
    w(_md_table(t, {"Quarters": lambda v: f"{int(v)}", "Losing quarters": lambda v: f"{int(v)}",
                    "Worst cumulated loss (expiry)": _usd, "Worst on any day": _usd,
                    "Biggest size (x)": lambda v: f"{v:.2f}", "Biggest notional": _usd}) + "\n")
    by = camp["by_year"].reset_index()
    by.columns = ["Year (expiries)", "Quarters", "OTM quarters", "Normal P&L if OTM (avg, $100k)", "P&L of OTM quarters",
                  "P&L of other quarters", "Worst cumulated loss (expiry)", "Worst on any day", "Biggest notional",
                  "Total P&L at year end"]
    fm = {c: _usd for c in by.columns[3:]}
    fm.update({c: (lambda v: f"{int(v)}") for c in by.columns[:3]})
    w("**By year:**\n")
    w(_md_table(by, fm) + "\n")
    q = led[["entry", "expiry", "normal_pnl_if_otm_usd", "size_x", "notional_usd", "premium_usd", "outcome", "pnl_usd",
             "cum_loss_usd", "worst_cum_loss_in_quarter_usd", "total_pnl_usd"]].copy()
    q.columns = ["Sold", "Expires", "Normal P&L if OTM ($100k)", "Size (x)", "Notional", "Premium", "Outcome", "P&L",
                 "Cumulated loss (expiry)", "Worst inside quarter", "Total P&L"]
    fq = {c: _usd for c in ["Normal P&L if OTM ($100k)", "Notional", "Premium", "P&L", "Cumulated loss (expiry)",
                            "Worst inside quarter", "Total P&L"]}
    fq["Size (x)"] = lambda v: f"{v:.2f}"
    w("**Every quarter:**\n")
    w(_md_table(q, fq) + "\n")
    w("CSV: [`results/recovery_2008_ledger.csv`](../results/recovery_2008_ledger.csv), "
      "[`results/recovery_2008_campaigns.csv`](../results/recovery_2008_campaigns.csv).\n")
    return L


def _variant_section(cv: dict) -> list[str]:
    t, rb = cv["table"].set_index("variant"), cv["robust"]
    L: list[str] = []
    w = L.append
    w("### 9.1 Buying the 10% OTM put, and delta hedging after a 2.5% or 5% fall\n")
    w("Same rule, same $100k base and start. Variants: the naked put; the put spread (sell the ATM put, buy the put 10% "
      "below it, same expiry); and NQ futures hedges that make the position delta-neutral (rebalanced daily) once NQ "
      "is 2.5% or 5% below the strike. *While below* removes the hedge when NQ climbs back above the trigger; "
      "*to expiry* keeps it until expiry once triggered. For the spread, the normal P&L is the net credit: the ATM "
      "premium minus the cost of the 10% OTM put.\n")
    w("*Premiums are neither fixed nor traded quotes. Each quarter's premium is priced on the sale date with Black-76 "
      "from that day's estimated implied volatility (VXN, calibrated to at-the-money levels, plus the VIX3M/VIX term "
      "structure), so it moves with the market. The 10% OTM put adds the model's skew (about +4.6 vol points at 3 months). "
      "Hedges trade NQ futures at modelled prices from daily Nasdaq-100 closes.*\n")
    tab = cv["table"][["label", "normal_pnl_if_otm", "total_pnl", "total_pnl_per_year", "worst_cum_loss",
                       "worst_cum_loss_mtm", "max_size_x", "max_notional", "capital_needed", "fixed_total_pnl",
                       "fixed_worst_cum_loss_mtm"]].copy()
    tab.columns = ["Variant (from 2008, Mar/Jun/Sep/Dec)", "Normal P&L if OTM", "Total P&L", "Per year",
                   "Worst cumulated loss (expiry)", "Worst on any day", "Biggest size (x)", "Biggest notional",
                   "Capital needed", "Fixed size: total P&L", "Fixed size: worst day"]
    fm = {c: _usd for c in tab.columns[1:]}
    fm["Biggest size (x)"] = lambda v: f"{v:.1f}"
    w(_md_table(tab, fm) + "\n")
    w("![variants](figures/7_recovery_2008_variants.png)\n")
    piv = rb.pivot_table(index="variant", columns=["start_year", "calendar"], values="worst_cum_loss_mtm", sort=False)
    order = [v for v in t.index]
    rows = []
    for v in order:
        r = {"Variant": t.loc[v, "label"]}
        for sy_, cal_ in [(2008, "Mar/Jun/Sep/Dec"), (2008, "Jan/Apr/Jul/Oct"), (2008, "Feb/May/Aug/Nov"),
                          (1990, "Mar/Jun/Sep/Dec"), (1990, "Jan/Apr/Jul/Oct"), (1990, "Feb/May/Aug/Nov")]:
            r[f"{sy_} {cal_[:3]}"] = piv.loc[v, (sy_, cal_)]
        sub = rb[rb.variant == v]
        r["Biggest size, any test"] = sub.max_size_x.max()
        rows.append(r)
    rt = pd.DataFrame(rows)
    fr = {c: _usd for c in rt.columns if c[:4] in ("2008", "1990")}
    fr["Biggest size, any test"] = lambda v: f"{v:.0f}x"
    w("**Worst cumulated loss on any day, every roll calendar, starting 2008 and 1990** (USD, $100k base):\n")
    w(_md_table(rt, fr) + "\n")
    def rng(v, year):
        x = rb[(rb.variant == v) & (rb.start_year == year)].worst_cum_loss_mtm
        return f"{_usd(x.max())} to {_usd(x.min())}"

    def per_year(v):
        return _usd(t.loc[v, "total_pnl_per_year"])

    sp = rb[rb.variant == "spread10"]
    w(f"* **The 10% OTM put does not make the recovery rule safe.** It lowers the normal P&L from "
      f"{_usd(t.loc['naked', 'normal_pnl_if_otm'])} to {_usd(t.loc['spread10', 'normal_pnl_if_otm'])} a quarter, so "
      f"winning back a loss needs a bigger multiple: up to {t.loc['spread10', 'max_size_x']:.0f}x from 2008 and "
      f"{sp.max_size_x.max():.0f}x in the tests from 1990. Worst day from 2008: {rng('spread10', 2008)} across the three "
      f"calendars (naked {rng('naked', 2008)}). What it does cap is the margin: about "
      f"{_usd(t.loc['spread10', 'capital_needed'])} of capital per $100k instead of {_usd(t.loc['naked', 'capital_needed'])}. "
      f"At fixed size it is a clean risk cut: worst day {_usd(t.loc['spread10', 'fixed_worst_cum_loss_mtm'])} vs "
      f"{_usd(t.loc['naked', 'fixed_worst_cum_loss_mtm'])}.")
    w(f"* **Hedging after the fall and keeping the hedge to expiry worked best.** From -5%: worst day {rng('naked_h5_latch', 2008)} "
      f"from 2008 and {rng('naked_h5_latch', 1990)} from 1990, for {per_year('naked_h5_latch')} a year (naked "
      f"{per_year('naked')}). From -2.5%: {rng('naked_h25_latch', 2008)} from 2008 and {rng('naked_h25_latch', 1990)} from "
      f"1990, but only {per_year('naked_h25_latch')} a year, because it hedges far more quarters and every hedge loss "
      f"raises the next recovery size (up to {rb[rb.variant == 'naked_h25_latch'].max_size_x.max():.0f}x, vs "
      f"{rb[rb.variant == 'naked_h5_latch'].max_size_x.max():.0f}x from -5%).")
    w(f"* **Hedges that switch off when NQ bounces back were unstable:** from 2008 the worst day was "
      f"{rng('naked_h25', 2008)} (below -2.5%) and {rng('naked_h5', 2008)} (below -5%), and from 1990 down to "
      f"{_usd(rb[rb.variant == 'naked_h5'].worst_cum_loss_mtm.min())}. In choppy markets (early 2009) the hedge goes on low "
      "and comes off high, and each of those losses raises the next recovery size.")
    w("* With unlimited sizing, every variant still has a worst case far above its normal quarterly income. Fixed size "
      "keeps all the holes small.\n")
    return L


def _h5_section(h5: dict) -> list[str]:
    q, cases = h5["quarters"], h5["summary"].set_index("case")
    br, bf, er = h5["breakdown_recover"], h5["breakdown_fixed"], h5["equal_risk"]
    trig = q[q.case.str.startswith("fell")]
    reb = q[q.case.str.contains("rebounded")]
    worst_reb = reb.loc[reb.hedge_effect_usd.idxmin()]
    settled = q[q.case != "open quarter"]
    L: list[str] = []
    w = L.append
    w("### 9.2 Inside \"hedge from -5% until expiry\"\n")
    w("**How it works.** Nothing happens until NQ closes 5% below the put's strike. That day the position sells NQ futures "
      "equal to the put's delta, which makes it delta-neutral. Every day until expiry the hedge is re-sized to the put's "
      "delta: if NQ keeps falling, more futures are sold (up to about one future per put when deep in the money); if NQ "
      "rises, futures are bought back. The position is never net short. At expiry the futures and the put settle "
      "together.\n")
    w(f"**Did the rebound effect happen? Yes.** Per $100k of notional at fixed size (no recovery sizing), "
      f"{len(trig)} of {len(settled)} quarters since 2008 switched the hedge on:\n")
    c = h5["summary"].copy()
    c.columns = ["What NQ did after the trigger", "Quarters", "Naked put P&L", "With the hedge", "Hedge effect",
                 "Average effect", "Worst effect", "Best effect"]
    w(_md_table(c, {k: _usd for k in c.columns[2:]} | {"Quarters": lambda v: f"{int(v)}"}) + "\n")
    w(f"* In all {len(reb)} quarters where NQ fell through -5% and then finished above the strike, the naked put would "
      f"have kept its whole premium, but the hedged version lost money: the futures sold on the way down were bought back "
      f"higher on the way up. Cost {_usd(cases.loc['fell through the trigger, then rebounded above the strike', 'hedge_effect_usd'])} "
      f"in total. The strongest rebound was {worst_reb.entry} to {worst_reb.expiry}: NQ fell {abs(worst_reb.low_vs_strike_pct):.1f}% "
      f"below the strike, then rose {worst_reb.rebound_from_low_pct:.1f}% from the low; the hedge (up to "
      f"{_usd(worst_reb.max_short_futures_usd)} of futures) lost {_usd(worst_reb.hedge_pnl_usd)}.")
    w("* The damage stays limited because the hedge shrinks as NQ rises: by the time NQ is back above the strike the "
      "put's delta is small and so is the short. The loss is the round trip (sell low, buy back high), not an open "
      "short position into a rally.")
    w(f"* When NQ kept falling, the hedge paid: {_usd(cases.loc['fell through the trigger and stayed down', 'hedge_effect_usd'])} "
      f"over {int(cases.loc['fell through the trigger and stayed down', 'quarters'])} quarters, the best "
      f"{_usd(cases.loc['fell through the trigger and stayed down', 'best_effect_usd'])} in a single quarter.")
    w(f"* Net, the hedge cost {_usd(cases.loc['all quarters', 'hedge_effect_usd'])} per $100k since 2008. That is the "
      f"price of the protection. Every hedged quarter ended between {_usd(trig.hedged_pnl_usd.min())} and "
      f"{_usd(trig.hedged_pnl_usd.max())}, so the worst quarter improved from {_usd(settled.naked_pnl_usd.min())} to "
      f"{_usd(settled.hedged_pnl_usd.min())}.\n")
    w("**Why it looks so good with the recovery rule.** The hedge turns rare big losses into frequent small ones. Small "
      "losses need only a modest size increase to win back, so the recovery rule rarely escalates. The trade-off is "
      "that about one quarter in three becomes a small loss.\n")
    t = pd.DataFrame([{"Sizing": "Recovery rule", **br.loc["total"].to_dict()},
                      {"Sizing": "Fixed size", **bf.loc["total"].to_dict()}])
    t = t[["Sizing", "premium_usd", "payout_usd", "hedge_pnl_usd", "hedge_cost_usd", "pnl_usd", "worst_cum_loss_any_day_usd",
           "max_size_x"]]
    t.columns = ["From 2008, $100k base", "Premiums kept", "Put payouts", "Hedge P&L", "Hedge trading costs", "Total P&L",
                 "Worst day", "Biggest size"]
    w("**Overall profitability** (USD, Mar/Jun/Sep/Dec calendar; premiums are net of option trading costs):\n")
    w(_md_table(t, {k: _usd for k in t.columns[1:7]} | {"Biggest size": lambda v: f"{v:.1f}x"}) + "\n")
    yb = br.drop(index="total").reset_index()
    yb.columns = ["Year", "Premiums kept", "Put payouts", "Hedge P&L", "Hedge costs", "P&L", "Worst day", "Biggest size"]
    w("By year, recovery rule:\n")
    w(_md_table(yb, {k: _usd for k in yb.columns[1:7]} | {"Year": lambda v: f"{int(v)}", "Biggest size": lambda v: f"{v:.1f}x"}) + "\n")
    e = er[["test", "recovery_pnl_per_year", "recovery_worst_day", "recovery_capital_needed", "fixed_multiple_same_worst_day",
            "fixed_same_risk_pnl_per_year", "fixed_same_risk_capital"]].copy()
    e.columns = ["Test", "Recovery rule: per year", "Worst day", "Capital needed", "Fixed size with the same worst day",
                 "Fixed: per year", "Fixed: capital needed"]
    wins = int((er.fixed_same_risk_pnl_per_year > er.recovery_pnl_per_year).sum())
    w("**Does the recovery rule add anything?** Compare it with simply trading a bigger fixed size that has the same worst "
      "day:\n")
    w(_md_table(e, {"Recovery rule: per year": _usd, "Worst day": _usd, "Capital needed": _usd,
                    "Fixed size with the same worst day": lambda v: f"{v:.2f}x", "Fixed: per year": _usd,
                    "Fixed: capital needed": _usd}) + "\n")
    w(f"At the same worst-day loss, the bigger fixed size earned more in {wins} of {len(er)} tests and always needed less "
      "capital. The value is in the hedge; the recovery sizing mostly adds calendar luck.\n")
    cm = h5["calmar"]
    piv = cm.pivot_table(index=["variant", "sizing"], columns=["start_year", "calendar"], values="calmar", sort=False)
    rows = []
    for (v, z), r in piv.iterrows():
        d = {"Variant": v, "Sizing": z}
        for sy_ in (2008, 1990):
            for cal_ in ("Mar/Jun/Sep/Dec", "Jan/Apr/Jul/Oct", "Feb/May/Aug/Nov"):
                d[f"{sy_} {cal_[:3]}"] = r[(sy_, cal_)]
        vals = [r[c] for c in piv.columns]
        d["Median"] = float(np.median(vals))
        rows.append(d)
    ct = pd.DataFrame(rows)
    main = cm[(cm.variant == "Hedge from -5% to expiry") & (cm.start_year == 2008) & (cm.calendar == "Mar/Jun/Sep/Dec")]
    w("**Calmar ratio** = average annual P&L / largest peak-to-trough drawdown of the daily marked P&L. Profits are not "
      "reinvested, so both are in dollars and the ratio does not depend on account size:\n")
    w(_md_table(ct, {c: (lambda v: f"{v:.2f}") for c in ct.columns[2:]}) + "\n")
    rec = main[main.sizing == "Recovery rule"].iloc[0]
    fx = main[main.sizing == "Fixed size"].iloc[0]
    w(f"From 2008 on the Mar/Jun/Sep/Dec calendar the hedge scores {rec.calmar:.2f} with the recovery rule "
      f"({_usd(rec.pnl_per_year)} a year over a {_usd(-rec.max_drawdown)} drawdown) and {fx.calmar:.2f} at fixed size. "
      f"That is the best of the six tests; including the dot-com bust (from 1990) it drops to "
      f"{cm[(cm.variant == 'Hedge from -5% to expiry') & (cm.start_year == 1990)].calmar.min():.2f}-"
      f"{cm[(cm.variant == 'Hedge from -5% to expiry') & (cm.start_year == 1990)].calmar.max():.2f}.\n")
    return L


def _markdown(df, ctx, runs, grid, grid01, pt, sy, sens, lad, cal, pao, snap, camp) -> str:
    mp = ctx.mp
    settled = pt[pt.status == "settled"]
    nq = A.NAKED.name
    nh, fx, rc = A.NO_HEDGE.name, A.FIXED.name, A.RECOVER.name
    ps10, ps20 = A.STRUCTURES[2].name, A.STRUCTURES[4].name
    base = _row(grid, nq, nh, fx)
    fut = _row(grid, A.BENCH.name, nh, fx)
    rec = _row(grid, nq, nh, rc)
    p10 = _row(grid, ps10, nh, fx)
    cap = _row(grid, nq, A.HEDGES[4].name, fx)
    dh = _row(grid, nq, A.HEDGES[1].name, fx)
    first, last = settled.entry.iloc[0], settled.expiry.iloc[-1]
    wins = settled.naked_pnl_pct_notional > 0
    q = snap["indicative_quotes"][0]
    op = snap.get("open_position", {})
    vrp = A.vrp_stats(ctx)
    avg_win = settled.naked_pnl_pct_notional[settled.naked_pnl_pct_notional > 0].mean()
    avg_loss = settled.naked_pnl_pct_notional[settled.naked_pnl_pct_notional < 0].mean()
    wings = grid[(grid.hedge == A.NO_HEDGE.name) & (grid.sizing == A.FIXED.name)].set_index("structure")
    sens_dh = sens[sens.strategy.str.contains("Delta hedge daily")].set_index("scenario")
    sy_r = sy.groupby("strategy").ruined.apply(lambda s: int((s.fillna("").astype(str).str.len() > 0).sum()))
    n_years = sy.start_year.nunique()
    calp = cal.copy()

    def calrow(cal_name, st, hd, sz):
        r = calp[(calp.calendar == cal_name) & (calp.structure == st) & (calp.hedge == hd) & (calp.sizing == sz)]
        return r.iloc[0]

    rec_ruins = {k: sy_r.get(f"{s} | {nh} | {z}", 0) for k, s, z in
                 [("naked", nq, rc), ("ps10", ps10, rc), ("ps20", ps20, rc), ("once", nq, A.SIZINGS[2].name)]}
    by_year = A.premium_by_year(pt)
    dec = settled.assign(decade=(pd.to_datetime(settled.entry).dt.year // 10 * 10).astype(str) + "s")
    dec_t = dec.groupby("decade").agg(rolls=("entry", "size"), iv=("atm_iv_3m_pct", "mean"),
                                       prem=("put_premium_pct", "mean"), usd=("put_premium_usd_per_NQ", "mean"),
                                       itm=("expired_itm", "mean"), pnl=("naked_pnl_pct_notional", "mean")).reset_index()
    dec_t.columns = ["Decade", "Rolls", "Avg 3M ATM IV %", "Avg premium % of notional", "Avg premium $ per NQ",
                     "Share expired ITM", "Avg naked P&L % per qtr"]
    dec_fmt = {"Avg 3M ATM IV %": lambda v: f"{v:.1f}", "Avg premium % of notional": lambda v: f"{v:.2f}",
               "Avg premium $ per NQ": lambda v: f"${v:,.0f}", "Share expired ITM": lambda v: f"{100 * v:.0f}%",
               "Avg naked P&L % per qtr": lambda v: f"{v:+.2f}"}

    L: list[str] = []
    w = L.append
    w("# Selling 3-month ATM puts on Nasdaq-100 futures (NQ): backtest 1986-2026\n")
    w(f"*Data through {snap['as_of']}. {len(settled)} settled quarterly rolls, {first} to {last}. "
      "All option prices are **model estimates** (free historical NQ option quotes do not exist). "
      "See [Method](#1-what-was-tested) and [Limitations](#10-limitations).*\n")
    w("## TL;DR: what to take from this\n")
    w(f"1. **Premiums.** A 3-month ATM put on NQ paid on average **{settled.put_premium_pct.mean():.1f}% of notional** "
      f"(median {settled.put_premium_pct.median():.1f}%, range {settled.put_premium_pct.min():.1f}% in 2017 to "
      f"{settled.put_premium_pct.max():.1f}% in 2001). At today's index that is about **${settled.put_premium_pct.mean() / 100 * snap['ndx'] * 20:,.0f} per NQ contract**. "
      f"Right now (VXN {snap['vxn']:.1f}) the estimate is **{100 * q['atm_put_pct']:.1f}%, about ${q['atm_put_usd_per_NQ']:,.0f} per NQ**, "
      "richer than the long-run average.")
    w(f"2. **Plain strategy** (sell one ATM put per $1 of notional every quarter, hold to expiry): "
      f"**{base.ann_return_pct:+.1f}%/yr** on notional, {base.pct_quarters_up:.0f}% winning quarters. But the losses are big: "
      f"worst quarter {base.worst_quarter_pct:.0f}%, max drawdown **{base.max_dd_pct_capital:.0f}% of notional** (2000-02). "
      f"Sharpe {base.sharpe:.2f}, while simply holding 0.5x NQ futures (the put's average delta) had Sharpe {fut.sharpe:.2f}. "
      "Almost all of the put's profit is Nasdaq beta. The volatility premium in ATM NDX options is thin: "
      f"3-month ATM implied vol was on average only {vrp['mean_gap']:.1f} vol pts (median {vrp['median_gap']:.1f}) above the "
      "realized vol that followed.")
    w(f"3. **Increasing size after an ITM loss to win it back is a martingale, and it is the main risk in the plan.** "
      f"On the Mar/Jun/Sep/Dec calendar it lifted returns to {rec.ann_return_pct:.1f}%/yr. To do that it needed up to "
      f"**{rec.max_mult:.0f}x size** and suffered a {rec.worst_quarter_pct:.0f}% quarter (drawdown {rec.max_dd_pct_capital:.0f}% of capital). "
      "It survived 2000-02 only because the ~11x position sold in March 2001 happened to expire out of the money. "
      f"The *same rule* on the Jan/Apr/Jul/Oct or Feb/May/Aug/Nov calendars **wiped out the account in 2001**. "
      f"By start year it was wiped out in {rec_ruins['naked']}/{n_years} start years (naked) and in "
      f"{rec_ruins['ps10']}/{n_years} and {rec_ruins['ps20']}/{n_years} start years with -10%/-20% put spreads. "
      "For the naked put, every softened version (max 3x, recover once, recover over 4 quarters, 200-day trend filter) "
      "still lost more than 100% of starting capital at its worst point on at least one calendar. The mildest version, "
      "'recover once' on a -10% put spread, stayed below that but deepened drawdowns from 36-53% to 51-85% for little or no "
      "Sharpe gain. **Don't upsize after losses.**")
    w(f"4. **Buying an OTM put (put spread)** is a risk dial, not an edge. With a -10% wing the worst quarter is "
      f"{p10.worst_quarter_pct:.0f}% (vs {base.worst_quarter_pct:.0f}%) and the max drawdown {p10.max_dd_pct_capital:.0f}% "
      f"(vs {base.max_dd_pct_capital:.0f}%), but the return halves to {p10.ann_return_pct:.1f}%/yr; Sharpe {p10.sharpe:.2f} vs {base.sharpe:.2f}. "
      "Put spreads make the martingale *worse*: the net credit is smaller, so 'recovering' needs larger multipliers.")
    w(f"5. **Delta hedging.** A full daily futures hedge strips out the equity premium and leaves only the thin vol premium: "
      f"{dh.ann_return_pct:+.1f}%/yr. That figure is fragile: it ranges from {sens_dh.loc['Implied vol -10%', 'ann_return_pct']:+.1f}% to "
      f"{sens_dh.loc['Implied vol +10%', 'ann_return_pct']:+.1f}%/yr if true implied vol was 10% lower or higher than estimated. "
      f"The one hedge that helped on every calendar is a **delta cap**: short futures only for the delta the put gains *above its entry delta* as NQ falls. "
      f"It returned {cap.ann_return_pct:.1f}%/yr at Sharpe {cap.sharpe:.2f} (vs {base.sharpe:.2f}) with max drawdown {cap.max_dd_pct_capital:.0f}% "
      f"(vs {base.max_dd_pct_capital:.0f}%).")
    lose, winr = pao.loc["after a losing quarter"], pao.loc["after a winning quarter"]
    w(f"6. **How to get your 'recovery' without a martingale.** After a losing quarter implied vol is higher, so the *same size* "
      f"already collects more: on average {lose.avg_premium_pct:.1f}% of notional vs {winr.avg_premium_pct:.1f}% after a win, and the "
      f"next quarter averaged {lose.next_q_naked_pnl_pct:+.1f}% vs {winr.next_q_naked_pnl_pct:+.1f}%. Size for survival instead: "
      f"the naked put lost {base.max_dd_pct_capital:.0f}% of its notional in 2000-02, so naked notional of about 0.3-0.5x equity "
      f"would have cost {0.3 * base.max_dd_pct_capital:.0f}-{0.5 * base.max_dd_pct_capital:.0f}% of the account in that scenario. "
      "Cap the tail with a -15% to -20% wing or a delta cap. "
      "Ladder entries monthly (1/3 of the size per cycle) so results do not hinge on one roll date.")
    if op:
        w(f"7. **Today ({snap['as_of']}).** The 3-month put sold {op['entry']} (strike ~{op['strike']:,.0f}, "
          f"premium ~{op['premium_pts']:,.0f} pts = ${op['premium_usd_per_NQ']:,.0f}/NQ) is **in the money**. NQ is about "
          f"{op['futures_now']:,.0f}, the put is worth ~{op['put_value_now_pts']:,.0f} pts, and the mark-to-market P&L is "
          f"~{op['pnl_to_date_pts']:+,.0f} pts ({_money(op['pnl_to_date_pts'] * 20, True)} per NQ). It has {op['days_left']} days left and delta ~{op['delta_now']:.2f}. "
          "Under your rule, a loss at the 18-Dec expiry would trigger a bigger position. The backtest says roll at normal size, "
          "because today's rich premium already does part of the recovery.\n")

    csm, cfx = camp["summary"], camp["fixed_summary"]
    w(f"8. **From 2008, winning back every loss in one quarter (section 9).** On $100k of base notional, not reinvested: "
      f"a normal quarter that expires OTM pays about {_usd(csm['base_premium_avg'])}; total P&L {_usd(csm['total_pnl'])} "
      f"(fixed size: {_usd(cfx['total_pnl'])}). The worst cumulated loss was {_usd(csm['worst_cum_loss'])} at an expiry and "
      f"{_usd(csm['worst_cum_loss_mtm'])} inside a quarter, holding up to {csm['max_size_x']:.1f}x size "
      f"({_usd(csm['max_notional'])} of notional).\n")
    w("## 1. What was tested\n")
    w("* **Trade.** At the close of each quarterly NQ expiry (3rd Friday of Mar/Jun/Sep/Dec), sell the put that expires "
      "at the next quarterly expiry (~13 weeks) with the **strike at the futures price (ATM-forward)**. Hold it to expiry. "
      "Settlement uses the NDX close on expiry day. 1 NQ option = $20 x index.")
    w("* **Size.** Base position = $1,000,000 notional (= 1.0x a $1M account; ~1.8 NQ at today's level). Sizes are fractional. "
      "Profits are not reinvested, so every quarter of 40 years counts equally. "
      "Returns, drawdowns and quarters are all in % of the $1M starting capital (= base notional).")
    w("* **Pricing.** Black-76 on the NQ future, with F = NDX x exp((r - q)T), T-bill r and q = 0.7%. Implied vol is estimated as:")
    d = ctx.diag
    w(f"  1. 30-day level = **VXN** (actual since {d['vxn_proxy']['fit_from']}). Before that VXN is reconstructed from VIX "
      f"(or VXO before 1990) and the NDX/SPX realized-vol ratio: regression R² {d['vxn_proxy']['r2']:.2f}.")
    a = d.get("atm_vs_vxn", {})
    w(f"  2. ATM vol = {a.get('a', -2.3):.2f} + {a.get('b', 0.98):.3f} x VXN. VXN is a variance-swap-style index that includes "
      f"skew, so it sits above ATM. This line is calibrated on Nasdaq's **VOLQ** at-the-money NDX vol index "
      f"({a.get('window', '')}, mean ATM/VXN = {a.get('mean_ratio', 0.89):.2f}).")
    w(f"  3. 3-month ATM vol = 30-day ATM vol x **VIX3M/VIX** term-structure ratio (regression proxy before 2006, "
      f"R² {d['term_structure_proxy']['r2']:.2f}).")
    w("  4. Put skew: sigma(K) = sigma_ATM + 0.22/sqrt(T) x ln(F/K). For 3 months that is about +4.6 vol pts at a 10% OTM strike, "
      "and the 25-delta risk reversal is about -4.5 vols, typical for NDX.")
    w("* **Costs.** Options trade 0.5 vol pt worse than model mid (about 2-3% of the ATM premium), plus $2.50 per contract. "
      "Futures hedges cost 1 bp of notional per side. Daily mark-to-market at model mid.")
    w("* **Margin and ruin.** Margin is assumed at 10% of notional for a naked put, or the max loss for a spread. A position "
      "is cut back if equity cannot carry it. 'Wiped out' means account equity reached zero.")
    w("* **Recovery sizing (your rule).** Next size = 1 + (drawdown from equity high) / (premium per $1 of notional). "
      "If the new put expires worthless it repays the whole deficit and still earns the normal premium (the 'earn a bit'). "
      "Variants tested: *recover once* (only one upsized quarter after a base-size loss), *max 3x*, "
      "*recover over 4 quarters*, and *+ 200-day trend filter* (stand aside when NDX < 200-day average).")
    w("* **Hedges.** Full delta hedge daily or weekly, 50% hedge, *delta cap* (short futures only for delta above the entry delta), "
      "and *stop hedge* (fully delta-hedged only while the put is ITM).\n")

    w("## 2. Premium history\n")
    w("![premium history](figures/1_premium_history.png)\n")
    w(_md_table(dec_t, dec_fmt) + "\n")
    w(f"Over all rolls: {100 * settled.expired_itm.mean():.0f}% expired ITM, but only {100 * (~wins).mean():.0f}% lost money, "
      f"because the premium absorbs small dips. Average winning quarter **{avg_win:+.1f}%**, "
      f"average losing quarter **{avg_loss:+.1f}%** of notional. One loss wipes out about {abs(avg_loss) / avg_win:.1f} wins, "
      "which is why the win rate looks great while the equity curve does not.\n")
    worst = settled.nsmallest(8, "naked_pnl_pct_notional")[["entry", "expiry", "atm_iv_3m_pct", "put_premium_pct",
                                                            "ndx_move_pct", "naked_pnl_pct_notional",
                                                            "spread10_pnl_pct_notional", "spread20_pnl_pct_notional"]]
    worst.columns = ["Sold", "Expiry", "IV %", "Premium %", "NDX move %", "Naked P&L %", "Spread -10% P&L %",
                     "Spread -20% P&L %"]
    w("**Worst quarters** (% of notional):\n")
    w(_md_table(worst) + "\n")
    w("Per-year detail (expiry year; premium $ per NQ is at that year's index level): "
      "[`results/premiums_by_year.csv`](../results/premiums_by_year.csv). Every roll: "
      "[`results/premiums_quarterly.csv`](../results/premiums_quarterly.csv).\n")
    yt = by_year.tail(12).reset_index()[["year", "avg_atm_iv_3m_pct", "avg_premium_pct", "avg_premium_usd_per_NQ",
                                         "expired_itm", "naked_pnl_pct", "ndx_move_pct"]]
    yt.insert(1, "rolls", by_year.tail(12)["rolls"].values)
    yt.columns = ["Year", "Rolls", "Avg IV %", "Avg premium %", "Avg premium $/NQ", "Expired ITM", "Naked P&L % (year)",
                  "NDX move %"]
    w(_md_table(yt, {"Avg premium $/NQ": lambda v: f"${v:,.0f}", "Expired ITM": lambda v: f"{int(v)}",
                     "Year": lambda v: f"{int(v)}", "Rolls": lambda v: f"{int(v)}"}) + "\n")

    w("## 3. Results at fixed size\n")
    w("![fixed size](figures/2_fixed_size_structures.png)\n")
    rows = grid[(grid.hedge == nh) & (grid.sizing == fx)].copy()
    w(_metric_table(rows, ["structure"], [c for c in METRIC_COLS if c not in ("max_mult", "ruined")]) + "\n")
    w(f"*Long NQ futures 1x is shown at full notional. At 0.5x (roughly the put's average delta) it returns "
      f"{fut.ann_return_pct / 2:.1f}%/yr at the same Sharpe {fut.sharpe:.2f} with max drawdown {fut.max_dd_pct_capital / 2:.0f}%.*\n")
    g1 = grid01[(grid01.hedge == nh) & (grid01.sizing == fx)].copy()
    w("Since 2001 (actual VXN only):\n")
    w(_metric_table(g1, ["structure"], ["ann_return_pct", "sharpe", "max_dd_pct_capital", "worst_quarter_pct"]) + "\n")

    w("## 4. Recovery sizing: \"next 3 months increase size to cover the loss\"\n")
    w("![recovery](figures/3_recovery_sizing.png)\n")
    t = cal[(cal.hedge == nh) & cal.structure.isin([nq, ps10])].copy()
    t["label"] = t.structure.str.replace("Put spread ATM/", "Spread ") + " · " + t.sizing
    piv = t.pivot_table(index="label", columns="calendar", values="max_dd_pct_capital", sort=False)
    piv_r = t.pivot_table(index="label", columns="calendar", values="ann_return_pct", sort=False)
    ruin = t.assign(r=t.ruined.fillna("")).pivot_table(index="label", columns="calendar", values="r", aggfunc="first",
                                                       sort=False)
    cals = list(A.CALENDARS)
    out = pd.DataFrame(index=piv.index)
    for cname in cals:
        out[cname] = [
            (f"**wiped out {ruin.loc[i, cname][:7]}**" if ruin.loc[i, cname] else
             f"{piv_r.loc[i, cname]:+.1f}%/yr, DD {piv.loc[i, cname]:.0f}%")
            for i in out.index]
    w("Same rule on the three possible 3-month roll calendars (return %/yr and max drawdown as % of starting capital):\n")
    w(_md_table(out.reset_index().rename(columns={"label": "Structure · sizing"})) + "\n")
    w("![start year](figures/4_recovery_by_start_year.png)\n")
    ep = settled.assign(d=pd.to_datetime(settled.entry))
    e1 = ep[(ep.d >= "2000-03-01") & (ep.d < "2002-10-01")]
    w(f"Why it fails: losses cluster. In the 2000-02 bust {int((e1.naked_pnl_pct_notional < 0).sum())} of {len(e1)} "
      "quarterly puts lost money. Each loss raises the next size by (loss / next premium). A -25% quarter followed by a 5% "
      "premium means 6x size, and a second loss at 6x costs 150% of base notional. So two or three losses in a row "
      "compound to 10-30x size, right when volatility and gap risk are highest. Richer premiums after losses do not offset "
      "this. The rule turns a once-a-decade drawdown into an account-ending one, and survival depends on which month "
      "you happen to roll in.\n")

    w("## 5. Buying the OTM put\n")
    rows = grid[(grid.hedge == nh) & grid.sizing.isin([fx, rc, A.SIZINGS[2].name])].copy()
    w(_metric_table(rows, ["structure", "sizing"]) + "\n")
    wq = [wings.loc[A.STRUCTURES[i].name, "worst_quarter_pct"] for i in range(1, 5)]
    wsh = [wings.loc[A.STRUCTURES[i].name, "sharpe"] for i in range(1, 5)]
    w(f"The wing caps the loss. The naked put's worst quarter was {wings.loc[A.NAKED.name, 'worst_quarter_pct']:.0f}%. "
      f"With -5/-10/-15/-20% wings it is {' / '.join(f'{v:.0f}%' for v in wq)}. "
      f"Return falls about in proportion: Sharpe is {' / '.join(f'{v:.2f}' for v in wsh)} vs "
      f"{wings.loc[A.NAKED.name, 'sharpe']:.2f} naked. Skew makes the protective put relatively expensive "
      "(+2 to +10 vol pts over ATM), so the tightest wing (-5%) is the worst deal. "
      "Prefer -15% to -20% wings to remove the catastrophe while keeping most of the income.\n")

    w("## 6. Delta hedging\n")
    w("![hedging](figures/5_delta_hedging.png)\n")
    rows = grid[(grid.structure == nq) & (grid.sizing == fx)].copy()
    w(_metric_table(rows, ["hedge"], [c for c in METRIC_COLS if c not in ("max_mult", "ruined")]) + "\n")
    hc = cal[(cal.structure == nq) & (cal.sizing == fx)].pivot_table(index="hedge", columns="calendar",
                                                                       values="sharpe", sort=False)
    hc = hc.reindex([h.name for h in A.HEDGES])
    w("Sharpe ratio on each roll calendar (robustness):\n")
    w(_md_table(hc.reset_index().rename(columns={"hedge": "Hedge"}),
                {c: (lambda v: f"{v:.2f}") for c in cals}) + "\n")
    bd = vrp["by_decade"]
    w("* **Full delta hedge**: P&L ≈ ½·Γ·S²·(σ_implied² − σ_realized²). For 3-month NDX ATM options the implied-minus-realized "
      f"gap averaged {vrp['mean_gap']:+.1f} vol pts (by decade: "
      + ", ".join(f"{k}s {v:+.1f}" for k, v in bd.items())
      + "), so after costs very little is left. Hedging *put spreads* is negative because you are long the expensive skew.")
    w("* **Delta cap** keeps the original ~0.5 delta exposure (the equity premium is where the money came from) but stops the "
      "short put from getting *longer* as the market falls. That is the convexity that hurts in crashes.")
    w("* **Stop hedge** (hedge only while ITM) cuts drawdowns but whipsaws: it buys high and sells low around the strike.\n")

    w("## 7. Robustness and sensitivity\n")
    sv = sens.pivot_table(index="scenario", columns="strategy", values="ann_return_pct", sort=False)
    sd = sens.pivot_table(index="scenario", columns="strategy", values="sharpe", sort=False)
    combos = list(sv.columns)
    short = {c: c.replace("Naked ATM put", "Naked").replace("Put spread ATM/-10%", "Spread -10%")
             .replace(" | No hedge", "").replace(" | ", ", ").replace("Recover until whole", "recover")
             .replace("Fixed 1x", "fixed").replace("Delta hedge daily", "delta-hedged") for c in combos}
    so = pd.DataFrame(index=sv.index)
    ruined_s = sens.assign(r=sens.ruined.fillna("")).pivot_table(index="scenario", columns="strategy", values="r",
                                                                 aggfunc="first", sort=False)
    for c in combos:
        so[short[c]] = [("wiped out " + str(ruined_s.loc[i, c])[:4]) if ruined_s.loc[i, c] else
                        f"{sv.loc[i, c]:+.1f}% ({sd.loc[i, c]:.2f})" for i in so.index]
    w("Return %/yr (Sharpe) under alternative assumptions:\n")
    w(_md_table(so.reset_index().rename(columns={"scenario": "Scenario"})) + "\n")
    w(f"Laddering (1/3 of the size on each monthly cycle) vs single calendars, fixed size, since 1990:\n")
    lt = lad.copy()
    lt = lt[["structure", "cycle", "ann_return_pct", "ann_vol_pct", "sharpe", "max_dd_pct_capital"]]
    lt.columns = ["Structure", "Calendar", "Return %/yr", "Vol %/yr", "Sharpe", "Max DD % cap."]
    w(_md_table(lt, FMT) + "\n")
    w("Takeaways: the *level* of implied vol is the biggest unknown (±10% IV moves the naked put Sharpe from about 0.3 to 0.5 "
      "and flips the delta-hedged result's sign). The martingale's fate depends on the calendar and on small modelling "
      "choices; the fixed-size results do not.\n")

    w("## 8. Where we are now\n")
    w(f"As of {snap['as_of']}: NDX {snap['ndx']:,.0f}, VXN {snap['vxn']:.1f}, estimated ATM IV 1M {100 * snap['atm_iv_1m']:.1f}% / "
      f"3M {100 * snap['atm_iv_3m']:.1f}%.\n")
    qt = pd.DataFrame(snap["indicative_quotes"])
    qt = qt[["contract", "days", "futures", "atm_iv", "atm_put_pts", "atm_put_pct", "atm_put_usd_per_NQ",
             "otm10_put_pts", "spread10_credit_pts"]]
    qt.columns = ["Contract (indicative, model)", "Days", "NQ fut.", "ATM IV", "ATM put pts", "% of notional",
                  "$ per NQ", "-10% put pts", "Spread -10% credit pts"]
    w(_md_table(qt, {"NQ fut.": lambda v: f"{v:,.0f}", "ATM IV": lambda v: f"{100 * v:.1f}%",
                     "ATM put pts": lambda v: f"{v:,.0f}", "% of notional": lambda v: f"{100 * v:.2f}%",
                     "$ per NQ": lambda v: f"${v:,.0f}", "-10% put pts": lambda v: f"{v:,.0f}",
                     "Spread -10% credit pts": lambda v: f"{v:,.0f}", "Days": lambda v: f"{int(v)}"}) + "\n")
    if op:
        w(f"Open backtest position: sold {op['entry']}, strike {op['strike']:,.0f}, expiry {op['expiry']}. It is ITM by "
          f"{op['intrinsic_pts']:,.0f} pts, with model value {op['put_value_now_pts']:,.0f} pts vs {op['premium_pts']:,.0f} collected.\n")
    w("Check these against live quotes before trading. The model ignores the current skew and term structure of NQ "
      "options specifically.\n")

    L.extend(_campaign_section(camp))
    L.extend(_variant_section(camp["variants"]))
    L.extend(_h5_section(camp["h5"]))
    w("## 10. Limitations\n")
    w("* Premiums are reconstructed from VXN/VIX, not traded quotes. Error is probably ±10% of premium, and larger before 2001 "
      "(VXN proxy) and before 1990 (VXO-based). NQ options did not exist before ~1999-2000; earlier years are a "
      "hypothetical on the index.")
    w("* Settlement uses the expiry-day close. Real quarterly NQ options settle to the Friday-morning SOQ, and early "
      "exercise of American-style quarterlies is ignored.")
    w("* The skew is a fixed parametric shape. In real crashes the skew and the term structure move, which matters for "
      "spread marks and hedge ratios (but not for expiry payoffs).")
    w("* Returns are excess of cash: collateral would also earn T-bill interest (~3% avg). Taxes are ignored.")
    w("* Margin is approximate. SPAN margin can jump in a crash, and that is exactly when the martingale needs more of it.\n")
    w("## 11. Reproduce\n")
    w("```bash\npip install -r requirements.txt\npython run_backtest.py --refresh   # downloads data, ~30 s\n```\n")
    w("Outputs: `results/*.csv` (grid of 200+ strategy variants, premium history, sensitivities), "
      "`reports/figures/*.png`, and this report.\n")
    return "\n".join(L)
