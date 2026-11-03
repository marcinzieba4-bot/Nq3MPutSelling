"""Engine sanity tests on synthetic data (run: python -m pytest -q  or  python tests/test_engine.py)."""
import numpy as np
import pandas as pd

from nqput.backtest import Cycle, Hedge, MarketParams, Sizing, Structure, run_sizing, unit_cycle
from nqput.black76 import put_delta, put_price
from nqput.volmodel import VolParams


def _synthetic_cycle(seed: int, rv: float, iv: float, n: int = 64) -> Cycle:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-03", periods=n)
    tau = (dates[-1] - dates).days.to_numpy() / 365.0
    dt = np.diff((dates - dates[0]).days.to_numpy()) / 365.0
    z = rng.standard_normal(n - 1)
    logS = np.concatenate([[0.0], np.cumsum(-0.5 * rv ** 2 * dt + rv * np.sqrt(dt) * z)])
    S = 100.0 * np.exp(logS)
    return Cycle(entry=dates[0], expiry=dates[-1], open=False, dates=dates, S=S, F=S.copy(), tau=tau,
                 r=np.zeros(n), atm=np.full(n, iv), src="synthetic")


def test_black76_delta_matches_finite_difference():
    F, K, T, r, s = 100.0, 95.0, 0.25, 0.03, 0.22
    fd = (put_price(F + 1e-3, K, T, r, s) - put_price(F - 1e-3, K, T, r, s)) / 2e-3
    assert abs(put_delta(F, K, T, r, s) - fd) < 1e-6


def test_unhedged_pnl_is_premium_minus_payoff():
    mp = MarketParams(opt_slip_vol=0.0, opt_comm_pts=0.0, fut_cost_bp=0.0)
    vp = VolParams(skew_alpha=0.0)
    c = _synthetic_cycle(1, 0.2, 0.2)
    u = unit_cycle(c, Structure("naked"), Hedge(), mp, vp)
    prem = put_price(c.F[0], c.F[0], c.tau[0], 0.0, 0.2)
    payoff = max(c.F[0] - c.S[-1], 0.0)
    assert abs(u.ret.sum() * c.F0 - (prem - payoff)) < 1e-9


def test_delta_hedged_pnl_tracks_vol_premium():
    """With daily hedging, P&L ~ 0 when IV == RV and ~ vega*(IV-RV) when IV > RV."""
    mp = MarketParams(opt_slip_vol=0.0, opt_comm_pts=0.0, fut_cost_bp=0.0)
    vp = VolParams(skew_alpha=0.0)
    fair, rich = [], []
    for seed in range(400):
        c = _synthetic_cycle(seed, 0.20, 0.20)
        fair.append(unit_cycle(c, Structure("naked"), Hedge(mode="full"), mp, vp).ret.sum())
        c2 = _synthetic_cycle(seed, 0.20, 0.23)
        rich.append(unit_cycle(c2, Structure("naked"), Hedge(mode="full"), mp, vp).ret.sum())
    vega = 0.4 * np.sqrt(c.tau[0])  # ATM vega per unit notional (approx)
    assert abs(np.mean(fair)) < 0.0015
    assert abs(np.mean(rich) - vega * 0.03) < 0.003
    # hedging slashes the dispersion versus an unhedged short put
    unh = [unit_cycle(_synthetic_cycle(s, 0.2, 0.2), Structure("naked"), Hedge(), mp, vp).ret.sum()
           for s in range(400)]
    assert np.std(fair) < 0.35 * np.std(unh)


def test_recovery_sizing_targets_deficit():
    mp = MarketParams(opt_slip_vol=0.0, opt_comm_pts=0.0, fut_cost_bp=0.0)
    vp = VolParams(skew_alpha=0.0)
    units = [unit_cycle(_synthetic_cycle(s, 0.25, 0.2), Structure("naked"), Hedge(), mp, vp) for s in range(30)]
    res = run_sizing(units, Sizing("recover", "recover"), mp)
    cyc = res.cycles
    for i in range(1, len(cyc)):
        expected = 1 + cyc.deficit_before.iloc[i] / (mp.base_notional * units[i].premium_frac)
        assert abs(cyc.mult_wanted.iloc[i] - expected) < 1e-9


def test_drawdown_limit_caps_size():
    """With dd_limit, a stress loss at the chosen size never exceeds the remaining drawdown budget."""
    from nqput.backtest import stress_loss_frac
    mp = MarketParams(opt_slip_vol=0.0, opt_comm_pts=0.0, fut_cost_bp=0.0)
    vp = VolParams(skew_alpha=0.0)
    units = [unit_cycle(_synthetic_cycle(s, 0.35, 0.2), Structure("naked"), Hedge(), mp, vp) for s in range(40)]
    sz = Sizing("recover, 50% limit", "recover", dd_limit=0.5, dd_stress=0.45)
    res = run_sizing(units, sz, mp)
    hwm, E = mp.capital, mp.capital
    for i, row in res.cycles.iterrows():
        budget = E - 0.5 * hwm
        worst = row.mult * mp.base_notional * stress_loss_frac(units[i], 0.45)
        assert worst <= budget + 1e-6
        E = row.equity
        hwm = max(hwm, E)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
