#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEWS_PATH = ROOT / "data" / "news.json"
CACHE_PATH = ROOT / "data" / "translations.json"
GLOSSARY_PATH = ROOT / "data" / "translation_glossary.json"

MODEL_ID = "Qwen/Qwen2.5-3B-Instruct-GGUF"
MODEL_VARIANT = "Q4_K_M"
MODEL_REVISION = "qwen2.5-3b-instruct-q4-k-m-summary-facts-v2"
CACHE_VERSION = 2
SUMMARY_FORMAT_VERSION = 2

TRANSLATION_FIELDS = ("titleJa", "bodyJa", "summaryJa")


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
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


def normalized_cache(raw) -> dict:
    if not isinstance(raw, dict):
        raw = {}
    items = raw.get("items")
    if not isinstance(items, dict):
        items = {}
    return {
        "version": CACHE_VERSION,
        "model": raw.get("model") or f"{MODEL_ID}:{MODEL_VARIANT}",
        "modelRevision": MODEL_REVISION,
        "items": items,
    }


def content_entry_valid(row: dict, entry) -> bool:
    if not isinstance(entry, dict):
        return False
    if entry.get("contentHash") != source_hash(row):
        return False
    return all(isinstance(entry.get(field), str) and entry.get(field).strip() for field in TRANSLATION_FIELDS)


def valid_entry(row: dict, entry) -> bool:
    if not content_entry_valid(row, entry):
        return False
    return int(entry.get("summaryFormatVersion") or 0) == SUMMARY_FORMAT_VERSION


def apply_cache(rows: list, cache: dict) -> int:
    applied = 0
    items = cache.get("items", {})
    for row in rows:
        entry = items.get(cache_key(row))
        # Keep existing translations visible while an old prose summary waits for
        # the new bullet-point format to be regenerated.
        if content_entry_valid(row, entry):
            for field in TRANSLATION_FIELDS:
                row[field] = entry[field]
            row["aiProcessed"] = True
            row["aiModel"] = entry.get("model") or cache.get("model")
            row["aiSummaryFormat"] = "facts-v2" if int(entry.get("summaryFormatVersion") or 0) == SUMMARY_FORMAT_VERSION else "legacy"
            applied += 1
        else:
            for field in TRANSLATION_FIELDS:
                row.pop(field, None)
            row.pop("aiProcessed", None)
            row.pop("aiModel", None)
            row.pop("aiSummaryFormat", None)
    return applied


def pending_rows(rows: list, cache: dict) -> list:
    items = cache.get("items", {})
    candidates = []
    for row in rows:
        if not row.get("title") and not row.get("body"):
            continue
        if valid_entry(row, items.get(cache_key(row))):
            continue
        candidates.append(row)

    def priority(row):
        platform = str(row.get("platform") or "")
        official = 1 if "公式" in platform or "プレスリリース" in platform else 0
        return (int(row.get("publishedAtEpoch") or 0), official)

    candidates.sort(key=priority, reverse=True)
    return candidates


def glossary_text() -> str:
    raw = read_json(GLOSSARY_PATH, {})
    if not isinstance(raw, dict):
        return ""
    pairs = []
    for source, target in raw.items():
        source = str(source).strip()
        target = str(target).strip()
        if source and target:
            pairs.append(f"- {source} → {target}")
    return "\n".join(pairs[:200])


