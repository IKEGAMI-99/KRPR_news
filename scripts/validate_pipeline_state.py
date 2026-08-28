#!/usr/bin/env python3
"""Fail closed before a refresh can replace known-good production data."""

import argparse
import json
import math
from collections import Counter
from pathlib import Path

REGIONS = ("JAPAN", "CHINA", "KOREA", "GLOBAL")
MIN_ABSOLUTE_ROWS = 20
MIN_TOTAL_RETENTION = 0.50
MIN_REGION_ROWS = 3
MIN_REGION_RETENTION = 0.25


class ValidationError(RuntimeError):
    pass


def read_json_strict(path: Path, expected_type, label: str):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValidationError(f"{label} is unreadable or malformed: {path}: {exc}") from exc
    if not isinstance(value, expected_type):
        raise ValidationError(
            f"{label} has the wrong top-level type: expected {expected_type.__name__}, "
            f"got {type(value).__name__}"
        )
    return value


def validate_news(rows: list, label: str) -> Counter:
    if not rows:
        raise ValidationError(f"{label} contains no articles")

    counts = Counter()
    urls = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValidationError(f"{label}[{index}] is not an object")
        region = str(row.get("region") or "").upper()
        url = str(row.get("sourceUrl") or "").strip()
        if region not in REGIONS:
            raise ValidationError(f"{label}[{index}] has an invalid region: {region!r}")
        if not url.startswith(("http://", "https://")):
            raise ValidationError(f"{label}[{index}] has no valid sourceUrl")
        if url in urls:
            raise ValidationError(f"{label} contains a duplicate sourceUrl: {url}")
        urls.add(url)
        counts[region] += 1
    return counts


def validate_translations(payload: dict) -> None:
    if not isinstance(payload.get("items"), dict):
        raise ValidationError("translations.items must be an object")
    failures = payload.get("failures", {})
    if not isinstance(failures, dict):
        raise ValidationError("translations.failures must be an object when present")


def compare_with_baseline(baseline: list, current: list, baseline_counts: Counter, current_counts: Counter) -> None:
    if len(baseline) >= MIN_ABSOLUTE_ROWS:
        minimum = max(MIN_ABSOLUTE_ROWS, math.floor(len(baseline) * MIN_TOTAL_RETENTION))
        if len(current) < minimum:
            raise ValidationError(
                f"news row count collapsed from {len(baseline)} to {len(current)}; "
                f"minimum safe count is {minimum}"
            )

    for region in REGIONS:
        previous = baseline_counts.get(region, 0)
        if previous < MIN_REGION_ROWS:
            continue
        minimum = max(MIN_REGION_ROWS, math.floor(previous * MIN_REGION_RETENTION))
        actual = current_counts.get(region, 0)
        if actual < minimum:
            raise ValidationError(
                f"{region} rows collapsed from {previous} to {actual}; "
                f"minimum safe count is {minimum}"
            )


def validate(news_path: Path, translations_path: Path, baseline_path: Path | None = None) -> None:
    rows = read_json_strict(news_path, list, "news")
    translations = read_json_strict(translations_path, dict, "translations")
    current_counts = validate_news(rows, "news")
    validate_translations(translations)

    if baseline_path:
        baseline = read_json_strict(baseline_path, list, "baseline news")
        baseline_counts = validate_news(baseline, "baseline news")
        compare_with_baseline(baseline, rows, baseline_counts, current_counts)

    counts = " ".join(f"{region}={current_counts.get(region, 0)}" for region in REGIONS)
    print(f"pipeline data validation passed: rows={len(rows)} {counts}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Kirapara production JSON before commit.")
    parser.add_argument("--news", type=Path, required=True)
    parser.add_argument("--translations", type=Path, required=True)
    parser.add_argument("--baseline-news", type=Path)
    args = parser.parse_args()
    try:
        validate(args.news, args.translations, args.baseline_news)
    except ValidationError as exc:
        print(f"::error::{exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
