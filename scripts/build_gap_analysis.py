#!/usr/bin/env python3
import json
import math
import re
import statistics
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEWS_PATH = ROOT / "data" / "news.json"
OUT_PATH = ROOT / "data" / "gap_analysis.json"
DAY_MS = 86_400_000

REGIONS = ("CHINA", "GLOBAL", "KOREA")
CATEGORIES = ("GACHA", "OUTFIT", "EVENT", "UPDATE", "FEATURE", "OTHER")
CATEGORY_LABELS = {
    "GACHA": "ガチャ",
    "OUTFIT": "衣装",
    "EVENT": "イベント",
    "UPDATE": "アップデート",
    "FEATURE": "新機能",
    "OTHER": "その他",
}

STOP_WORDS_RE = re.compile(
    r"きらめきパラダイス|キラパラ|life\s*makeover|以闪亮之名|스타일라잇|公式|official|"
    r"お知らせ|予告|preview|登場|開催|イベント|event|更新|アップデート|update",
    re.I,
)
URL_RE = re.compile(r"https?://\S+", re.I)
HASH_RE = re.compile(r"#[^\s#]+")
DATE_YMD_RE = re.compile(r"20\d{2}[年./-]\d{1,2}[月./-]\d{1,2}日?")
DATE_MD_RE = re.compile(r"\d{1,2}月\d{1,2}日")
TIME_RE = re.compile(r"\d{1,2}:\d{2}")
NON_TEXT_RE = re.compile(r"[^0-9a-zぁ-ゖァ-ヺー一-龯가-힣]+", re.I)
NAMED_RE = re.compile(r"[「『【\[(]([^」』】\])]{2,28})[」』】\])]" )


