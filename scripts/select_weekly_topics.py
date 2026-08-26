#!/usr/bin/env python3
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEWS_PATH = ROOT / "data" / "news.json"
TOPICS_PATH = ROOT / "data" / "weekly_topics.json"

HIGH_VALUE = {
    "新衣装": 13, "新セット": 13, "セット": 5, "星6": 12, "6星": 12, "★6": 12,
    "ガチャ": 10, "イベント": 8, "アップデート": 12, "大型アップデート": 18,
    "新機能": 14, "コラボ": 18, "限定": 8, "復刻": 6, "報酬": 5, "無料": 5,
    "予告": 7, "登場": 5, "実装": 8, "開催": 4, "メンテナンス": -5,
    "coming soon": 7, "update": 10, "collab": 18, "limited": 8, "event": 6,
    "预告": 7, "联动": 18, "限定": 8, "更新": 9, "이벤트": 6, "업데이트": 10,
}


def read_rows():
    try:
        data = json.loads(NEWS_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def searchable(row):
    return "\n".join(str(row.get(k) or "") for k in ("titleJa", "summaryJa", "bodyJa", "title", "body")).lower()


def heuristic_score(row, now_epoch):
    published = int(row.get("publishedAtEpoch") or 0)
    age_hours = max(0.0, (now_epoch - published) / 3600) if published else 168.0
    recency = max(0, 24 - int(age_hours / 7))
    score = 18 + recency

    platform = str(row.get("platform") or "")
    if "公式" in platform:
        score += 15
    if row.get("earlyInfo"):
        score += 13
    if row.get("aiProcessed") and row.get("summaryJa"):
        score += 3
    if row.get("imageUrl") or row.get("imageUrls"):
        score += 2

    text = searchable(row)
    for marker, weight in HIGH_VALUE.items():
        if marker.lower() in text:
            score += weight

    # Tiny social posts and pure maintenance notices should not dominate a weekly digest.
    if len(text) < 90:
        score -= 7
    if "メンテナンス" in text and not any(k in text for k in ("アップデート", "新機能", "実装")):
        score -= 8

    return max(0, min(100, int(score)))


def compact_title(row):
    title = str(row.get("titleJa") or row.get("title") or "注目ニュース").strip()
    title = re.sub(r"\s+", " ", title)
    return title if len(title) <= 56 else title[:55].rstrip() + "…"


def parse_json_object(text):
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except Exception:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            return None
    return None


def ai_select(candidates, model_path):
    if not model_path or not Path(model_path).exists():
        return None
    try:
        from llama_cpp import Llama
    except Exception as exc:
        print(f"weekly topics AI unavailable: {exc}")
        return None

    digest = []
    for row in candidates:
        digest.append({
            "id": row.get("id"),
            "region": row.get("region"),
            "platform": row.get("platform"),
            "baseScore": row.get("importanceScore", 0),
            "earlyInfo": bool(row.get("earlyInfo")),
            "title": compact_title(row),
            "facts": str(row.get("summaryJa") or row.get("bodyJa") or row.get("body") or "")[:420],
        })

    prompt = (
        "あなたは『きらめきパラダイス / Life Makeover』ニュースアプリの編集者です。\n"
        "以下は直近7日間の記事候補です。今週ユーザーが特に知る価値の高い3件だけを選んでください。\n"
        "新イベント、新衣装・ガチャ、大型更新、新機能、コラボ、日本未告知の海外先行情報を重視し、\n"
        "単なるメンテナンスや似た内容の重複記事は優先しないでください。地域が偏りすぎないことも考慮してください。\n"
        "各記事に0〜100の注目度を付け、titleは日本語で24文字程度の短い見出しにしてください。\n"
        "出力は説明なしのJSONのみ: {\"topics\":[{\"id\":\"...\",\"score\":90,\"title\":\"...\"}, ...]}\n\n"
        + json.dumps(digest, ensure_ascii=False)
    )

    try:
        llm = Llama(model_path=model_path, n_ctx=4096, n_threads=4, verbose=False)
        out = llm.create_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=420,
        )
        text = out["choices"][0]["message"]["content"]
        parsed = parse_json_object(text)
        topics = parsed.get("topics") if isinstance(parsed, dict) else None
        return topics if isinstance(topics, list) else None
    except Exception as exc:
        print(f"weekly topics AI failed: {exc}")
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="")
    args = parser.parse_args()

    rows = read_rows()
    if not rows:
        TOPICS_PATH.write_text("[]\n", encoding="utf-8")
        return

    now_epoch = int(datetime.now(timezone.utc).timestamp())
    latest_epoch = max((int(r.get("publishedAtEpoch") or 0) for r in rows), default=0)
    # Protect against runner clock/source timestamp skew while keeping the selection to roughly one week.
    reference_epoch = max(now_epoch, latest_epoch)
    cutoff = reference_epoch - 7 * 24 * 3600

    for row in rows:
        row.pop("weeklyTopic", None)
        row["importanceScore"] = heuristic_score(row, reference_epoch)

    weekly = [r for r in rows if int(r.get("publishedAtEpoch") or 0) >= cutoff]
    weekly.sort(key=lambda r: (int(r.get("importanceScore") or 0), int(r.get("publishedAtEpoch") or 0)), reverse=True)
    candidates = weekly[:15]

    ai_topics = ai_select(candidates, args.model)
    candidate_by_id = {str(r.get("id")): r for r in candidates}
    selected = []
    seen = set()

    if ai_topics:
        for item in ai_topics:
            if not isinstance(item, dict):
                continue
            article_id = str(item.get("id") or "")
            row = candidate_by_id.get(article_id)
            if not row or article_id in seen:
                continue
            seen.add(article_id)
            score = max(0, min(100, int(item.get("score") or row.get("importanceScore") or 0)))
            row["importanceScore"] = score
            selected.append((row, str(item.get("title") or "").strip() or compact_title(row), score))
            if len(selected) >= 3:
                break

    selector = "qwen2.5-3b"
    if len(selected) < 3:
        selector = "heuristic-fallback" if not ai_topics else "qwen2.5-3b+fallback"
        for row in candidates:
            article_id = str(row.get("id") or "")
            if not article_id or article_id in seen:
                continue
            seen.add(article_id)
            selected.append((row, compact_title(row), int(row.get("importanceScore") or 0)))
            if len(selected) >= 3:
                break

    topics = []
    for rank, (row, title, score) in enumerate(selected[:3], start=1):
        row["weeklyTopic"] = True
        topics.append({
            "rank": rank,
            "id": row.get("id"),
            "title": title[:64],
            "score": score,
            "region": row.get("region"),
            "platform": row.get("platform"),
            "sourceUrl": row.get("sourceUrl"),
        })

    NEWS_PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    TOPICS_PATH.write_text(json.dumps({
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "selector": selector,
        "topics": topics,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"weekly topics: selector={selector} candidates={len(candidates)} selected={len(topics)}")


if __name__ == "__main__":
    main()
