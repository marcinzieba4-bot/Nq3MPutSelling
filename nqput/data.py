"""Download, cache and merge the free public data the backtest needs.

Sources (all daily closes):
  * NASDAQ-100 index (NDX) ............ FRED `NASDAQ100` (primary), Yahoo `^NDX` (gap fill, pre-1986)
  * S&P 500 (SPX) ...................... Yahoo `^GSPC` (only used for the pre-2001 VXN proxy)
  * VXN (Cboe Nasdaq-100 vol index) .... FRED `VXNCLS`, Cboe, Yahoo `^VXN` (from 2001)
  * VIX / VXO .......................... FRED `VIXCLS` (from 1990), `VXOCLS` (1986-2021)
  * VIX3M (3-month VIX) ................ FRED `VXVCLS`, Yahoo `^VIX3M` (from 2006)
  * 3-month T-bill ..................... FRED `DTB3`
  * VOLQ (Nasdaq-100 ATM vol index) .... Nasdaq API (2019-2023, used to calibrate ATM IV vs VXN)
"""
from __future__ import annotations

import io
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

# FRED stalls browser-like user agents; Yahoo/Cboe/Nasdaq want one.
BROWSER_HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json,text/csv,*/*"}

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1=0&period2={end}&interval=1d"
CBOE_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/{sym}_History.csv"
VOLQ_URL = ("https://api.nasdaq.com/api/quote/VOLQ/historical?assetclass=index"
            "&fromdate=2015-01-01&todate={today}&limit=9999")

# name -> (provider, symbol)
SOURCES: dict[str, tuple[str, str]] = {
    "ndx_fred": ("fred", "NASDAQ100"),
    "vxn_fred": ("fred", "VXNCLS"),
    "vix_fred": ("fred", "VIXCLS"),
    "vxo_fred": ("fred", "VXOCLS"),
    "vix3m_fred": ("fred", "VXVCLS"),
    "tbill3m_fred": ("fred", "DTB3"),
    "ndx_yahoo": ("yahoo", "^NDX"),
    "spx_yahoo": ("yahoo", "^GSPC"),
    "vxn_yahoo": ("yahoo", "^VXN"),
    "vix3m_yahoo": ("yahoo", "^VIX3M"),
    "vxn_cboe": ("cboe", "VXN"),
    "vix_cboe": ("cboe", "VIX"),
    "volq_nasdaq": ("nasdaq", "VOLQ"),
}


def _get(url: str, tries: int = 4, browser: bool = True) -> requests.Response:
    last: Exception | None = None
    for i in range(tries):
        try:
            r = requests.get(url, headers=BROWSER_HEADERS if browser else None, timeout=30)
            r.raise_for_status()
            return r
        except Exception as exc:  # network hiccups -> exponential backoff
            last = exc
            time.sleep(2 ** (i + 1))
    raise RuntimeError(f"download failed: {url}: {last}")


def _fetch(provider: str, sym: str) -> pd.Series:
    if provider == "fred":
        df = pd.read_csv(io.StringIO(_get(FRED_URL.format(sid=sym), browser=False).text))
        s = pd.Series(pd.to_numeric(df.iloc[:, 1], errors="coerce").values,
                      index=pd.to_datetime(df.iloc[:, 0]))
    elif provider == "yahoo":
        end = int(time.time()) + 86400
        res = _get(YAHOO_URL.format(sym=requests.utils.quote(sym), end=end)).json()["chart"]["result"][0]
        idx = pd.to_datetime(res["timestamp"], unit="s").normalize()
        s = pd.Series(res["indicators"]["quote"][0]["close"], index=idx, dtype=float)
    elif provider == "cboe":
        df = pd.read_csv(io.StringIO(_get(CBOE_URL.format(sym=sym)).text))
        s = pd.Series(pd.to_numeric(df["CLOSE"], errors="coerce").values,
                      index=pd.to_datetime(df["DATE"], format="%m/%d/%Y"))
    elif provider == "nasdaq":
        today = pd.Timestamp.today().strftime("%Y-%m-%d")
        rows = _get(VOLQ_URL.format(today=today)).json()["data"]["tradesTable"]["rows"]
        df = pd.DataFrame(rows)
        s = pd.Series(pd.to_numeric(df["close"].str.replace(",", ""), errors="coerce").values,
                      index=pd.to_datetime(df["date"], format="%m/%d/%Y"))
    else:
        raise ValueError(provider)
    s = s.dropna()
    s = s[~s.index.duplicated(keep="last")].sort_index()
    s.index.name = "date"
    return s


def download_all(cache_dir: Path, refresh: bool = False, verbose: bool = True) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    for name, (prov, sym) in SOURCES.items():
        path = cache_dir / f"{name}.csv"
        if path.exists() and not refresh:
            continue
        try:
            s = _fetch(prov, sym)
            s.rename(name).to_csv(path)
            if verbose:
                print(f"  downloaded {name:<14} {len(s):>6} rows  {s.index[0].date()} .. {s.index[-1].date()}")
        except Exception as exc:  # optional sources may fail; required ones are checked in load
            print(f"  WARNING: {name}: {exc}")


def _read(cache_dir: Path, name: str) -> pd.Series:
    path = cache_dir / f"{name}.csv"
    if not path.exists():
        return pd.Series(dtype=float)
    s = pd.read_csv(path, index_col=0, parse_dates=True).iloc[:, 0]
    return pd.to_numeric(s, errors="coerce").dropna()


def _stale_tail_cut(s: pd.Series, min_run: int = 10) -> pd.Series:
    """Drop a frozen tail (VOLQ stopped updating in Oct-2023 and repeats one value)."""
    if len(s) < min_run:
        return s
    same = (s.diff() == 0).to_numpy()
    n = 0
    for v in same[::-1]:
        if not v:
            break
        n += 1
    return s.iloc[: len(s) - n - 1] if n >= min_run else s


def load_market_data(cache_dir: Path) -> pd.DataFrame:
    """Merge all sources onto the NDX trading calendar.

    Columns: ndx, spx, vxn, vix, vxo, vix3m, rf (decimal), volq.
    """
    ndx = _read(cache_dir, "ndx_fred").combine_first(_read(cache_dir, "ndx_yahoo"))
    if ndx.empty:
        raise RuntimeError("NDX data missing - run with --refresh")
    vxn = _read(cache_dir, "vxn_fred").combine_first(_read(cache_dir, "vxn_cboe")).combine_first(
        _read(cache_dir, "vxn_yahoo"))
    vix3m = _read(cache_dir, "vix3m_fred").combine_first(_read(cache_dir, "vix3m_yahoo"))
    volq = _stale_tail_cut(_read(cache_dir, "volq_nasdaq"))

    df = pd.DataFrame(index=ndx.index)
    df["ndx"] = ndx
    for col, s in [("spx", _read(cache_dir, "spx_yahoo")), ("vxn", vxn),
                   ("vix", _read(cache_dir, "vix_fred").combine_first(_read(cache_dir, "vix_cboe"))),
                   ("vxo", _read(cache_dir, "vxo_fred")),
                   ("vix3m", vix3m), ("rf", _read(cache_dir, "tbill3m_fred") / 100.0), ("volq", volq)]:
        df[col] = s.reindex(df.index)
    # forward-fill small holes (holiday mismatches) but never across long gaps
    for col in ["spx", "vxn", "vix", "vxo", "vix3m", "rf"]:
        first = df[col].first_valid_index()
        last = df[col].last_valid_index()
        if first is not None:
            df.loc[first:last, col] = df.loc[first:last, col].ffill(limit=5)
    df["rf"] = df["rf"].ffill()
    df = df[df.index >= "1985-10-01"]
    df.index.name = "date"
    return df


def realized_vol(px: pd.Series, window: int) -> pd.Series:
    r = np.log(px).diff()
    return r.rolling(window, min_periods=int(window * 0.8)).std() * np.sqrt(252) * 100.0


if __name__ == "__main__":  # pragma: no cover
    import sys
    cache = Path(__file__).resolve().parents[1] / "data" / "raw"
    download_all(cache, refresh="--refresh" in sys.argv)
    d = load_market_data(cache)
    print(d.describe().T)
    print(json.dumps({c: str(d[c].first_valid_index()) for c in d.columns}, indent=1))
