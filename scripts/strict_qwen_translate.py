#!/usr/bin/env python3
import re
import sys
from pathlib import Path

import translate_news_llm as qwen
from glossary_schema import active_entries, read_glossary


STRICT_MODEL_REVISION = "qwen2.5-3b-instruct-q4-k-m-summary-facts-region-titles-strict-ja-v4"
URL_HASH_RE = re.compile(r"https?://\S+|#[^\s#]+")
KANA_RE = re.compile(r"[ぁ-ゖァ-ヺー]")
HANGUL_RE = re.compile(r"[가-힣] ")
HANGUL_CHAR_RE = re.compile(r"[가-힣]")
HAN_RE = re.compile(r"[一-龯㐀-䶿]")
LATIN_WORD_RE = re.compile(r"[A-Za-z]{3,}")

_ORIGINAL_BUILD_MESSAGES = qwen.build_messages
_ORIGINAL_VALIDATE_RESULT = qwen.validate_result


def scoped_preserved_terms(row: dict) -> list[str]:
    terms = [qwen.canonical_game_title(str(row.get("region") or ""))]
    try:
        doc = read_glossary(qwen.GLOSSARY_PATH)
        region = str(row.get("region") or "").upper()
        for entry in active_entries(doc):
            regions = {str(value).upper() for value in (entry.get("regions") or [])}
            if regions and region not in regions:
                continue
            if str(entry.get("behavior") or "translate") != "preserve":
                continue
            for key in ("sourceText", "targetText"):
                value = str(entry.get(key) or "").strip()
                if value:
                    terms.append(value)
    except Exception:
        pass
    return sorted({term for term in terms if term}, key=len, reverse=True)


def prose_for_language_check(value: str, row: dict) -> str:
    text = URL_HASH_RE.sub(" ", str(value or ""))
    for term in scoped_preserved_terms(row):
        text = re.sub(re.escape(term), " ", text, flags=re.IGNORECASE)
    text = re.sub(r"[\d\s\W_]+", " ", text, flags=re.UNICODE)
    return text.strip()


def japanese_failure_reason(row: dict, result: dict) -> str:
    region = str(row.get("region") or "").upper()
    if region == "JAPAN":
        check = str(result.get("summaryJa") or "")
        source = str(row.get("body") or row.get("title") or "")
    else:
        check = "\n".join([
            str(result.get("bodyJa") or ""),
            str(result.get("summaryJa") or ""),
        ])
        source = "\n".join([
            str(row.get("body") or ""),
            str(row.get("title") or ""),
        ])

    prose = prose_for_language_check(check, row)
    source_prose = prose_for_language_check(source, row)
    if len(source_prose) < 18:
        # Very short official posts can legitimately be almost entirely a proper
        # noun or product/set name. Do not force fake Japanese around them.
        return ""

    kana = len(KANA_RE.findall(prose))
    hangul = len(HANGUL_CHAR_RE.findall(prose))
    han = len(HAN_RE.findall(prose))
    latin_words = len(LATIN_WORD_RE.findall(prose))
    visible = max(1, len(re.sub(r"\s+", "", prose)))

    if region != "JAPAN":
        source_norm = re.sub(r"\s+", " ", source_prose).strip().casefold()
        output_norm = re.sub(r"\s+", " ", prose).strip().casefold()
        if len(source_norm) >= 25 and output_norm == source_norm:
            return "原文がほぼそのまま返されています"

    if kana < 3 or kana / visible < 0.025:
        return f"日本語かな文字が不足しています(kana={kana}, visible={visible})"
    if hangul >= 3 and hangul > kana * 0.25:
        return f"韓国語が多く残っています(hangul={hangul}, kana={kana})"
    if han >= 35 and kana / max(1, han) < 0.10:
        return f"中国語原文が多く残っている可能性があります(han={han}, kana={kana})"
    if latin_words >= 14 and latin_words > kana * 0.8:
        return f"英語文が多く残っています(latinWords={latin_words}, kana={kana})"
    return ""


def strict_build_messages(row: dict, retry_note: str = ""):
    messages = _ORIGINAL_BUILD_MESSAGES(row, retry_note)
    region = str(row.get("region") or "").upper()
    language_rule = f"""

【最優先・日本語出力ルール】
region={region} の記事でも、ユーザーに表示する titleJa / bodyJa / summaryJa の説明文は必ず自然な日本語にしてください。
中国語・韓国語・英語の文章を原文のまま返すことは禁止です。単語を少し置換しただけの原文コピーも禁止です。
日本語以外を残してよいのは、用語集で原語保持と指定された固有名詞、人物名、セット名、イベント名、公式ゲームタイトル、URL、ハッシュタグだけです。
固有名詞の前後にある説明・日時・条件・報酬・動作・告知文は必ず日本語へ翻訳してください。
特に bodyJa と summaryJa は日本語の文章として読めることが必須です。翻訳できていない場合は出力を完了したことにしてはいけません。
JSONキーは指定どおりにし、値だけを日本語化してください。
"""
    messages[0]["content"] = str(messages[0].get("content") or "") + language_rule
    return messages


