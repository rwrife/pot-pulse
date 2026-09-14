"""Synthetic report fixtures test the gate, not the physical board."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "check_drc.py"


class DrcGateTests(unittest.TestCase):
    def run_gate(self, data):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "drc.json"
            report.write_text(json.dumps(data), encoding="utf-8")
            return subprocess.run([sys.executable, str(SCRIPT), str(report)],
                                  text=True, capture_output=True)

    def test_unconnected_items_block_without_geometry_errors(self):
        result = self.run_gate({
            "$schema": "https://schemas.kicad.org/drc.v1.json",
            "included_severities": ["error", "warning", "exclusion"],
            "source": "pot-pulse.kicad_pcb", "kicad_version": "9.0.9",
            "violations": [], "unconnected_items": [{"severity": "error"}] * 5,
            "schematic_parity": [],
        })
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("BLOCKED: violations=0 unconnected_items=5 schematic_parity=0", result.stdout)


if __name__ == "__main__":
    unittest.main()