def read_rows():
    try:
        data = json.loads(NEWS_PATH.read_text(encoding="utf-8"))
        return [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []
    except Exception:
        return []


def searchable(row):
    return " ".join(str(row.get(k) or "") for k in ("titleJa", "summaryJa", "bodyJa", "title", "body"))


def category_of(row):
    t = searchable(row).lower()
    if re.search(r"ガチャ|追光|light\s*chase|招募|召喚|限定ガチャ|祈願", t, re.I):
        return "GACHA"
    if re.search(r"星\s*[456]|[456]\s*星|★\s*[456]|セット|衣装|コーデ|ファッション|outfit|fashion|套装|时装|의상|코디", t, re.I):
        return "OUTFIT"
    if re.search(r"大型アップデート|アップデート|update|更新|バージョン|版本|업데이트", t, re.I):
        return "UPDATE"
    if re.search(r"新機能|機能追加|システム|撮影機能|ホーム機能|feature|function|新功能|系统|기능", t, re.I):
        return "FEATURE"
    if re.search(r"イベント|event|開催|活動|活动|이벤트", t, re.I):
        return "EVENT"
    return "OTHER"


def normalize(value):
    text = unicodedata.normalize("NFKC", str(value or "")).lower()
    text = URL_RE.sub(" ", text)
    text = HASH_RE.sub(" ", text)
    text = DATE_YMD_RE.sub(" ", text)
    text = DATE_MD_RE.sub(" ", text)
    text = TIME_RE.sub(" ", text)
    text = STOP_WORDS_RE.sub(" ", text)
    return NON_TEXT_RE.sub("", text)


def gram_set(value, n=2):
    text = normalize(value)
    if not text:
        return set()
    if len(text) <= n:
        return {text}
    return {text[i:i+n] for i in range(len(text) - n + 1)}


def dice(a, b):
    if not a or not b:
        return 0.0
    return 2 * len(a & b) / (len(a) + len(b))


def named_pieces(value):
    text = unicodedata.normalize("NFKC", str(value or ""))
    out = []
    for match in NAMED_RE.finditer(text):
        value = normalize(match.group(1))
        if len(value) >= 2:
            out.append(value)
    return set(out[:12])


def shared_named_score(a, b):
    aa, bb = named_pieces(a), named_pieces(b)
    if not aa or not bb:
        return 0.0
    for x in aa:
        for y in bb:
            if x == y or (min(len(x), len(y)) >= 4 and (x in y or y in x)):
                return 1.0
    return 0.0


def similarity(a, b):
    a_title = str(a.get("titleJa") or a.get("title") or "")
    b_title = str(b.get("titleJa") or b.get("title") or "")
    a_body = str(a.get("summaryJa") or a.get("bodyJa") or a.get("body") or "")[:360]
    b_body = str(b.get("summaryJa") or b.get("bodyJa") or b.get("body") or "")[:360]
    title = max(dice(gram_set(a_title, 2), gram_set(b_title, 2)), dice(gram_set(a_title, 3), gram_set(b_title, 3)))
    body = dice(gram_set(a_body, 2), gram_set(b_body, 2))
    named = max(shared_named_score(a_title, b_title), shared_named_score(a_body, b_body))
    same_category = 1.0 if category_of(a) == category_of(b) else 0.0
    return min(1.0, title * 0.68 + body * 0.18 + named * 0.10 + same_category * 0.04)


def published_ms(row):
    try:
        epoch = float(row.get("publishedAtEpoch") or 0)
    except Exception:
        return 0
    if not math.isfinite(epoch) or epoch <= 0:
        return 0
    return int(epoch * 1000)


def candidate_dates(text, reference_ms):
    if not reference_ms:
        return []
    ref_year = datetime.fromtimestamp(reference_ms / 1000, tz=timezone.utc).year
    source = unicodedata.normalize("NFKC", str(text or ""))
    out = set()

    for m in re.finditer(r"(?:(20\d{2})年)?(\d{1,2})月(\d{1,2})日", source):
        explicit_year = int(m.group(1)) if m.group(1) else None
        month, day = int(m.group(2)), int(m.group(3))
        years = [explicit_year] if explicit_year else [ref_year - 1, ref_year, ref_year + 1]
        for year in years:
            try:
                out.add(int(datetime(year, month, day, tzinfo=timezone.utc).timestamp() * 1000))
            except ValueError:
                pass

    for m in re.finditer(r"(20\d{2})[/.\-](\d{1,2})[/.\-](\d{1,2})", source):
        year, month, day = map(int, m.groups())
        try:
            out.add(int(datetime(year, month, day, tzinfo=timezone.utc).timestamp() * 1000))
        except ValueError:
            pass
    return sorted(out)


def implementation_date(row):
    published = published_ms(row)
    if not published:
        return {"ms": 0, "basis": "不明"}
    text = " ".join(str(row.get(k) or "") for k in ("summaryJa", "bodyJa", "body", "titleJa"))
    dates = [d for d in candidate_dates(text, published) if published - 3 * DAY_MS <= d <= published + 180 * DAY_MS]
    if dates:
        return {"ms": dates[0], "basis": "開始日"}
    return {"ms": published, "basis": "記事日"}


def build_matches(rows):
    japan = [r for r in rows if r.get("region") == "JAPAN"]
    foreign = [r for r in rows if r.get("region") in REGIONS and r.get("aiProcessed")]
    candidates = []

    for source in foreign:
        source_date = implementation_date(source)
        if not source_date["ms"]:
            continue
        source_category = category_of(source)
        for jp in japan:
            jp_date = implementation_date(jp)
            if not jp_date["ms"]:
                continue
            gap = round((jp_date["ms"] - source_date["ms"]) / DAY_MS)
            if gap < -21 or gap > 240:
                continue
            jp_category = category_of(jp)
            if source_category != jp_category and source_category != "OTHER" and jp_category != "OTHER":
                continue
            score = similarity(source, jp)
            if score < 0.36:
                continue
            category = jp_category if source_category == "OTHER" else source_category
            candidates.append({
                "source": source,
                "jp": jp,
                "sourceDate": source_date,
                "jpDate": jp_date,
                "gap": gap,
                "score": score,
                "category": category,
            })

    candidates.sort(key=lambda item: item["score"], reverse=True)
    used_source, used_jp_by_region, chosen = set(), set(), []
    for item in candidates:
        source_key = str(item["source"].get("id") or item["source"].get("sourceUrl") or "")
        jp_key = f'{item["source"].get("region")}:{item["jp"].get("id") or item["jp"].get("sourceUrl") or ""}'
        if not source_key or source_key in used_source or jp_key in used_jp_by_region:
            continue
        used_source.add(source_key)
        used_jp_by_region.add(jp_key)
        chosen.append(item)
    return chosen


def median(values):
    values = [v for v in values if isinstance(v, (int, float)) and math.isfinite(v)]
    return statistics.median(values) if values else None


def average(values):
    values = [v for v in values if isinstance(v, (int, float)) and math.isfinite(v)]
    return statistics.fmean(values) if values else None


def mad(values, med):
    if med is None:
        return None
    return median([abs(v - med) for v in values if isinstance(v, (int, float)) and math.isfinite(v)])


def plausible(matches):
    return [m for m in matches if -7 <= m["gap"] <= 180 and m["score"] >= 0.40]


def stats_for(matches, region=None, category=None):
    subset = plausible(matches)
    if region:
        subset = [m for m in subset if m["source"].get("region") == region]
    if category:
        subset = [m for m in subset if m["category"] == category]
    gaps = [m["gap"] for m in subset]
    med = median(gaps)
    return {
        "n": len(subset),
        "median": med,
        "average": average(gaps),
        "mad": mad(gaps, med),
    }


def model_for(matches, region, category):
    specific = stats_for(matches, region, category)
    if specific["n"] >= 2:
        return {**specific, "source": "地域×カテゴリ"}
    regional = stats_for(matches, region, None)
    if regional["n"] >= 2:
        return {**regional, "source": "地域全体"}
    category_all = stats_for(matches, None, category)
    if category_all["n"] >= 2:
        return {**category_all, "source": "カテゴリ全体"}
    overall = stats_for(matches)
    if overall["n"] >= 1:
        return {**overall, "source": "全地域"}
    return None


def iso_date(ms):
    if not ms:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date().isoformat()


def short_title(row):
    value = re.sub(r"\s+", " ", str(row.get("titleJa") or row.get("title") or "名称不明")).strip()
    return value if len(value) <= 68 else value[:67] + "…"


def build_forecasts(rows, matches):
    pending = [r for r in rows if r.get("earlyInfo") is True and r.get("region") in REGIONS]
    pending.sort(key=published_ms, reverse=True)
    out = []
    for row in pending[:60]:
        category = category_of(row)
        source_date = implementation_date(row)
        model = model_for(matches, row.get("region"), category)
        item = {
            "id": row.get("id"),
            "title": short_title(row),
            "region": row.get("region"),
            "category": category,
            "categoryLabel": CATEGORY_LABELS.get(category, "その他"),
            "sourceDate": iso_date(source_date["ms"]),
            "sourceBasis": source_date["basis"],
            "sourceUrl": row.get("sourceUrl") or "",
            "prediction": None,
        }
        if model and model.get("median") is not None and source_date["ms"]:
            lag = round(model["median"])
            predicted = source_date["ms"] + lag * DAY_MS
            spread = max(7, round((model.get("mad") * 1.5 if model.get("mad") is not None else 14)), 14 if model["n"] < 3 else 0)
            confidence = "高め" if model["n"] >= 6 else "中" if model["n"] >= 3 else "低め"
            item["prediction"] = {
                "date": iso_date(predicted),
                "rangeStart": iso_date(predicted - spread * DAY_MS),
                "rangeEnd": iso_date(predicted + spread * DAY_MS),
                "lagDays": lag,
                "modelSource": model["source"],
                "samples": model["n"],
                "confidence": confidence,
            }
        out.append(item)
    return out


def build_match_rows(matches):
    shown = [m for m in matches if m["score"] >= 0.40]
    shown.sort(key=lambda m: max(m["sourceDate"]["ms"], m["jpDate"]["ms"]), reverse=True)
    out = []
    for m in shown[:80]:
        out.append({
            "title": short_title(m["jp"]),
            "sourceRegion": m["source"].get("region"),
            "category": m["category"],
            "categoryLabel": CATEGORY_LABELS.get(m["category"], "その他"),
            "sourceDate": iso_date(m["sourceDate"]["ms"]),
            "sourceBasis": m["sourceDate"]["basis"],
            "jpDate": iso_date(m["jpDate"]["ms"]),
            "jpBasis": m["jpDate"]["basis"],
            "gapDays": m["gap"],
            "score": round(m["score"], 4),
            "sourceUrl": m["source"].get("sourceUrl") or "",
            "jpUrl": m["jp"].get("sourceUrl") or "",
        })
    return out


def clean_number(value, digits=2):
    if value is None:
        return None
    return round(float(value), digits)


def main():
    rows = read_rows()
    matches = build_matches(rows)
    region_stats = {}
    for region in REGIONS:
        stat = stats_for(matches, region)
        region_stats[region] = {
            "n": stat["n"],
            "median": clean_number(stat["median"], 1),
            "average": clean_number(stat["average"], 1),
            "mad": clean_number(stat["mad"], 1),
        }

    match_rows = build_match_rows(matches)
    payload = {
        "version": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sourceCount": len(rows),
        "matchedCount": len(match_rows),
        "earlyCount": sum(1 for r in rows if r.get("earlyInfo") is True),
        "stats": region_stats,
        "forecasts": build_forecasts(rows, matches),
        "matches": match_rows,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"gap analysis: rows={payload['sourceCount']} matches={payload['matchedCount']} early={payload['earlyCount']}")


if __name__ == "__main__":
    main()
