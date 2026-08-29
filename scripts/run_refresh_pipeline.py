#!/usr/bin/env python3
"""Run the news collectors with hard deadlines and last-known-good rollback.

``urllib`` timeouts limit individual socket operations, not the total lifetime
of a request. A server that accepts a connection and then trickles bytes can
therefore keep a collector alive for many minutes. This runner puts a hard
wall-clock deadline around each collector and restores the data snapshot when
an optional network step times out. A nonzero exit still fails the workflow so
code regressions are not mistaken for harmless upstream outages.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
STATE_PATHS = (
    Path("data/news.json"),
    Path("data/article_dates.json"),
    Path("data/image_quality.json"),
)


@dataclass(frozen=True)
class Step:
    label: str
    script: str
    timeout_seconds: float
    continue_on_timeout: bool = True


PIPELINE_STEPS = (
    Step("base public news", "fetch_news.py", 90),
    Step("official X history preservation", "preserve_official_x_history.py", 20, False),
    Step("known official pages", "merge_direct_official.py", 45),
    Step("source enrichment", "enrich_sources.py", 60),
    Step("X and Bilibili resilient repair", "repair_social_sources.py", 90),
    Step("social image enrichment", "enrich_social_images.py", 70),
    Step("Weibo native image enrichment", "enrich_weibo_images.py", 55),
    Step("Weibo CDN normalization", "normalize_weibo_cdn.py", 20, False),
    Step("Bilibili native image enrichment", "enrich_bilibili_images.py", 45),
    Step("TapTap official news", "fetch_taptap_official.py", 45),
    Step("Haoyoukuaibao official news", "fetch_haoyoukuaibao.py", 30),
    Step("WeChat official news", "fetch_wechat_official.py", 50),
    Step("duplicate source merge", "merge_duplicate_sources.py", 20, False),
    Step("public web discovery", "discover_web_news.py", 30),
    Step("generic image enrichment", "enrich_images.py", 30),
    Step("X image URL normalization", "upgrade_x_images.py", 20, False),
    Step("small image filter", "filter_small_images.py", 60),
    Step("final news normalization", "normalize_news.py", 60, False),
)


class StepFailed(RuntimeError):
    def __init__(self, step: Step, reason: str, returncode: int):
        super().__init__(f"{step.label}: {reason}")
        self.step = step
        self.returncode = returncode


def _annotation(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _snapshot(root: Path, backup_root: Path, state_paths: tuple[Path, ...]) -> set[Path]:
    existing: set[Path] = set()
    for relative in state_paths:
        target = root / relative
        if not target.exists():
            continue
        existing.add(relative)
        backup = backup_root / relative
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, backup)
    return existing


def _restore(
    root: Path,
    backup_root: Path,
    state_paths: tuple[Path, ...],
    existing: set[Path],
) -> None:
    for relative in state_paths:
        target = root / relative
        if relative not in existing:
            if target.exists():
                target.unlink()
            continue
        backup = backup_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        restore_path = target.with_name(f".{target.name}.refresh-restore")
        shutil.copy2(backup, restore_path)
        os.replace(restore_path, target)


def _stop_process_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
        process.wait(timeout=5)
        return
    except (ProcessLookupError, subprocess.TimeoutExpired):
        pass

    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except ProcessLookupError:
        return
    process.wait()


def run_step(
    step: Step,
    *,
    root: Path = ROOT,
    state_paths: tuple[Path, ...] = STATE_PATHS,
) -> bool:
    """Run one step, returning False only for a contained soft failure."""

    root = root.resolve()
    command = [sys.executable, "-u", str(root / "scripts" / step.script)]
    started = time.monotonic()
    print(f"\n=== {step.label} (hard limit: {step.timeout_seconds:g}s) ===", flush=True)

    with tempfile.TemporaryDirectory(prefix="kirapara-refresh-") as raw_backup:
        backup_root = Path(raw_backup)
        existing = _snapshot(root, backup_root, state_paths)
        process = subprocess.Popen(
            command,
            cwd=root,
            start_new_session=os.name == "posix",
        )
        try:
            returncode = process.wait(timeout=step.timeout_seconds)
        except subprocess.TimeoutExpired:
            _stop_process_tree(process)
            _restore(root, backup_root, state_paths, existing)
            reason = f"exceeded the {step.timeout_seconds:g}s hard limit; restored last-known-good state"
            print(f"::warning title={_annotation(step.label)}::{_annotation(reason)}", flush=True)
            if step.continue_on_timeout:
                return False
            raise StepFailed(step, reason, 124)
        except BaseException:
            _stop_process_tree(process)
            _restore(root, backup_root, state_paths, existing)
            raise

        elapsed = time.monotonic() - started
        if returncode == 0:
            print(f"=== {step.label} completed in {elapsed:.1f}s ===", flush=True)
            return True

        _restore(root, backup_root, state_paths, existing)
        reason = f"exited with code {returncode}; restored last-known-good state"
        raise StepFailed(step, reason, returncode)


def run_pipeline(steps: tuple[Step, ...] = PIPELINE_STEPS) -> list[str]:
    degraded: list[str] = []
    for step in steps:
        if not run_step(step):
            degraded.append(step.label)
    if degraded:
        print(
            "Refresh pipeline completed with cached fallbacks for: " + ", ".join(degraded),
            flush=True,
        )
    else:
        print("Refresh pipeline completed without fallback use", flush=True)
    return degraded


def main() -> int:
    try:
        run_pipeline()
    except StepFailed as exc:
        print(f"::error title={_annotation(exc.step.label)}::{_annotation(str(exc))}", flush=True)
        return exc.returncode or 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
