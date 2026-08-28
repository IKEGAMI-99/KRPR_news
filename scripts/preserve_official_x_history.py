#!/usr/bin/env python3
import json
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEWS_PATH = ROOT / "data" / "news.json"
RETENTION_DAYS = 21
MAX_PER_ACCOUNT = 12
MAX_HISTORY_COMMITS = 40

OFFICIAL_X_ACCOUNTS = {
    "JAPAN": "kirapara_jp",
    "GLOBAL": "lifemakeover510",
    "KOREA": "stylight_kr",
}


def read_rows(path: Path) -> list[dict]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return value if isinstance(value, list) else []


def account_key(row: dict) -> str | None:
    url = str(row.get("sourceUrl") or "").lower()
    region = str(row.get("region") or "").upper()
    for expected_region, handle in OFFICIAL_X_ACCOUNTS.items():
        if region == expected_region and (
            f"x.com/{handle}/status/" in url
            or f"twitter.com/{handle}/status/" in url
        ):
            return expected_region
    return None


def recent_enough(row: dict, now: int) -> bool:
    try:
        epoch = int(row.get("publishedAtEpoch") or 0)
    except (TypeError, ValueError):
        return False
    return epoch > 0 and epoch >= now - RETENTION_DAYS * 86400


def git_news_commits() -> list[str]:
    try:
        result = subprocess.run(
            ["git", "log", f"--max-count={MAX_HISTORY_COMMITS}", "--format=%H", "--", "data/news.json"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception as exc:
        print(f"official X history: git log unavailable: {exc}")
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def rows_from_commit(commit: str) -> list[dict]:
    try:
        result = subprocess.run(
            ["git", "show", f"{commit}:data/news.json"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        value = json.loads(result.stdout)
    except Exception:
        return []
    return value if isinstance(value, list) else []


def collect_history(now: int) -> list[dict]:
    recovered: dict[str, dict] = {}
    counts = {region: 0 for region in OFFICIAL_X_ACCOUNTS}

    for commit in git_news_commits():
        if all(count >= MAX_PER_ACCOUNT for count in counts.values()):
            break
        for row in rows_from_commit(commit):
            if not isinstance(row, dict) or not recent_enough(row, now):
                continue
            region = account_key(row)
            if not region or counts[region] >= MAX_PER_ACCOUNT:
                continue
            url = str(row.get("sourceUrl") or "")
            if not url or url in recovered:
                continue
            recovered[url] = row
            counts[region] += 1

    return list(recovered.values())


def merge_rows(current: list[dict], history: list[dict], now: int) -> tuple[list[dict], dict[str, int]]:
    merged = {
        str(row.get("sourceUrl")): row
        for row in current
        if isinstance(row, dict) and row.get("sourceUrl")
    }
    restored = {region: 0 for region in OFFICIAL_X_ACCOUNTS}

    current_counts = {region: 0 for region in OFFICIAL_X_ACCOUNTS}
    for row in current:
        region = account_key(row) if isinstance(row, dict) else None
        if region and recent_enough(row, now):
            current_counts[region] += 1

    # Prefer fresh rows already in news.json. History only fills missing URLs and
    # never expands an account beyond the collector's normal 12-item window.
    history_sorted = sorted(
        history,
        key=lambda row: int(row.get("publishedAtEpoch") or 0),
        reverse=True,
    )
    for row in history_sorted:
        if not isinstance(row, dict) or not recent_enough(row, now):
            continue
        region = account_key(row)
        if not region or current_counts[region] >= MAX_PER_ACCOUNT:
            continue
        url = str(row.get("sourceUrl") or "")
        if not url or url in merged:
            continue
        merged[url] = row
        current_counts[region] += 1
        restored[region] += 1

    rows = sorted(
        merged.values(),
        key=lambda row: int(row.get("publishedAtEpoch") or 0),
        reverse=True,
    )
    return rows, restored


def main():
    current = read_rows(NEWS_PATH)
    now = int(time.time())
    history = collect_history(now)
    rows, restored = merge_rows(current, history, now)

    if rows != current:
        NEWS_PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("official X outage protection:")
    for region in OFFICIAL_X_ACCOUNTS:
        print(f"  {region}: restored {restored[region]} historical rows")
    print(f"  total rows: {len(rows)}")


if __name__ == "__main__":
    main()
