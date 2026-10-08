# Stock Guru — PSX Decision-Support Agent — Consolidated Design Document

**Name:** Stock Guru *(chosen; a naming/branding choice — not a change to the
agent's required neutral, hedged, advisory tone in §4.3)*

**Last updated:** 2026-10-02 (see §10 change log)

**Status:** A working record of everything discussed so far. Items are marked
as **Decided** (explicitly confirmed by Homi), *working direction* (discussed,
no objections, not formally agreed) or *open question* (undecided). No code
is written until the relevant items are Decided.

---

## 1. Purpose

A self-hosted, personal-use-only system that watches a chosen list of PSX
stocks, gathers facts (prices, statistics, news, macro and global market
indicators) from reliable sources, and produces written analysis with
reasoning — **analytical help for making decisions, never the decision
itself, and never an executed trade.** Homi always makes the final call and
executes it manually in AKDTrade. Hobby/research project, built for one
user, reviewed and refined over months before anything runs unattended.

**Main needs it addresses:**
1. Cut the time spent reading charts — the system reads them and explains
   them in plain language.
2. A weekly look ahead for PSX, informed by local and international
   financial and commodity trends.
3. A short list of the most interesting setups to study each week.
4. A separate nightly digest of favourite YouTube analysts, for review only
   (§4.6).

---

## 2. Guiding principles

- **Simplicity over sophistication.** Prefer transparent statistics over
  black-box models. Add complexity only after a simpler version has proven
  itself.
- **Human-in-the-loop, always.** No layer of this system is ever allowed to
  submit an order. Fixed boundary.
- **Analysis, not decisions.** Outputs describe evidence, probabilities from
  history, and conditions — never "buy/sell" instructions. **Decided.**
- **Facts, not opinions — in the analysis.** The analysis engine uses only
  reported facts (prices, volumes, earnings, corporate actions, macro
  releases) and discards personal calls or predictions from any source.
  Analyst opinion is handled only in the separate Analyst Digest (§4.6) and
  never feeds the analysis. **Decided.**
- **No price forecasts.** No predicted prices or targets. Replaced by
  historical base-rate statistics, an events calendar and conditional
  scenarios (§4.4). **Decided.**
- **Fail loud, fail safe.** If data is missing, stale or looks wrong, the
  report says so rather than going out on bad data.
- **Verify before you trust.** Each layer is checked by hand against
  known-good data before the next layer is built on it.
- **Measure itself.** The system keeps score of its own past outputs (§4.5).
  **Decided.**

---

## 3. Architecture *(working direction)*

```
Data sources                         YouTube channels (5 analysts)
(PSX portal, news, macro, global)            |
        |                                    v
        v                           [ Analyst Digest ]  -- separate module,
[ Host: NAS — Debian, headless,       transcripts -> AI summary   no data flows
  systemd-scheduled ]                         |            into Stock Guru
   Data acquisition  -> fetch + validate      v
   Storage           -> local DB + backup   Nightly digest ~11:00 PM
   Statistics engine -> trend, momentum,
                        volatility, patterns
   Self-scoring log  -> tracks past outputs
   AI reasoning      -> plain-language analysis
   Reports           -> daily note + weekly outlook
        |
        v
You + AKDTrade (you decide, you execute)
```

**Host hardware (confirmed):**
- NAS running headless Debian
- CPU: Intel Xeon E3-1225 V2 (2012-generation)
- RAM: 16GB DDR3 ECC
- Storage: 256GB SSD (OS) + multiple SATA drives (data/backup)
- No GPU — AI reasoning uses an external API call (Google Gemini), not a
  local model.
  If speech-to-text is ever needed for the Analyst Digest (§4.6), the NAS
  is too slow; Hadi's PC (homidev) is the candidate machine for that step.

---

## 4. Scope

### 4.1 Data acquisition — sources *(working direction)*

| Tier | Examples | Status |
|---|---|---|
| 1 — Official/regulatory | PSX Data Portal (dps.psx.com.pk), PSX Data Services Vending (licensed real-time), SECP, State Bank of Pakistan | Primary source of truth for prices; **terms need checking before automating (§7)** |
| 2 — Data aggregators | Mettis Global, Investify | Possible cross-check/backup; need same fact/opinion filter |
| 3 — News wires | Business Recorder, Dawn Business, The Express Tribune, Profit by Pakistan Today | Facts-only ingestion |
| 4 — Brokerage/analyst commentary | Brokerage notes, PSX commentary sites, YouTube analysts | **Excluded from the analysis.** YouTube analysts appear only in the separate Analyst Digest (§4.6) |

- **AKDTrade:** as far as known, no public data feed. Data comes from PSX
  and public sources, not the trading account. *Open: ask AKD whether they
  offer one.*
- **Timing:** one run per day after market close, end-of-day data only. No
  live/intraday data. **Decided.**

**Local macro indicators:** SBP policy rate, CPI inflation, forex reserves,
T-bill/PIB yields, PKR/USD rate, foreign portfolio investment flows into PSX.

### 4.2 International financial & commodity factors **(Decided — starting set)**

The system does not claim "X moved, so PSX will move." It reports what moved
and which PSX sectors on the watchlist are exposed, using this map:

| Global factor | PSX sectors mainly affected |
|---|---|
| Brent crude oil | Oil & gas producers, refineries, oil marketing |
| Coal | Cement, power |
| Gold | Gold-linked / some mining |
| Cotton | Textiles |
| Steel / scrap | Steel |
| US dollar, US interest rates, emerging-market sentiment | Foreign flows into PSX overall |
| PKR/USD | Exporters vs. importers |

The map can be extended later; each addition is a design change, not a
silent addition.

### 4.3 Analysis capabilities

- **Daily watchlist analysis** — indicators and plain-language explanation
  for each stock on the user's list.
- **Candlestick pattern detection** — pure OHLC math, no image recognition.
- **Annotated chart images** — charts with detected patterns/levels marked
  and one plain-language line each; also serves as a learning aid for
  reading charts. *Working direction.*
- **Portfolio-aware analysis** — holdings supplied by the user as a simple
  file.
- **Historical base-rate statistics** — "when this setup occurred
  historically, price rose over the next N sessions X% of the time; worst
  −Y%, best +Z%." **Decided** as the forecast substitute.

### 4.4 Weekly outlook **(Decided — format)**

Delivered once a week for the coming week. Contains:
1. **Events calendar** — SBP monetary policy, CPI release, IMF reviews,
   company results dates, other scheduled market-moving events.
2. **Global/commodity summary** — what moved, which sectors are exposed
   (§4.2).
3. **Base rates** for current setups (§4.3).
4. **Conditional scenarios** — "if the index holds above A, trend intact;
   a break below B invalidates it." No price targets.
5. **Top setups this week** — see below.

**Top setups this week — Decided:**
- Screened from **liquid stocks only (e.g. KSE-100)**, not all listings.
- **Up to 10** — never forced to 10; a quiet week may show fewer.
- Labelled "setups worth your attention", not "best stocks to buy".
- Each entry shows: why it qualified, score breakdown, base rate, and what
  would invalidate it.

### 4.5 Self-scoring log **(Decided — mandatory)**

- Every daily note and weekly setup list is logged.
- The following week, the system reports how those setups actually did.
- **Paper-trading period of 2–3 months** before any output is allowed to
  influence a real trade.

**Trial plan — Decided 2026-10-02:**
- Run the bot in parallel with Homi's own analysis for about **3 months**,
  on a shortlist of **10 blue-chip stocks across varied sectors**.
- Compare the bot's analysis and suggestions against Homi's own, and both
  against what actually happened.

*Working direction — making the comparison fair:*
- **Write your own view first**, before reading the bot's report for that
  day/week. Reading the bot first will pull your view toward it, and the
  comparison stops meaning anything.
- Keep one simple log: date, stock, your view, bot's view, what happened
  1 week later.
- 3 months gives roughly 12 weekly outlooks — enough to spot clear
  problems, not enough to prove the bot is reliable. Treat the result as
  "promising / not promising", not as proof.

### 4.6 Analyst Digest (YouTube) — separate module

**Decided:**
- Summaries of 5 favourite YouTube analysts' talks/podcasts, **for review
  only.**
- **Never used as input** to Stock Guru's fact- and research-based
  analysis. Separate module; no data flows from it into the analysis.
- Delivered daily at **around 11:00 PM** (PKT).

*Working direction — format:*
- **Combined summary** of the day's talks, with **every point attributed to
  the analyst who said it** (prevents blending different views into a false
  consensus).
- Top section: agreement vs. disagreement (e.g. "3 of 5 bullish on cement;
  2 cautious on banks").
- Per analyst: stocks/sectors mentioned, their view (labelled as opinion),
  the reason given, any price levels mentioned, link to the video.
- If an analyst posted nothing new that day, say so.

**Channels (Decided — provided 2026-10-02), all in Urdu:**

| # | Channel | Type |
|---|---|---|
| 1 | Abdul Rehman Najam (ARN Financial Advisors) | Advisory firm |
| 2 | Zafar Securities | Brokerage |
| 3 | InvestKaar (Furqan Punjani) | Independent analyst |
| 4 | Afaque Manzar (The Chart Alchemist) | Independent, technical/chart analysis |
| 5 | AKD Securities Limited | Brokerage (same group as AKDTrade) |

The digest shows each channel's type next to its points, since brokerage
channels may have commercial interests (trading activity, house positions).

*How it works — **Decided 2026-10-02** (Gemini primary, homidev fallback):*
1. Check each channel's public upload feed for new videos.
2. **Primary:** pass the public YouTube link directly to Google's Gemini
   API, which can watch/listen to public YouTube videos and summarize them
   (Urdu audio → English summary). No download and no caption scraping.
   Feature is in preview: free tier allows up to 8 hours of YouTube video
   per day; paid tier has no length limit; public videos only; terms and
   pricing may change.
3. **Fallback:** download audio and transcribe with an open speech-to-text
   model on homidev (not the NAS), then summarize.
4. Deliver at ~11:00 PM.

*Verification before relying on it:* run 2–3 real videos per channel,
watch them yourself, and compare against the summary — especially stock
names, numbers and price levels, which are where Urdu speech recognition
is most likely to slip.

*Known risks:*
- Urdu speech recognition quality is unproven for this content —
  biggest technical risk; settled by the verification step above.
- Gemini's YouTube feature is a preview — it could change or start
  costing money; the fallback path exists for that reason.
- Whole system depends on one AI provider (Google Gemini, Decided 9) —
  mitigated by keeping all AI calls in one swappable piece of code.
- Summaries lose nuance (conditions, qualifiers) — video link always kept.
- YouTube terms (§7).

*Later idea — not in scope:* log analysts' calls and score them over time
to see who is right more often.

### 4.7 Excluded

- Analyst/sentiment opinion as an input to the analysis, regardless of
  format.
- Price prediction or price targets.
- Live/intraday data.
- Full market-wide deep analysis — deep analysis stays on the watchlist;
  only the liquid-stock screener scans broadly.
- Any order placement.

---

## 5. Build phases *(working direction — order agreed in principle)*

| Phase | Adds |
|---|---|
| 1 | Watchlist, daily end-of-day data, 2–3 indicators, plain-language daily note |
| 2 | Candlestick patterns, annotated chart images, portfolio holdings input |
| 3 | Base-rate statistics + self-scoring log (paper-trading period starts) |
| 4 | Weekly outlook: events calendar, global/commodity-to-sector map, scenarios |
| 5 | KSE-100 screener → "Top setups this week" (up to 10) |
| Separate track | Analyst Digest (§4.6) — independent of phases 1–5 |

One piece at a time: build, verify against known-good data, then move on.

---

## 6. Dependencies & requirements on the NAS host

- **OS:** Debian, headless — confirm it is a supported stable release.
- **Runtime:** Python 3 (§8).
- **Storage:** SSD for OS + working DB; SATA for history archive and
  nightly backups; consider mirroring critical data across two drives.
- **Scheduling:** systemd timers (built-in logging, failure tracking).
  Daily run after market close; weekly outlook run; Analyst Digest at
  ~11:00 PM.
- **Networking:** outbound HTTPS only. Basic hardening: SSH key-only,
  firewall, no unnecessary open ports.
- **Secrets:** API keys in a restricted-permission config file or
  environment variables, never in the code.
- **Logging:** what was fetched, computed and returned each day (auditable).
- **Backups:** nightly copy of DB and logs to a separate drive.
- **Power:** small UPS for clean shutdowns.
- **Monitoring:** daily "did it run?" self-check with a separate alert.
- **Delivery channel:** email (PDF) for reports; *open: email vs. Telegram
  for the 11 PM digest.*

---

## 7. Legal / terms-of-use / compliance notes

- **PSX data:** portal states data is for "information and/or educational
  purposes only"; main site prohibits dissemination and commercial use of
  market data without a licence, broadly worded. Read PSX's full terms (or
  ask PSX) before automating regular pulls.
- **Other websites:** same check — "personal use" doesn't automatically
  make automated scraping permitted.
- **YouTube:** the primary method (Gemini reading a public YouTube link) is
  a Google-provided feature, so it avoids scraping. The fallback (audio
  download) is not officially permitted under YouTube's terms; at personal
  scale the practical risk is mainly that it breaks and needs fixing.
- **Employer insider-trading policy:** Fatima Fertilizer is listed on PSX.
  Check the company's insider-trading policy before including it or related
  stocks in the watchlist. Keep it off the watchlist until confirmed.

---

## 8. Decisions

- **Stack:** Python 3 backend. *(Proposed; not yet confirmed against prior
  stack experience from the club/hospital projects.)*
- **Frontend:** none in v1 — delivery is PDF + email. Lightweight dashboard
  possibly later.
- **PDF generation:** lean toward `fpdf2`/`reportlab` over `weasyprint`.
- **Build approach:** comprehensive end vision, built in verified phases.
- **Decided 2026-10-02:**
  1. Run once daily after market close; no live/intraday data.
  2. "Top setups this week" — up to 10, never forced; liquid stocks only.
  3. Weekly outlook = events calendar + base rates + conditional scenarios;
     no price targets.
  4. Global/commodity factor set as in §4.2 is the starting set.
  5. Self-scoring log is mandatory, with a 2–3 month paper-trading period.
  6. Analyst Digest: YouTube summaries for review only, daily ~11:00 PM,
     never used as input to fact/research-based analysis.
  7. Analyst Digest channels: the 5 listed in §4.6 (all Urdu).
  8. Analyst Digest method: Google Gemini API reading public YouTube links;
     speech-to-text on homidev only as fallback. Requires a Google AI
     Studio API key, kept in the secrets file (§6).
  9. AI provider for the main analysis: Google Gemini as well — one
     provider, one key, one bill. All AI calls go through one small,
     separate piece of code so the provider can be swapped later without
     touching the rest.

---

## 9. Open questions

1. Confirm or override the Python stack.
2. Which local macro indicators are v1-essential vs. later (§4.1).
3. Initial stock watchlist — Homi to provide a list of 10 stocks for a
   first test bot (on hold as of 2026-10-02).
4. How far the facts-only filter extends to PSX sites mixing facts and
   opinion (default: excluded).
5. **Privacy of portfolio data (Phase 2):** before holdings are sent to
   Gemini, either move to the paid tier (free-tier inputs may be used by
   Google to improve its products) or send only stock names/percentages,
   never quantities or values.
6. **Analyst Digest:** build order — after Phase 1 (recommended, one thing
   at a time) or first.
7. **Analyst Digest:** delivery channel — email or Telegram.
8. Ask AKD whether they offer a data feed/API.
9. Check employer insider-trading policy (§7).

---

## 10. Change log

- **2026-10-02:** Added purpose items (chart time-saving, weekly outlook,
  top setups, Analyst Digest). Locked: daily end-of-day runs; up to 10 top
  setups from liquid stocks; weekly outlook format; global/commodity sector
  map; mandatory self-scoring + paper-trading period; Analyst Digest as a
  review-only separate module at ~11 PM. Added annotated charts, YouTube and
  insider-policy compliance notes, revised phase table.
- **2026-10-02 (later):** Analyst Digest channels recorded (5, all Urdu).
  Primary method changed to Gemini YouTube-link summarization, with
  speech-to-text on homidev as fallback; verification step added.
- **2026-10-02 (later):** Gemini confirmed as Analyst Digest method
  (Decided 7–8). New open question: AI provider for the main analysis.
- **2026-10-02 (later):** Gemini confirmed for the main analysis too
  (Decided 9). New open question: privacy of portfolio data on free tier.
- **2026-10-02 (later):** Trial plan recorded (§4.5): ~3-month parallel
  run on 10 blue-chip stocks across sectors, compared against Homi's own
  analysis. Project on hold until the 10-stock list is provided.
