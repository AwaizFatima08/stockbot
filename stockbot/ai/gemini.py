"""The single, swappable AI provider module (design doc Decided 9).

Everything the rest of the system needs from an AI model goes through
`narrate()`. To change provider, change this file only.

Rules enforced by the prompt and by `_sanitise()`:
- rewords given facts only, adds no new numbers;
- no buy/sell/hold instructions, no price targets, no predictions;
- hedged, neutral tone.
"""
from __future__ import annotations

import json
import logging
import re

from stockbot.config import Settings

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the writing assistant of a personal stock-research notebook for the Pakistan Stock Exchange.
You receive end-of-day facts and indicator readings for a watchlist, in JSON.
Write a short plain-English daily note (150-300 words) for an experienced reader.

Hard rules:
1. Use only the numbers given. Never invent, estimate or round to a different value.
2. Never tell the reader to buy, sell, hold, add, trim, enter or exit. Never give a price target or a prediction.
   Describe what the data shows, what conditions would confirm or weaken the current picture, and what historically
   this kind of reading has meant in general terms.
3. Mark uncertainty honestly. If the data section lists problems, mention them first.
4. Group stocks by what stands out (unusual volume, trend changes, stretched RSI). Skip stocks with nothing notable
   in one sentence at the end.
5. Plain language, no hype, no emojis, no headings. Paragraphs only.
"""

_FORBIDDEN = re.compile(r"\b(buy|sell|hold|accumulate|short|go long|price target|target price|will rise|will fall|guaranteed)\b", re.I)


class AIDisabled(Exception):
    pass


def _sanitise(text: str) -> tuple[str, list[str]]:
    """Flag (not silently remove) forbidden advisory language."""
    flags = sorted({m.group(0).lower() for m in _FORBIDDEN.finditer(text)})
    return text.strip(), flags


def narrate(payload: dict, cfg: Settings) -> tuple[str | None, str]:
    """Returns (narrative or None, status message)."""
    if not cfg.ai_enabled:
        return None, "AI narrative disabled in settings.toml"
    key = cfg.gemini_api_key
    if not key:
        return None, "AI narrative skipped: GEMINI_API_KEY not set"
    try:
        from google import genai  # type: ignore
        from google.genai import types  # type: ignore
    except ImportError:
        return None, "AI narrative skipped: google-genai package not installed"

    try:
        client = genai.Client(api_key=key)
        resp = client.models.generate_content(
            model=cfg.ai_model,
            contents=json.dumps(payload, indent=1),
            config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, temperature=0.3),
        )
        text = (resp.text or "").strip()
    except Exception as e:  # noqa: BLE001 - any provider failure must not kill the report
        log.warning("Gemini call failed: %s", e)
        return None, f"AI narrative failed: {type(e).__name__}: {e}"
    if not text:
        return None, "AI narrative failed: empty response"
    text, flags = _sanitise(text)
    status = f"AI narrative by {cfg.ai_model}"
    if flags:
        status += f" (WARN: advisory words detected: {', '.join(flags)})"
    return text, status
