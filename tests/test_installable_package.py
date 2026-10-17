"""Deterministic package-copy tests, not Agent installation or host discovery."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'skill' / 'human-rlaif'


class InstallablePackageTests(unittest.TestCase):
    def test_complete_portable_copy_runs_cli_without_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            installed = base / 'synthetic-skills' / 'human-rlaif'
            shutil.copytree(PACKAGE, installed, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            self.assertEqual({p.name for p in installed.iterdir()},
                             {'SKILL.md', 'LICENSE', 'references', 'assets', 'scripts'})
            self.assertEqual((installed / 'LICENSE').read_bytes(), (ROOT / 'LICENSE').read_bytes())
            private = base / 'private'
            script = installed / 'scripts' / 'workspace.py'

            def cli(command, *arguments):
                result = subprocess.run([sys.executable, str(script), command,
                                         '--workspace', str(private), *arguments],
                                        cwd=base, capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                return json.loads(result.stdout)

            self.assertTrue(cli('init')['created'])
            self.assertTrue(cli('doctor')['ok'])
            cli('record', '--event', str(installed / 'assets' / 'event.v1.example.json'))
            self.assertEqual(cli('due')['count'], 0)
            self.assertEqual(cli('calibration')['scored_count'], 0)
            output = base / 'redacted.json'
            cli('export', '--output', str(output))
            exported = json.loads(output.read_text())
            self.assertEqual(len(exported['events']), 1)
            self.assertNotIn('human_input', exported['events'][0])
            self.assertFalse((installed / 'paper').exists())
            self.assertFalse((installed / 'tests').exists())
            self.assertFalse((installed / '.github').exists())


if __name__ == '__main__':
    unittest.main()
