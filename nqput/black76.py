"""Black-76 pricing for (European) options on futures - NQ options exercise into NQ futures."""
from __future__ import annotations

import numpy as np
from scipy.special import ndtr


def _prep(F, K, T, r, sigma):
    arrs = np.broadcast_arrays(*(np.atleast_1d(np.asarray(x, dtype=float)) for x in (F, K, T, r, sigma)))
    scalar = all(np.ndim(x) == 0 for x in (F, K, T, r, sigma))
    return [a.copy() for a in arrs], scalar


def put_price(F, K, T, r, sigma):
    (F, K, T, r, sigma), scalar = _prep(F, K, T, r, sigma)
    out = np.maximum(K - F, 0.0)
    live = T > 1e-10
    if live.any():
        Fl, Kl, Tl, sl = F[live], K[live], T[live], sigma[live]
        sq = sl * np.sqrt(Tl)
        d1 = (np.log(Fl / Kl) + 0.5 * sq ** 2) / sq
        d2 = d1 - sq
        out[live] = np.exp(-r[live] * Tl) * (Kl * ndtr(-d2) - Fl * ndtr(-d1))
    return float(out[0]) if scalar else out


def put_delta(F, K, T, r, sigma):
    """dV/dF of a put (negative); at expiry -1 if ITM else 0."""
    (F, K, T, r, sigma), scalar = _prep(F, K, T, r, sigma)
    out = np.where(F < K, -1.0, 0.0)
    live = T > 1e-10
    if live.any():
        Fl, Kl, Tl, sl = F[live], K[live], T[live], sigma[live]
        sq = sl * np.sqrt(Tl)
        d1 = (np.log(Fl / Kl) + 0.5 * sq ** 2) / sq
        out[live] = -np.exp(-r[live] * Tl) * ndtr(-d1)
    return float(out[0]) if scalar else out


def call_price(F, K, T, r, sigma):
    (F, K, T, r, sigma), scalar = _prep(F, K, T, r, sigma)
    out = np.maximum(F - K, 0.0)
    live = T > 1e-10
    if live.any():
        Fl, Kl, Tl, sl = F[live], K[live], T[live], sigma[live]
        sq = sl * np.sqrt(Tl)
        d1 = (np.log(Fl / Kl) + 0.5 * sq ** 2) / sq
        out[live] = np.exp(-r[live] * Tl) * (Fl * ndtr(d1) - Kl * ndtr(d1 - sq))
    return float(out[0]) if scalar else out


def call_delta(F, K, T, r, sigma):
    """dV/dF of a call (positive); at expiry 1 if ITM else 0."""
    (F, K, T, r, sigma), scalar = _prep(F, K, T, r, sigma)
    out = np.where(F > K, 1.0, 0.0)
    live = T > 1e-10
    if live.any():
        Fl, Kl, Tl, sl = F[live], K[live], T[live], sigma[live]
        sq = sl * np.sqrt(Tl)
        d1 = (np.log(Fl / Kl) + 0.5 * sq ** 2) / sq
        out[live] = np.exp(-r[live] * Tl) * ndtr(d1)
    return float(out[0]) if scalar else out