def strict_validate_result(row: dict, obj):
    result = _ORIGINAL_VALIDATE_RESULT(row, obj)
    if not result:
        return None
    reason = japanese_failure_reason(row, result)
    if reason:
        print(f"  rejected non-Japanese output: {qwen.cache_key(row)}: {reason}", file=sys.stderr)
        return None
    return result


def strict_infer_one(llm, row: dict):
    attempts = [
        "日本語への完全翻訳を最優先してください。原文言語の文章を残さないでください。",
        "前回は日本語化が不十分でした。固有名詞・URL・ハッシュタグ以外の中国語・韓国語・英語文をすべて自然な日本語へ翻訳し直してください。JSONだけを返してください。",
        "最終再試行です。bodyJaとsummaryJaが日本語として読めない出力は失敗です。原文コピーは禁止。固有名詞以外を必ず日本語にしてください。",
    ]
    for attempt, retry_note in enumerate(attempts, 1):
        try:
            response = llm.create_chat_completion(
                messages=strict_build_messages(row, retry_note),
                temperature=0.0,
                top_p=0.85,
                max_tokens=1000,
                seed=42 + attempt,
            )
            text = response["choices"][0]["message"]["content"]
            result = strict_validate_result(row, qwen.parse_json_object(text))
            if result:
                return result
        except Exception as exc:
            print(f"LLM strict attempt {attempt} failed {qwen.cache_key(row)}: {exc}", file=sys.stderr)
    return None


def purge_non_japanese_cache() -> int:
    rows = qwen.read_json(qwen.NEWS_PATH, [])
    cache = qwen.normalized_cache(qwen.read_json(qwen.CACHE_PATH, {}))
    if not isinstance(rows, list):
        return 0
    items = cache.get("items", {})
    removed = 0
    for row in rows:
        key = qwen.cache_key(row)
        entry = items.get(key)
        if not qwen.content_entry_valid(row, entry):
            continue
        model = str((entry or {}).get("model") or "")
        if "GPT-5.6 Sol" in model or (entry or {}).get("managedBySol"):
            continue
        result = {field: str((entry or {}).get(field) or "") for field in qwen.TRANSLATION_FIELDS}
        reason = japanese_failure_reason(row, result)
        if not reason:
            continue
        items.pop(key, None)
        removed += 1
        print(f"purged non-Japanese cache: {key}: {reason}")

    if removed:
        qwen.apply_cache(rows, cache)
        qwen.write_json(qwen.CACHE_PATH, cache)
        qwen.write_json(qwen.NEWS_PATH, rows)
    print(f"strict Japanese cache audit: removed={removed}")
    return removed


def patch_qwen_module() -> None:
    qwen.MODEL_REVISION = STRICT_MODEL_REVISION
    qwen.build_messages = strict_build_messages
    qwen.validate_result = strict_validate_result
    qwen.infer_one = strict_infer_one


def run_prepare_or_translate(args: list[str]) -> int:
    patch_qwen_module()
    purge_non_japanese_cache()
    old_argv = sys.argv[:]
    try:
        sys.argv = [str(Path(qwen.__file__)), *args]
        try:
            qwen.main()
        except SystemExit as exc:
            return int(exc.code or 0)
    finally:
        sys.argv = old_argv
    return 0


def run_regenerate(args: list[str]) -> int:
    patch_qwen_module()
    import regenerate_ai
    old_argv = sys.argv[:]
    try:
        sys.argv = [str(Path(regenerate_ai.__file__)), *args]
        try:
            regenerate_ai.main()
        except SystemExit as exc:
            return int(exc.code or 0)
    finally:
        sys.argv = old_argv
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: strict_qwen_translate.py prepare|translate|regenerate [ARGS...]", file=sys.stderr)
        return 2
    command = sys.argv[1]
    args = sys.argv[2:]
    if command in {"prepare", "translate"}:
        return run_prepare_or_translate([command, *args])
    if command == "regenerate":
        return run_regenerate(args)
    print(f"unknown command: {command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
