"""Approximate Nasdaq-100 option implied-vol surface from free index data.

There is no free history of NQ / NDX option quotes, so premiums are *estimated*:

1. 30-day vol level = VXN (Cboe Nasdaq-100 vol index, actual from Feb-2001).
   Before 2001 VXN is reconstructed by regression on VIX (VXO before 1990) and the
   ratio of NDX / SPX realized vol (fit on 2001-2026, R^2 ~ 0.97).
2. VXN is a variance-swap style index (includes skew), so it sits above ATM vol.
   ATM 30d vol = a + b * VXN, calibrated on Nasdaq's VOLQ index (an ATM NDX vol
   index, valid data Oct-2019 .. Sep-2023): ATM ~ 0.98 * VXN - 2.3 vol pts
   (on average ATM ~ 0.89 x VXN).
3. 3-month ATM vol = ATM 30d vol x (VIX3M / VIX) term-structure ratio
   (proxy regression on VIX level/trend before 2006).
4. Put skew: sigma(K) = sigma_ATM + alpha / sqrt(T) * ln(F/K) for K < F
   (half the slope on the call side). alpha = 0.22 gives ~ +4.6 vol pts at a
   10%-OTM 3-month strike and a 25-delta risk reversal of ~ -4.5 vols, in line
   with typical NDX skew.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .data import realized_vol

T1M_DAYS = 30.0
T3M_DAYS = 93.0  # VIX3M horizon


@dataclass
class VolParams:
    iv_scale: float = 1.0          # multiply the whole surface (sensitivity: 0.9 / 1.1)
    skew_alpha: float = 0.22       # put-wing slope = alpha / sqrt(T) per unit ln(F/K)
    call_wing: float = 0.5         # call-side slope as a fraction of the put-side slope
    min_tau_skew_days: float = 7.0
    vol_floor: float = 0.05
    # ATM(30d) = atm_a + atm_b * VXN (vol points); refit from VOLQ when available
    atm_a: float = -2.30
    atm_b: float = 0.982


def _ols(y: pd.Series, X: pd.DataFrame) -> tuple[np.ndarray, float, float]:
    A = np.column_stack([np.ones(len(X))] + [X[c].to_numpy() for c in X.columns])
    b, *_ = np.linalg.lstsq(A, y.to_numpy(), rcond=None)
    pred = A @ b
    resid = y.to_numpy() - pred
    r2 = 1 - (resid ** 2).sum() / ((y - y.mean()) ** 2).sum()
    return b, float(r2), float(resid.std())


def build_vol_inputs(df: pd.DataFrame, params: VolParams | None = None,
                     refit_atm: bool = True) -> tuple[pd.DataFrame, dict]:
    """Return daily frame with ATM 1M / 3M implied vols (decimals) and fit diagnostics."""
    params = params or VolParams()
    out = pd.DataFrame(index=df.index)
    diag: dict = {}

    # --- 1) VIX history incl. VXO-based back-fill (pre-1990) -----------------
    ov = df[["vix", "vxo"]].dropna()
    b, r2, sd = _ols(np.log(ov.vix), np.log(ov[["vxo"]]))
    diag["vix_from_vxo"] = {"coef": b.round(4).tolist(), "r2": round(r2, 3), "resid_sd": round(sd, 3)}
    vix = df.vix.copy()
    fill = vix.isna() & df.vxo.notna() & (df.index < "1990-01-02")
    vix[fill] = np.exp(b[0] + b[1] * np.log(df.vxo[fill]))
    out["vix_full"] = vix

    # --- 2) VXN back-fill from VIX and relative NDX/SPX realized vol ----------
    rvr21 = np.log(realized_vol(df.ndx, 21) / realized_vol(df.spx, 21))
    rvr63 = np.log(realized_vol(df.ndx, 63) / realized_vol(df.spx, 63))
    X = pd.DataFrame({"lvix": np.log(vix), "rvr21": rvr21, "rvr63": rvr63})
    fit = pd.concat([np.log(df.vxn).rename("y"), X], axis=1).dropna()
    b, r2, sd = _ols(fit.y, fit[["lvix", "rvr21", "rvr63"]])
    diag["vxn_proxy"] = {"coef": b.round(4).tolist(), "r2": round(r2, 3), "resid_sd": round(sd, 3),
                         "fit_from": str(fit.index[0].date())}
    vxn_hat = np.exp(b[0] + b[1] * X.lvix + b[2] * X.rvr21 + b[3] * X.rvr63)
    out["vxn_full"] = df.vxn.combine_first(vxn_hat.where(df.index < df.vxn.first_valid_index()))
    out["vxn_src"] = np.where(df.vxn.notna(), "VXN actual", "VXN proxy")

    # --- 3) Term-structure ratio VIX3M / VIX ---------------------------------
    vix_ma = vix.rolling(252, min_periods=20).mean()
    T = pd.DataFrame({"lvix": np.log(vix), "trend": np.log(vix / vix_ma)})
    fit = pd.concat([np.log(df.vix3m / df.vix).rename("y"), T], axis=1).dropna()
    b, r2, sd = _ols(fit.y, fit[["lvix", "trend"]])
    diag["term_structure_proxy"] = {"coef": b.round(4).tolist(), "r2": round(r2, 3), "resid_sd": round(sd, 3)}
    ts_hat = np.exp(b[0] + b[1] * T.lvix + b[2] * T.trend)
    out["ts_ratio"] = (df.vix3m / df.vix).combine_first(ts_hat)

    # --- 4) ATM 30d vol vs VXN, calibrated on VOLQ --------------------------
    if refit_atm:
        cal = df[["volq", "vxn"]].dropna()
        if len(cal) > 250:
            bb = np.polyfit(cal.vxn, cal.volq, 1)
            params.atm_b, params.atm_a = float(bb[0]), float(bb[1])
            diag["atm_vs_vxn"] = {"b": round(params.atm_b, 4), "a": round(params.atm_a, 3), "n": len(cal),
                                  "mean_ratio": round(float((cal.volq / cal.vxn).mean()), 3),
                                  "window": f"{cal.index[0].date()}..{cal.index[-1].date()}"}
    atm1m = (params.atm_a + params.atm_b * out.vxn_full) / 100.0
    out["atm1m"] = atm1m.clip(lower=params.vol_floor)
    out["atm3m"] = (out.atm1m * out.ts_ratio).clip(lower=params.vol_floor)
    out[["atm1m", "atm3m", "ts_ratio"]] = out[["atm1m", "atm3m", "ts_ratio"]].ffill(limit=5)
    return out, diag


def atm_vol_for_tau(atm1m: np.ndarray, atm3m: np.ndarray, tau_days: np.ndarray) -> np.ndarray:
    """ATM vol for any maturity: linear interpolation in total variance between 30d and 93d."""
    t1, t3 = T1M_DAYS, T3M_DAYS
    w1 = atm1m ** 2 * t1
    w3 = atm3m ** 2 * t3
    tau = np.asarray(tau_days, dtype=float)
    w = w1 + (w3 - w1) * (tau - t1) / (t3 - t1)
    with np.errstate(invalid="ignore", divide="ignore"):
        mid = np.sqrt(np.maximum(w, 1e-12) / np.maximum(tau, 1e-9))
    return np.where(tau <= t1, atm1m, np.where(tau >= t3, atm3m, mid))


def strike_vol(atm: np.ndarray, F: np.ndarray, K: np.ndarray | float, tau_years: np.ndarray,
               p: VolParams) -> np.ndarray:
    """Skewed implied vol for strike K (sticky-moneyness parametric skew)."""
    k = np.log(np.asarray(F, dtype=float) / K)  # >0 for OTM puts
    teff = np.maximum(tau_years, p.min_tau_skew_days / 365.0)
    slope = p.skew_alpha / np.sqrt(teff)
    vol = atm + slope * np.where(k > 0, k, p.call_wing * k)
    vol = np.maximum(vol, 0.6 * atm)
    return np.maximum(vol * p.iv_scale, p.vol_floor)
