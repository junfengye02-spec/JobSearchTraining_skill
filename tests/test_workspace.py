import json
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import workspace  # noqa: E402
from configuration import upgrade_config  # noqa: E402


class WorkspaceV2Tests(unittest.TestCase):
    def test_v1_defaults_upgrade_without_overwriting_custom_limits(self):
        upgraded = upgrade_config({
            "schema_version": 1,
            "profile": {"roles": ["后端开发"]},
            "discovery": {
                "initial_max_candidates_per_source": 50,
                "daily_max_candidates_per_source": 75,
                "initial_max_result_pages_per_query": 5,
            },
            "files": {},
        })
        self.assertEqual(2, upgraded["schema_version"])
        self.assertEqual(120, upgraded["discovery"]["initial_max_candidates_per_source"])
        self.assertEqual(75, upgraded["discovery"]["daily_max_candidates_per_source"])
        self.assertEqual(8, upgraded["discovery"]["initial_max_result_pages_per_query"])
        self.assertIn("pending_job_leads", upgraded["files"])

    def test_init_creates_v2_discovery_state_and_watchlist(self):
        with tempfile.TemporaryDirectory() as temp:
            args = workspace.parser().parse_args([
                "init",
                "--workspace", temp,
                "--grad-year", "2027",
                "--season", "秋招",
                "--role", "产品经理",
                "--role-alias", "产品经理=AI产品经理",
                "--watch-company", "字节跳动",
                "--include-high-growth-companies",
            ])
            with redirect_stdout(io.StringIO()):
                self.assertEqual(0, args.func(args))
            runtime = Path(temp) / workspace.RUNTIME_DIR
            config = json.loads((runtime / "config.json").read_text(encoding="utf-8"))
            self.assertEqual(2, config["schema_version"])
            self.assertEqual(["字节跳动"], config["profile"]["watch_companies"])
            self.assertTrue(config["profile"]["include_high_growth_companies"])
            self.assertEqual(120, config["discovery"]["initial_max_candidates_per_source"])
            self.assertTrue((runtime / "state" / "pending-job-leads.json").exists())
            self.assertTrue((runtime / "state" / "company-audit.json").exists())


if __name__ == "__main__":
    unittest.main()
