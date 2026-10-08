"""Long-term statistics (multi-year, from actual prices and reported results).
No projections: these describe what the stock has done and what it reports."""
from __future__ import annotations

import math
from datetime import date

from stockbot.storage.db import DB

YEAR = 250


def _cagr(first: float, last: float, years: float) -> float | None:
    if first <= 0 or last <= 0 or years <= 0:
        return None
    return ((last / first) ** (1.0 / years) - 1.0) * 100.0


def price_stats(db: DB, symbol: str, as_of: str) -> dict:
    rows = db.history(symbol, as_of, 10_000)
    closes = [float(r["close"]) for r in rows if r["close"] and r["close"] > 0]
    dates = [r["date"] for r in rows if r["close"] and r["close"] > 0]
    out: dict = {"sessions": len(closes), "first_date": dates[0] if dates else None}
    if len(closes) < 30:
        return out
    last = closes[-1]
    for label, n in (("1y", YEAR), ("3y", 3 * YEAR), ("5y", 5 * YEAR)):
        if len(closes) > n:
            out[f"return_{label}_pct"] = (last / closes[-n - 1] - 1.0) * 100.0
            out[f"cagr_{label}_pct"] = _cagr(closes[-n - 1], last, n / YEAR)
        else:
            out[f"return_{label}_pct"] = None
            out[f"cagr_{label}_pct"] = None
    # since first available session
    yrs = (date.fromisoformat(dates[-1]) - date.fromisoformat(dates[0])).days / 365.25
    out["cagr_since_start_pct"] = _cagr(closes[0], last, yrs) if yrs >= 0.5 else None
    out["years_of_data"] = round(yrs, 1)
    # volatility (annualised, from daily log returns, last 1y) and max drawdown (last 3y)
    window = closes[-YEAR - 1:]
    lr = [math.log(b / a) for a, b in zip(window[:-1], window[1:]) if a > 0 and b > 0 and abs(b / a - 1) < 0.5]
    if len(lr) > 20:
        mean = sum(lr) / len(lr)
        sd = math.sqrt(sum((x - mean) ** 2 for x in lr) / (len(lr) - 1))
        out["volatility_1y_pct"] = sd * math.sqrt(YEAR) * 100.0
    w3 = closes[-3 * YEAR:]
    peak, mdd, trough_date, peak_date, cur_peak_date = w3[0], 0.0, None, None, dates[-len(w3)]
    for d, c in zip(dates[-len(w3):], w3):
        if c > peak:
            peak, cur_peak_date = c, d
        dd = (c / peak - 1.0) * 100.0
        if dd < mdd:
            mdd, trough_date, peak_date = dd, d, cur_peak_date
    out["max_drawdown_3y_pct"] = mdd
    out["max_drawdown_from"] = peak_date
    out["max_drawdown_to"] = trough_date
    out["drawdown_from_3y_high_pct"] = (last / max(w3) - 1.0) * 100.0
    # share of positive rolling 1-month and 1-year windows
    for label, n in (("month", 21), ("year", YEAR)):
        wins = [(closes[i + n] / closes[i] - 1.0) for i in range(0, len(closes) - n)]
        out[f"positive_{label}_windows_pct"] = (100.0 * sum(1 for w in wins if w > 0) / len(wins)) if wins else None
    return out


def fundamentals_view(company: dict | None, close: float | None) -> dict:
    """Reported numbers from the PSX company page, lightly derived."""
    if not company:
        return {"available": False}
    ann = company.get("annual") or {}
    years = ann.get("years") or []
    eps = ann.get("EPS") or []
    pat = ann.get("Profit after Taxation") or []
    sales = ann.get("Sales") or []
    out = {
        "available": True,
        "fiscal_year_end": company.get("fiscal_year_end"),
        "pe_ttm": company.get("pe_ttm"),
        "change_1y_pct": company.get("change_1y_pct"),
        "change_ytd_pct": company.get("change_ytd_pct"),
        "market_cap_bn": (company.get("market_cap_000") or 0) / 1e6 if company.get("market_cap_000") else None,  # 000's -> billions
        "free_float_pct": company.get("free_float_pct"),
        "years": years, "eps": eps, "profit_after_tax_000": pat, "sales_000": sales,
        "ratios": company.get("ratios") or {},
        "quarterly": company.get("quarterly") or {},
        "eps_latest": eps[0] if eps else None,
    }
    if eps and close and eps[0] and eps[0] > 0:
        out["pe_on_latest_annual_eps"] = close / eps[0]
    if len(eps) >= 2 and eps[-1] and eps[-1] > 0 and eps[0] and eps[0] > 0:
        out["eps_cagr_pct"] = _cagr(eps[-1], eps[0], len(eps) - 1)
    if eps:
        out["profitable_years"] = sum(1 for e in eps if e and e > 0)
        out["loss_years"] = sum(1 for e in eps if e is not None and e <= 0)
    return out


def sentences(symbol: str, ps: dict, fv: dict, corp: dict) -> list[str]:
    out = []
    if ps.get("cagr_3y_pct") is not None:
        out.append(f"Over the last 3 years the price compounded at {ps['cagr_3y_pct']:+.1f}% a year; over 1 year {ps['return_1y_pct']:+.1f}%.")
    elif ps.get("cagr_since_start_pct") is not None:
        out.append(f"Price history covers {ps['years_of_data']} years; it compounded at {ps['cagr_since_start_pct']:+.1f}% a year over that period.")
    if ps.get("max_drawdown_3y_pct") is not None:
        out.append(f"The deepest fall in the last 3 years was {ps['max_drawdown_3y_pct']:.0f}% ({ps['max_drawdown_from']} to {ps['max_drawdown_to']}); it is now {ps['drawdown_from_3y_high_pct']:.0f}% from its 3-year high.")
    if ps.get("volatility_1y_pct") is not None:
        v = ps["volatility_1y_pct"]
        band = "low" if v < 20 else "moderate" if v < 35 else "high" if v < 55 else "very high"
        out.append(f"Annualised volatility over the last year is {v:.0f}% ({band} for PSX).")
    if ps.get("positive_year_windows_pct") is not None:
        out.append(f"Historically, {ps['positive_year_windows_pct']:.0f}% of 1-year holding windows and {ps['positive_month_windows_pct']:.0f}% of 1-month windows ended higher.")
    if fv.get("available"):
        if fv.get("eps"):
            yrs, eps = fv["years"], fv["eps"]
            out.append("Reported EPS by fiscal year: " + ", ".join(f"{y} {e:.2f}" for y, e in zip(yrs, eps) if e is not None) + ".")
        if fv.get("eps_cagr_pct") is not None:
            out.append(f"EPS compounded at {fv['eps_cagr_pct']:+.1f}% a year across the reported years; {fv['profitable_years']} of {len(fv['eps'])} years profitable.")
        if fv.get("pe_ttm"):
            out.append(f"Trailing P/E is {fv['pe_ttm']:.1f} (PSX portal).")
    if corp.get("last_ex_dividend"):
        out.append(f"Last went ex-dividend on {corp['last_ex_dividend']}; {corp['ex_dividends_last_12m']} ex-dividend dates in the last 12 months and {corp['ex_dividends_last_3y']} in 3 years. Dividend amounts are not available from the PSX portal feed.")
    else:
        out.append("No ex-dividend date found in the price history since 2020.")
    return out
