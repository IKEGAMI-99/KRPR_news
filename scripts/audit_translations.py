#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEWS_PATH = ROOT / "data" / "news.json"
CACHE_PATH = ROOT / "data" / "translations.json"

KANA_RE = re.compile(r"[ぁ-ゖァ-ヺー]")
HANGUL_RE = re.compile(r"[가-힣]")
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
LATIN_WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z'-]{2,}\b")
SPACE_RE = re.compile(r"\s+")


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def source_hash(row: dict) -> str:
    payload = "\n".join([
        str(row.get("region") or ""),
        str(row.get("title") or ""),
        str(row.get("body") or ""),
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def cache_key(row: dict) -> str:
    return str(row.get("sourceUrl") or row.get("id") or source_hash(row))


def compact(value) -> str:
    return SPACE_RE.sub(" ", str(value or "")).strip()


def likely_untranslated(row: dict):
    region = str(row.get("region") or "")
    if region == "JAPAN":
        return False, ""

    source_body = compact(row.get("body") or row.get("title"))
    translated_body = compact(row.get("bodyJa"))
    summary = compact(row.get("summaryJa"))
    translated = f"{translated_body}\n{summary}".strip()

    if not translated_body or not summary:
        return False, ""

    if source_body and translated_body == source_body:
        return True, "bodyJa is identical to the foreign source body"

    kana = len(KANA_RE.findall(translated))
    hangul = len(HANGUL_RE.findall(translated))
    cjk = len(CJK_RE.findall(translated))
    latin_words = LATIN_WORD_RE.findall(translated)

    # Korean prose should not survive into the Japanese body/summary. A couple
    # of Hangul characters can be a proper noun, so keep the threshold lenient.
    if hangul >= 8 and hangul > max(4, kana // 2):
        return True, f"Hangul residue: {hangul} chars"

    # Chinese and Japanese share Han characters, so the useful signal is a
    # long Han-heavy output with almost no kana. Proper nouns alone won't trip it.
    if region == "CHINA" and cjk >= 28 and kana < 6:
        return True, f"Chinese-looking output: cjk={cjk}, kana={kana}"

    # English names are common in this game. Only flag long English prose when
    # there is barely any Japanese grammar around it.
    if region == "GLOBAL" and len(latin_words) >= 18 and kana < 8:
        return True, f"English-looking output: words={len(latin_words)}, kana={kana}"

    # Region-independent safety net for suspiciously non-Japanese long output.
    visible_letters = kana + hangul + cjk + sum(len(word) for word in latin_words)
    if visible_letters >= 80 and kana < 4 and (hangul >= 5 or len(latin_words) >= 20):
        return True, "long translated output contains almost no Japanese kana"

    return False, ""


def main():
    parser = argparse.ArgumentParser(description="Find AI translations that still look Chinese, Korean, or English and invalidate them for regeneration.")
    parser.add_argument("--github-output", default="")
    args = parser.parse_args()

    rows = read_json(NEWS_PATH, [])
    if not isinstance(rows, list):
        rows = []
    cache = read_json(CACHE_PATH, {})
    if not isinstance(cache, dict):
        cache = {}
    items = cache.get("items")
    if not isinstance(items, dict):
        items = {}
        cache["items"] = items

    scanned = 0
    flagged = 0
    for row in rows:
        if str(row.get("region") or "") == "JAPAN":
            continue
        if not row.get("aiProcessed"):
            continue
        scanned += 1
        bad, reason = likely_untranslated(row)
        if not bad:
            continue

        key = cache_key(row)
        items.pop(key, None)
        for field in ("titleJa", "bodyJa", "summaryJa", "aiProcessed", "aiModel"):
            row.pop(field, None)
        flagged += 1
        print(f"translation audit flagged [{row.get('region')}] {str(row.get('title') or '')[:80]} :: {reason}")

    write_json(CACHE_PATH, cache)
    write_json(NEWS_PATH, rows)
    print(f"translation audit: scanned={scanned} flagged={flagged}")

    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as fh:
            fh.write(f"audit_scanned={scanned}\n")
            fh.write(f"audit_flagged={flagged}\n")


if __name__ == "__main__":
    main()
