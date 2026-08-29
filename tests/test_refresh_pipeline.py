import importlib
import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
runner = importlib.import_module("run_refresh_pipeline")


class RefreshPipelineTests(unittest.TestCase):
    def make_root(self, source: str):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        (root / "scripts").mkdir()
        (root / "data").mkdir()
        (root / "scripts" / "step.py").write_text(textwrap.dedent(source), encoding="utf-8")
        (root / "data" / "news.json").write_text(
            json.dumps([{"title": "last known good"}]),
            encoding="utf-8",
        )
        return temporary, root

    def test_timeout_restores_last_known_good_and_soft_fails(self):
        temporary, root = self.make_root(
            """
            from pathlib import Path
            import time
            Path('data/news.json').write_text('[{"title":"partial"}]', encoding='utf-8')
            time.sleep(10)
            """
        )
        self.addCleanup(temporary.cleanup)
        step = runner.Step("slow optional source", "step.py", 0.2, True)

        completed = runner.run_step(
            step,
            root=root,
            state_paths=(Path("data/news.json"),),
        )

        self.assertFalse(completed)
        rows = json.loads((root / "data" / "news.json").read_text(encoding="utf-8"))
        self.assertEqual("last known good", rows[0]["title"])

    def test_nonzero_exit_restores_state_and_is_not_hidden(self):
        temporary, root = self.make_root(
            """
            from pathlib import Path
            Path('data/news.json').write_text('[{"title":"broken"}]', encoding='utf-8')
            raise SystemExit(7)
            """
        )
        self.addCleanup(temporary.cleanup)
        step = runner.Step("broken collector", "step.py", 5, True)

        with self.assertRaises(runner.StepFailed) as raised:
            runner.run_step(
                step,
                root=root,
                state_paths=(Path("data/news.json"),),
            )

        self.assertEqual(7, raised.exception.returncode)
        rows = json.loads((root / "data" / "news.json").read_text(encoding="utf-8"))
        self.assertEqual("last known good", rows[0]["title"])

    def test_successful_step_keeps_new_state(self):
        temporary, root = self.make_root(
            """
            from pathlib import Path
            Path('data/news.json').write_text('[{"title":"fresh"}]', encoding='utf-8')
            """
        )
        self.addCleanup(temporary.cleanup)
        step = runner.Step("healthy source", "step.py", 5, True)

        completed = runner.run_step(
            step,
            root=root,
            state_paths=(Path("data/news.json"),),
        )

        self.assertTrue(completed)
        rows = json.loads((root / "data" / "news.json").read_text(encoding="utf-8"))
        self.assertEqual("fresh", rows[0]["title"])

    def test_critical_failure_is_not_hidden(self):
        temporary, root = self.make_root("raise SystemExit(9)\n")
        self.addCleanup(temporary.cleanup)
        step = runner.Step("critical normalization", "step.py", 5, False)

        with self.assertRaises(runner.StepFailed) as raised:
            runner.run_step(
                step,
                root=root,
                state_paths=(Path("data/news.json"),),
            )

        self.assertEqual(9, raised.exception.returncode)


if __name__ == "__main__":
    unittest.main()
