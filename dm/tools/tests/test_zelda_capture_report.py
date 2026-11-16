"""Sanitized offline capture summaries; no game, GPU or personal logs required."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[3] / 'scripts/zelda_capture_report.py'
spec = importlib.util.spec_from_file_location('capture_report', SCRIPT)
assert spec and spec.loader
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


class CaptureReport(unittest.TestCase):
    def test_delayed_rows_counts_and_percentiles(self):
        lines = ['1\t@t_s\t0', '2\t@t_s\t1', '3\t@t_s\t2',
                 '3\t@frame_ms\t40', '1\t@frame_ms\t20', '2\t@frame_ms\t30',
                 '1\t@gpu_ms\t0', '2\t@presented_ms\t-1']
        result = report.summarize(lines)
        self.assertEqual(result['metrics']['frame_ms']['p50'], 30)
        self.assertEqual(result['metrics']['frame_ms']['p95'], 40)
        self.assertEqual(result['metrics']['gpu_ms']['samples'], 1)
        self.assertEqual(result['over_budget_frames'], 1)
        self.assertEqual(result['dropped_presentations'], 1)
        self.assertEqual(result['observed_frame_rate'], 1)
        self.assertIsNone(result['metrics']['submit_ms']['p50'])

    def test_no_false_duration_or_rate_for_missing_frames(self):
        result = report.summarize(['1\t@t_s\t0', '4\t@t_s\t1200'])
        self.assertTrue(result['duration_gate_1200s_met'])
        self.assertIsNone(result['observed_frame_rate'])
        self.assertIn('visual correctness', result['unmeasured'])
        result = report.summarize(['1\t@t_s\t0'])
        self.assertFalse(result['duration_gate_1200s_met'])
        self.assertIsNone(result['observed_frame_rate'])

    def test_invalid_values_and_nonmonotonic_capture(self):
        for lines in ([], ['1\t@t_s\tnan'], ['1\t@t_s\t1', '2\t@t_s\t0'],
                      ['1\t@t_s\t0', '1\t@t_s\t1']):
            with self.subTest(lines=lines), self.assertRaises(ValueError):
                report.summarize(lines)
        result = report.summarize(['1\t@t_s\t0', '1\t@gpu_ms\tinf'])
        self.assertEqual(result['invalid_numeric_rows'], 1)
        for budget in (0, -1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                report.summarize(['1\t@t_s\t0'], budget)

    def test_cli_emits_no_private_fields_or_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'private-owner.tsv'
            source = 'private log /Users/PRIVATE/game\n1\t@t_s\t0\n1\t@PRIVATE_NAME\t42\n'
            path.write_text(source)
            result = subprocess.run([sys.executable, str(SCRIPT), str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('PRIVATE', result.stdout)
            self.assertNotIn(tmp, result.stdout)
            json.loads(result.stdout)
            self.assertEqual(path.read_text(), source)
            path.unlink()
            result = subprocess.run([sys.executable, str(SCRIPT), str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn(tmp, result.stderr)

    def test_argument_errors_never_echo_rejected_text(self):
        for args in (['PRIVATE-path', '--unknown-PRIVATE'],
                     ['PRIVATE-path', '--budget-ms', 'PRIVATE-value'], [],
                     ['PRIVATE-path', 'PRIVATE-extra']):
            with self.subTest(args=args):
                result = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
                self.assertNotIn('PRIVATE', result.stderr + result.stdout)
                self.assertNotIn('Traceback', result.stderr)
        result = subprocess.run([sys.executable, str(SCRIPT), '--help'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn('--budget-ms', result.stdout)

    def test_finite_timestamps_cannot_emit_infinite_rate_or_traceback(self):
        source = '1\t@t_s\t0\n2\t@t_s\t1e-320\n'
        with self.assertRaises(ValueError):
            report.summarize(source.splitlines())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'PRIVATE.tsv'
            path.write_text(source)
            result = subprocess.run([sys.executable, str(SCRIPT), str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, '')
            self.assertNotIn('PRIVATE', result.stderr)
            self.assertNotIn('Traceback', result.stderr)


if __name__ == '__main__':
    unittest.main()