def clean_output(value, max_len: int) -> str:
    if not isinstance(value, str):
        return ""
    value = value.strip()
    value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.I)
    value = re.sub(r"\s*```$", "", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value[:max_len].strip()


def normalize_bullet_summary(value) -> str:
    value = clean_output(value, 900)
    if not value:
        return ""

    raw_lines = [line.strip() for line in value.splitlines() if line.strip()]
    if len(raw_lines) == 1:
        one = re.sub(r"^[・●▪︎◦*\-]+\s*", "", raw_lines[0]).strip()
        # If the model ignored the requested line breaks, split ordinary Japanese
        # sentences so the UI still remains a compact fact list.
        parts = [p.strip() for p in re.split(r"(?<=。)\s*", one) if p.strip()]
        raw_lines = parts if len(parts) > 1 else [one]

    bullets = []
    seen = set()
    for line in raw_lines:
        line = re.sub(r"^[・●▪︎◦*\-]+\s*", "", line).strip()
        if not line:
            continue
        line = line.rstrip("。 ")
        if not line or line in seen:
            continue
        seen.add(line)
        bullets.append("・" + line[:170])
        if len(bullets) >= 5:
            break

    return "\n".join(bullets)


def parse_json_object(text: str):
    text = (text or "").strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            return None
    return None


def build_messages(row: dict, retry_note: str = ""):
    region = str(row.get("region") or "")
    title = str(row.get("title") or "").strip()
    body = str(row.get("body") or "").strip()[:1800]
    glossary = glossary_text()

    common = """あなたは『きらめきパラダイス / 以闪亮之名 / Life Makeover / Stylight』専用のニュース翻訳・情報抽出エンジンです。
必ず原文だけを根拠にしてください。原文にない情報、推測、補足、感想を追加してはいけません。
日付、時刻、数値、星の数、報酬数、イベント期間は落とさず正確に保持してください。
人物名・衣装名・イベント名・アイテム名などの固有名詞は、下の用語集に公式対応がある場合だけ置換してください。
用語集にない固有名詞は、公式日本語名を創作せず、必要なら原語を残してください。
宣伝文句は自然な日本語に整えて構いませんが、意味を強めたり弱めたりしないでください。

summaryJaは文章要約にしてはいけません。ニュースを見た人が事実だけを一瞬で把握できる、2〜5個の箇条書きにしてください。
各行は必ず「・」から始め、1行につき1情報だけにしてください。
原文に存在する項目だけを書き、存在しない項目を推測して埋めてはいけません。
優先して抽出する情報は次の通りです。
- 何が追加・公開・変更・復刻されたか
- 開始日時、終了日時、開催期間、公開日
- 入手方法、参加条件、解放条件
- 衣装の星数、報酬、価格、回数など重要な数値
- メンテナンスや仕様変更なら変更点

例:
・追加: 星6セット「○○」が登場
・期間: 8月27日10:00〜9月16日23:59
・入手: 限定ガチャ「○○」から獲得
・報酬: ログイン7日でダイヤ×200

「イベントが開催されます」「様々な報酬を獲得できます」のような曖昧な説明だけの行は禁止です。
同じ情報の言い換えを重複させないでください。
Markdown、コードブロック、前置き、説明文は禁止です。JSONオブジェクトだけを返してください。"""

    if region == "JAPAN":
        task = """入力はすでに日本語です。翻訳はせず、summaryJaだけを事実の箇条書きで作ってください。
出力形式:
{\"summaryJa\":\"・追加: ...\\n・期間: ...\"}"""
    else:
        task = """titleJaとbodyJaは自然で読みやすい日本語に翻訳してください。summaryJaは翻訳文の作文要約ではなく、原文にある事実だけを箇条書きで抽出してください。
出力形式:
{\"titleJa\":\"...\",\"bodyJa\":\"...\",\"summaryJa\":\"・追加: ...\\n・期間: ...\"}"""

    user_payload = {
        "region": region,
        "title": title,
        "body": body,
        "glossary": glossary,
    }
    if retry_note:
        user_payload["retryInstruction"] = retry_note

    return [
        {"role": "system", "content": common + "\n\n" + task},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
    ]


def validate_result(row: dict, obj) -> dict | None:
    if not isinstance(obj, dict):
        return None

    region = str(row.get("region") or "")
    source_title = str(row.get("title") or "").strip()
    source_body = str(row.get("body") or source_title).strip()

    if region == "JAPAN":
        title_ja = source_title
        body_ja = source_body
    else:
        title_ja = clean_output(obj.get("titleJa"), 240)
        body_ja = clean_output(obj.get("bodyJa"), 3000)
        if not title_ja or not body_ja:
            return None

    summary_ja = normalize_bullet_summary(obj.get("summaryJa"))
    if not summary_ja:
        return None

    bad_markers = ("retryInstruction", '"region":', '"glossary":', "出力形式")
    combined = title_ja + "\n" + body_ja + "\n" + summary_ja
    if any(marker in combined for marker in bad_markers):
        return None

    return {
        "titleJa": title_ja,
        "bodyJa": body_ja,
        "summaryJa": summary_ja,
    }


def infer_one(llm, row: dict) -> dict | None:
    attempts = [
        "",
        "前回の出力はJSONとして不正か、必須フィールドが欠けていました。指定したJSON形式だけを返し、summaryJaは必ず「・」で始まる事実の箇条書きにしてください。",
    ]
    for retry_note in attempts:
        try:
            response = llm.create_chat_completion(
                messages=build_messages(row, retry_note),
                temperature=0.05,
                top_p=0.9,
                max_tokens=900,
                seed=42,
            )
            text = response["choices"][0]["message"]["content"]
            result = validate_result(row, parse_json_object(text))
            if result:
                return result
        except Exception as exc:
            print(f"LLM attempt failed {cache_key(row)}: {exc}", file=sys.stderr)
    return None


def prune_cache(cache: dict, max_entries: int = 2500):
    items = cache.get("items", {})
    if len(items) <= max_entries:
        return
    ranked = sorted(
        items.items(),
        key=lambda kv: int((kv[1] or {}).get("updatedAtEpoch") or 0),
        reverse=True,
    )[:max_entries]
    cache["items"] = dict(ranked)


def write_github_output(path: str | None, pending: int, applied: int):
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(f"pending={pending}\n")
        fh.write(f"applied={applied}\n")


def cmd_prepare(args) -> int:
    rows = read_json(NEWS_PATH, [])
    if not isinstance(rows, list):
        rows = []
    cache = normalized_cache(read_json(CACHE_PATH, {}))
    applied = apply_cache(rows, cache)
    pending = len(pending_rows(rows, cache))
    write_json(NEWS_PATH, rows)
    write_json(CACHE_PATH, cache)
    write_github_output(args.github_output, pending, applied)
    print(f"translation cache applied: {applied}/{len(rows)}")
    print(f"translation pending: {pending}")
    return 0


def cmd_translate(args) -> int:
    model_path = Path(args.model or os.getenv("LLM_MODEL_PATH", "")).expanduser()
    if not model_path.is_file():
        print(f"model not found: {model_path}", file=sys.stderr)
        return 2

    rows = read_json(NEWS_PATH, [])
    if not isinstance(rows, list):
        rows = []
    cache = normalized_cache(read_json(CACHE_PATH, {}))
    apply_cache(rows, cache)
    pending = pending_rows(rows, cache)
    limit = max(1, int(args.max_items or os.getenv("LLM_MAX_ITEMS", "10")))
    selected = pending[:limit]

    if not selected:
        write_json(NEWS_PATH, rows)
        write_json(CACHE_PATH, cache)
        print("no new items need LLM processing")
        return 0

    from llama_cpp import Llama

    threads = max(2, min(4, os.cpu_count() or 4))
    llm = Llama(
        model_path=str(model_path),
        n_ctx=4096,
        n_batch=128,
        n_threads=threads,
        n_threads_batch=threads,
        verbose=False,
    )

    successes = 0
    failures = 0
    for index, row in enumerate(selected, 1):
        key = cache_key(row)
        print(f"[{index}/{len(selected)}] LLM {row.get('region')} {row.get('platform')}: {str(row.get('title') or '')[:70]}")
        result = infer_one(llm, row)
        if not result:
            failures += 1
            print(f"  failed: {key}", file=sys.stderr)
            continue

        entry = {
            "contentHash": source_hash(row),
            **result,
            "model": f"{MODEL_ID}:{MODEL_VARIANT}",
            "modelRevision": MODEL_REVISION,
            "summaryFormatVersion": SUMMARY_FORMAT_VERSION,
            "updatedAtEpoch": int(time.time()),
        }
        cache["items"][key] = entry
        successes += 1

        apply_cache(rows, cache)
        prune_cache(cache)
        write_json(CACHE_PATH, cache)
        write_json(NEWS_PATH, rows)

    apply_cache(rows, cache)
    prune_cache(cache)
    write_json(CACHE_PATH, cache)
    write_json(NEWS_PATH, rows)
    remaining = len(pending_rows(rows, cache))
    print(f"LLM processed: success={successes} failed={failures} remaining={remaining}")
    return 0 if successes or not selected else 1


def main():
    parser = argparse.ArgumentParser(description="Apply and generate Japanese translations/summaries for Kirapara news.")
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare", help="Apply cached translations and report pending items.")
    prepare.add_argument("--github-output", default=os.getenv("GITHUB_OUTPUT"))
    prepare.set_defaults(func=cmd_prepare)

    translate = sub.add_parser("translate", help="Run the local GGUF model for pending news.")
    translate.add_argument("--model", default="")
    translate.add_argument("--max-items", type=int, default=0)
    translate.set_defaults(func=cmd_translate)

    args = parser.parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
