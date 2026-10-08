# Data sources for Stock Guru - candidates to shortlist

Status on 8 Oct 2026. "In use" means the code already reads it. Everything
else is a suggestion for Homi to shortlist; each needs its terms of use
checked before automation (design doc section 7).

## Prices, volumes, corporate-action markers

| Source | What it gives | Access | Status |
|---|---|---|---|
| **PSX Data Portal - daily Market Summary file** (`dps.psx.com.pk/download/mkt_summary/<date>.Z`) | Official end-of-day OHLC, volume, previous close for every listed security; XD/XB/XR markers on ex-dates; archive back to 2020 | one small file per day, plain download | **In use** (prices, ex-dividend dates) |
| **PSX Data Portal - company page** (`dps.psx.com.pk/company/<SYM>`) | P/E (TTM), market cap, shares, free float, 1-year/YTD change, 4 years of sales / profit / EPS, quarterly EPS, margin and PEG ratios, announcements (results, board meetings, AGM notices with PDF links) | one page per stock, plain GET | **In use** (fundamentals, AGM, results) |
| PSX Data Portal - AGM notice PDFs (`/download/document/<id>.pdf`) | Actual meeting date and agenda | small PDF per notice; some are scanned images with no text | **In use** where text is extractable |
| PSX Data Portal - other daily downloads (`/downloads`) | Closing-rate PDF, index constituent list (`indhist` XLS), VAR margins, short-sell volume, daily announcements PDF, post-close report | plain download | available, not used yet |
| PSX portal JSON/AJAX endpoints (`/timeseries/...`, `/historical`, `/company/payouts`, `/calendar`) | intraday & historical series, dividend/payout history, AGM calendar | **blocked** (403/404) outside the portal's own browser session | not usable |
| PSX Data Services (licensed vending) | real-time and full historical feeds under licence | paid licence from PSX | the official route if terms become a problem |

## Dividends and payouts (amounts)

Filled on 8 Oct 2026 by the ksestocks Book Closures page (see review below). The PSX daily file still
supplies the historical ex-dividend dates. Other candidates, kept for reference:

| Source | Notes |
|---|---|
| **Result announcement PDFs on the PSX portal** | The declared dividend ("final cash dividend Rs X per share / X%") is in the results announcement already linked from the company page. Parsing is feasible with the same PDF text extraction used for AGM dates. First thing to try, stays within PSX. |
| Sarmaaya.pk | Free fundamentals and payout history per company, widely used by retail investors in Pakistan. Check terms; probably manual-copy only. |
| SCSTrade.com | Historical prices, book closures, payout history; free registration. Check terms. |
| KSEStocks.com | Book closures, dividends, announcements. Check terms. |
| Investify.pk / Mettis Global (mg-link.net) | Aggregators with corporate-action data; Mettis is paid. |
| Company investor-relations pages / annual reports | Authoritative for dividend history; one-off manual check per stock. |

## Review of candidate sites (checked from the NAS on 8 Oct 2026)

| Site | Verdict | What was found |
|---|---|---|
| **ksestocks.com** | **In use since 8 Oct 2026** for declared dividends, bonus/right percentages and book-closure dates (`sources/ksestocks.py`, `payouts` table) | `BookClosures` page embeds a JSON list (symbol, face value, book-closure from/to, payout as "Dividend=60%", "Bonus=20%", "Right=..%", last close) for current and recent closures, so the last declared dividend per share = pct x face value / 100. Also announcements, dividend schedule, daily quotation files back to 2015, historic highs/lows. `robots.txt` allows everything; the disclaimer has no restriction on copying or automated use and warns only that accuracy is not guaranteed. Data source is not stated (mirrors PSX notices). One plain GET per day is enough. |
| **scstrade.com** (Standard Capital Securities) | Usable as a cross-check, second choice | Company snapshot pages (P/E, EPS, book value, ROE etc.), historical prices (ASP.NET form with VIEWSTATE, needs a POST per query), payout guides, a 5-page "PSX Company Dividend Schedule" PDF of credited dividends, top dividend-yield lists. No robots.txt, no usage terms beyond a privacy policy and "all rights reserved"; the "Online Trading Terms" cover the brokerage service, not the data pages. Nothing here that PSX + ksestocks do not already give, and it is a brokerage site, so keep it as a cross-check only. |
| **akdtrade.com** (AKD Trade) | Not a data source | It is the AKD brokerage's trading platform (login only). From the NAS the HTTPS handshake does not complete. AKD publishes no public data API; the design doc's open question "ask AKD for a feed" still stands. |
| **investing.com** | Not usable | Blocks non-browser clients outright (HTTP 403 even for `robots.txt`); its terms (which could not be fetched from here for the same reason) are known to prohibit automated access and redistribution; PSX coverage of small caps is delayed and partial. Would need a browser-automation workaround that their terms forbid. Skip. |
| "sctrade" | Assumed to be scstrade.com (above). No site of that name found. |

Licensed alternatives if a formal feed is ever wanted: PSX Data Services vending (official end-of-day and historical products, paid) and CapitalStake (REST API with EOD/intraday prices, dividends, fundamentals, announcements; pricing not published).

## Macro and global factors (design 4.1-4.2; not built yet)

| Source | What |
|---|---|
| State Bank of Pakistan (sbp.org.pk) | policy rate, forex reserves, PKR/USD reference rate, T-bill/PIB auction results |
| Pakistan Bureau of Statistics (pbs.gov.pk) | monthly CPI |
| NCCPL (nccpl.com.pk) | daily foreign and local portfolio investment flows (FIPI/LIPI) |
| PSX index constituent file (`indhist` XLS, daily download) | KSE-100 membership for the liquid-stock screener |
| Brent, coal, gold, cotton, steel, US dollar index, US 10-year | any free daily commodities/FX feed (e.g. stooq.com CSV, FRED for US rates); cross-check against a second source |

## News (facts-only ingestion, design 4.1 tier 3; not built yet)

Business Recorder, Dawn Business, The Express Tribune business, Profit by Pakistan Today, PSX daily announcements PDF. Analyst/brokerage opinion stays excluded from the analysis by design.

## Not used, by design

YouTube analysts (V1 scope excludes the digest), brokerage research notes, social media.
