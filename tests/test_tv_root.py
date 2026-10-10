import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "reorganize_tv_for_jellyfin.py"


class TVRootTests(unittest.TestCase):
    def run_script(self, root, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            env={**os.environ, "TV_ROOT": str(root)},
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    def test_environment_root_and_dry_run(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "Example.S01"
            source.mkdir()
            output = self.run_script(root)
            self.assertIn(f"Root: {root}", output)
            self.assertIn("Example/Season 01/", output)
            self.assertTrue(source.exists())
            self.assertFalse((Path(root) / "Example").exists())

    def test_cli_overrides_environment(self):
        with tempfile.TemporaryDirectory() as root:
            output = self.run_script("/nonexistent/environment/root", "--root", root)
            self.assertIn(f"Root: {root}", output)

    def test_empty_environment_keeps_default_root(self):
        result = subprocess.run(
            [sys.executable, "-c",
             "import runpy,sys; print(runpy.run_path(sys.argv[1])['ROOT'])",
             str(SCRIPT)],
            env={**os.environ, "TV_ROOT": ""},
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.stdout.strip(), "/mnt/files1/data/shared/tv")

    def test_environment_expands_home(self):
        with tempfile.TemporaryDirectory() as home:
            result = subprocess.run(
                [sys.executable, str(SCRIPT)],
                env={**os.environ, "TV_ROOT": "~", "HOME": home},
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn(f"Root: {home}", result.stdout)


if __name__ == "__main__":
    unittest.main()
