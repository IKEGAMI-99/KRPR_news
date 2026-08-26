#!/usr/bin/env python3
import difflib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEWS_PATH = ROOT / "data" / "news.json"

SPACE_RE = re.compile(r"\s+")
PUNCT_RE = re.compile(r"[^0-9A-Za-zぁ-ゖァ-ヺー一-龯가-힣]+")

PREVIEW_MARKERS = (
    # Japanese translations
    "予告", "先行公開", "先行情報", "近日", "まもなく", "登場予定", "実装予定", "開催予定", "公開予定",
    "配信予定", "アップデート予定", "次回", "次期", "ティザー", "明日登場", "明日公開", "今後登場",
    # Chinese source text
    "预告", "抢先", "即将", "敬请期待", "将于", "前瞻", "明日上线", "即将上线", "即将开启",
    # English source text
    "coming soon", "upcoming", "preview", "teaser", "will arrive", "will be available", "launches on", "available on",
    # Korean source text
    "예고", "곧 공개", "출시 예정", "업데이트 예정", "등장 예정", "공개 예정", "사전 공개",
)


def read_rows():
    try:
        data = json.loads(NEWS_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def normalized(value):
    value = SPACE_RE.sub(" ", str(value or "")).strip().lower()
    return PUNCT_RE.sub("", value)


def char_ngrams(value, n=2):
    text = normalized(value)
    if len(text) < n:
        return {text} if text else set()
    return {text[i:i+n] for i in range(len(text) - n + 1)}


def similarity(a, b):
    a = normalized(a)
    b = normalized(b)
    if not a or not b:
        return 0.0
    seq = difflib.SequenceMatcher(None, a[:260], b[:260]).ratio()
    ga = char_ngrams(a[:420])
    gb = char_ngrams(b[:420])
    jaccard = len(ga & gb) / max(1, len(ga | gb))
    return max(seq, jaccard * 1.45)


def searchable(row):
    return " ".join(str(row.get(k) or "") for k in ("titleJa", "summaryJa", "bodyJa", "title", "body"))


def preview_signal(row):
    text = searchable(row).lower()
    marker = next((m for m in PREVIEW_MARKERS if m.lower() in text), "")
    if marker:
        return marker

    # Explicit future dates/relative wording in otherwise translated text.
    if re.search(r"(?:明日|来週|来月|\d{1,2}月\d{1,2}日).{0,14}(?:登場|公開|開催|実装|配信|開始|アップデート)", text):
        return "future announcement"
    return ""


def main():
    rows = read_rows()
    japan = [r for r in rows if r.get("region") == "JAPAN"]
    japan_texts = [(r, searchable(r)) for r in japan]

    tagged = 0
    cleared = 0
    for row in rows:
        old = bool(row.get("earlyInfo"))
        for key in ("earlyInfo", "earlyInfoReason", "earlyInfoConfidence"):
            row.pop(key, None)

        if row.get("region") == "JAPAN" or not row.get("aiProcessed"):
            if old:
                cleared += 1
            continue

        marker = preview_signal(row)
        if not marker:
            if old:
                cleared += 1
            continue

        candidate_text = searchable(row)
        best_score = 0.0
        best_jp = None
        for jp, jp_text in japan_texts:
            score = similarity(candidate_text, jp_text)
            if score > best_score:
                best_score = score
                best_jp = jp

        # If a reasonably similar Japanese announcement already exists, this is
        # no longer treated as advance information in the current feed.
        if best_score >= 0.42:
            if old:
                cleared += 1
            continue

        row["earlyInfo"] = True
        row["earlyInfoReason"] = "海外公式の予告・近日公開系情報で、現在の日本版フィードに近い告知が見つかっていません"
        row["earlyInfoConfidence"] = round(max(0.55, min(0.92, 0.78 - best_score / 2)), 2)
        tagged += 1

    NEWS_PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"early-info tagging: tagged={tagged} cleared={cleared} japan_reference={len(japan)}")


if __name__ == "__main__":
    main()
