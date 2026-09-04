import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import discovery  # noqa: E402


class DiscoveryV2Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        runtime = self.workspace / discovery.RUNTIME_DIR
        (runtime / "state").mkdir(parents=True)
        self.config = {
            "schema_version": 2,
            "profile": {
                "target_grad_year": "2027",
                "target_season_label": "秋招",
                "roles": ["产品经理"],
                "role_aliases": {"产品经理": ["AI产品经理", "产品实习生"]},
                "watch_companies": ["字节跳动"],
                "include_internships": True,
            },
            "discovery": {
                "max_role_aliases": 8,
                "initial_max_candidates_per_source": 120,
                "daily_max_candidates_per_source": 40,
                "initial_max_result_pages_per_query": 8,
                "daily_max_result_pages_per_query": 3,
                "stop_after_consecutive_no_new_pages": 2,
                "initial_max_new_company_verifications": 120,
                "daily_max_new_company_verifications": 20,
                "initial_low_yield_threshold": 20,
                "history_retention_runs": 30,
            },
            "files": {
                "discovery_history": f"{discovery.RUNTIME_DIR}/state/discovery-runs.json",
                "pending_job_leads": f"{discovery.RUNTIME_DIR}/state/pending-job-leads.json",
                "company_audit": f"{discovery.RUNTIME_DIR}/state/company-audit.json",
            },
        }
        (runtime / "config.json").write_text(
            json.dumps(self.config, ensure_ascii=False), encoding="utf-8"
        )
        (runtime / "state" / "discovery-runs.json").write_text(
            json.dumps({"schema_version": 2, "runs": []}), encoding="utf-8"
        )

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def audit(company):
        return {
            "company": company,
            "status": "no_match",
            "official_search_attempted": True,
            "queries": [f"{company} 校招 官网"],
            "pages_checked": [f"https://example.com/search?q={company}"],
            "checked_at": "2026-09-04T08:00:00+08:00",
        }

    def complete_report(self, plan, candidates_by_source=None):
        candidates_by_source = candidates_by_source or {}
        sources = []
        for group in plan["source_groups"]:
            candidates = candidates_by_source.get(group["id"], [])
            companies = list(dict.fromkeys(
                [*group.get("required_watch_companies", [])]
                + [candidate["company"] for candidate in candidates]
            ))
            role_coverage = []
            for task in group["role_tasks"]:
                role_coverage.append({
                    "role": task["role"],
                    "status": "empty" if not candidates else "success",
                    "query_runs": [
                        {
                            "query": query,
                            "status": "empty" if not candidates else "success",
                            "pages_checked": ["https://example.com/results?page=1"],
                            "exhausted": True,
                            "stop_reason": "end",
                        }
                        for query in task["queries"]
                    ],
                })
            sources.append({
                "id": group["id"],
                "status": "empty" if not candidates else "success",
                "role_coverage": role_coverage,
                "entry_runs": [
                    {
                        "url": url,
                        "status": "empty" if not candidates else "success",
                        "checked_at": "2026-09-04T08:00:00+08:00",
                        "evidence": "entry opened and inspected",
                    }
                    for url in group["entry_urls"]
                ],
                "enumeration_complete": group["id"] == "nowcoder",
                "enumerated_companies": companies if group["id"] == "nowcoder" else [],
                "company_audits": [self.audit(company) for company in companies],
                "candidates": candidates,
            })
        return {"mode": plan["mode"], "sources": sources}

    def test_plan_uses_direct_nowcoder_surfaces_and_all_aliases(self):
        plan = discovery.query_plan(self.config)
        nowcoder = next(item for item in plan["source_groups"] if item["id"] == "nowcoder")
        urls = nowcoder["entry_urls"]
        self.assertIn(
            "https://www.nowcoder.com/jobs/school/schedule?pageSource=5001", urls
        )
        self.assertIn("https://www.nowcoder.com/jobs/recommend/campus", urls)
        self.assertIsNone(nowcoder["max_new_company_verifications"])
        self.assertEqual(
            ["产品经理", "AI产品经理", "产品实习生"],
            nowcoder["role_tasks"][0]["search_terms"],
        )

    def test_existing_v1_workspace_uses_v2_effective_limits(self):
        old = json.loads(json.dumps(self.config))
        old["schema_version"] = 1
        old["discovery"].update({
            "initial_max_candidates_per_source": 50,
            "initial_max_result_pages_per_query": 5,
        })
        config_path = self.workspace / discovery.RUNTIME_DIR / "config.json"
        config_path.write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")
        upgraded = discovery.load_config(self.workspace)
        plan = discovery.query_plan(upgraded)
        nowcoder = next(item for item in plan["source_groups"] if item["id"] == "nowcoder")
        self.assertEqual(120, nowcoder["max_candidates"])
        self.assertEqual(8, nowcoder["max_result_pages_per_query"])

    def test_v1_completion_history_is_revalidated_by_initial_full(self):
        history_path = (
            self.workspace / discovery.RUNTIME_DIR / "state" / "discovery-runs.json"
        )
        history_path.write_text(json.dumps({
            "schema_version": 1,
            "runs": [{
                "schema_version": 1,
                "mode": "initial_full",
                "full_search_complete": True,
            }],
        }), encoding="utf-8")
        self.assertEqual("initial_full", discovery.resolve_mode(self.workspace, self.config))

    def test_legacy_aggregate_evidence_cannot_complete_search(self):
        plan = discovery.query_plan(self.config)
        legacy_sources = []
        for group in plan["source_groups"]:
            legacy_sources.append({
                "id": group["id"],
                "status": "empty",
                "role_coverage": [{
                    "role": "产品经理",
                    "status": "empty",
                    "queries": group["queries"],
                    "pages_checked": ["https://example.com/one-page"],
                    "exhausted": True,
                    "stop_reason": "end",
                }],
                "candidates": [],
            })
        status, _, _ = discovery.finalize_report(
            self.workspace, {"mode": "initial_full", "sources": legacy_sources}
        )
        self.assertFalse(status["coverage_complete"])
        self.assertFalse(status["full_search_complete"])
        self.assertFalse(status["can_report_no_jobs"])
        self.assertNotEqual("searched_no_jobs", status["conclusion"])
        self.assertEqual("initial_full", discovery.resolve_mode(self.workspace, self.config))

    def test_page_limit_requires_the_configured_number_of_pages(self):
        plan = discovery.query_plan(self.config)
        report = self.complete_report(plan)
        for source in report["sources"]:
            for role in source["role_coverage"]:
                for run in role["query_runs"]:
                    run["stop_reason"] = "page_limit"
        status, _, _ = discovery.finalize_report(self.workspace, report)
        self.assertFalse(status["source_coverage_complete"])
        self.assertFalse(status["full_search_complete"])

    def test_entry_and_company_timestamps_must_be_valid_iso(self):
        plan = discovery.query_plan(self.config)
        report = self.complete_report(plan)
        nowcoder = next(item for item in report["sources"] if item["id"] == "nowcoder")
        nowcoder["entry_runs"][0]["checked_at"] = "not-a-time"
        official = next(item for item in report["sources"] if item["id"] == "official")
        official["company_audits"][0]["checked_at"] = "not-a-time"
        status, _, _ = discovery.finalize_report(self.workspace, report)
        self.assertFalse(status["source_coverage_complete"])
        self.assertEqual(1, status["pending_company_audit_count"])

    def test_complete_per_query_entry_and_company_evidence_can_finish(self):
        plan = discovery.query_plan(self.config)
        status, ready, leads = discovery.finalize_report(
            self.workspace, self.complete_report(plan)
        )
        self.assertEqual([], ready)
        self.assertEqual([], leads)
        self.assertTrue(status["coverage_complete"])
        self.assertTrue(status["full_search_complete"])
        self.assertTrue(status["can_report_no_jobs"])
        self.assertEqual("searched_no_jobs", status["conclusion"])
        self.assertEqual("daily_refresh", discovery.resolve_mode(self.workspace, self.config))

    def test_incomplete_lead_persists_and_blocks_full_completion(self):
        plan = discovery.query_plan(self.config)
        lead = {
            "company": "示例科技",
            "title": "AI产品经理",
            "responsibilities": "",
            "source_url": "https://example.com/job/1",
            "matched_roles": ["产品经理"],
            "application_status": "open",
            "availability_evidence": "Apply button visible",
            "checked_at": "2026-09-04T08:00:00+08:00",
        }
        report = self.complete_report(plan, {"nowcoder": [lead]})
        status, ready, leads = discovery.finalize_report(self.workspace, report)
        self.assertEqual([], ready)
        self.assertEqual(1, len(leads))
        self.assertEqual(1, status["pending_lead_count"])
        self.assertFalse(status["coverage_complete"])
        self.assertFalse(status["full_search_complete"])
        retry_plan = discovery.query_plan(
            self.config,
            discovery.resolve_mode(self.workspace, self.config),
            discovery.load_pending_leads(self.workspace, self.config),
            discovery.load_pending_company_audits(self.workspace, self.config),
        )
        self.assertEqual("initial_full", retry_plan["mode"])
        self.assertEqual(1, len(retry_plan["retry_queue"]["pending_leads"]))

    def test_deferred_company_audit_is_retried_by_official_search(self):
        plan = discovery.query_plan(self.config)
        report = self.complete_report(plan)
        official = next(item for item in report["sources"] if item["id"] == "official")
        official["company_audits"] = [{
            "company": "字节跳动",
            "status": "deferred",
            "official_search_attempted": False,
            "queries": [],
            "pages_checked": [],
            "checked_at": "2026-09-04T08:00:00+08:00",
            "error": "rate limited",
        }]
        status, _, _ = discovery.finalize_report(self.workspace, report)
        self.assertEqual(1, status["pending_company_audit_count"])
        self.assertFalse(status["full_search_complete"])
        retry_audits = discovery.load_pending_company_audits(self.workspace, self.config)
        retry_plan = discovery.query_plan(self.config, "initial_full", [], retry_audits)
        self.assertEqual("字节跳动", retry_plan["retry_queue"]["pending_company_audits"][0]["company"])
        official_plan = next(
            item for item in retry_plan["source_groups"] if item["id"] == "official"
        )
        self.assertIn("字节跳动", official_plan["required_watch_companies"])
        self.assertTrue(any("字节跳动" in query for query in official_plan["queries"]))

    def test_incomplete_verified_audit_cannot_fall_out_of_retry_queue(self):
        plan = discovery.query_plan(self.config)
        report = self.complete_report(plan)
        official = next(item for item in report["sources"] if item["id"] == "official")
        official["company_audits"][0] = {
            "company": "字节跳动",
            "status": "verified",
            "official_search_attempted": True,
            "queries": [],
            "pages_checked": [],
            "checked_at": "",
        }
        status, _, _ = discovery.finalize_report(self.workspace, report)
        self.assertEqual(1, status["pending_company_audit_count"])
        pending = discovery.load_pending_company_audits(self.workspace, self.config)
        self.assertEqual(["字节跳动"], [item["company"] for item in pending])

    def test_lead_resolution_requires_evidence_and_does_not_readd_current_lead(self):
        plan = discovery.query_plan(self.config)
        lead = {
            "company": "示例科技",
            "title": "AI产品经理",
            "responsibilities": "",
            "source_url": "https://example.com/job/resolve",
            "matched_roles": ["产品经理"],
            "application_status": "open",
            "availability_evidence": "Apply button visible",
            "checked_at": "2026-09-04T08:00:00+08:00",
        }
        first = self.complete_report(plan, {"nowcoder": [lead]})
        first_status, _, _ = discovery.finalize_report(self.workspace, first)
        self.assertEqual(1, first_status["pending_lead_count"])
        key = discovery.candidate_key(lead)

        bare = self.complete_report(plan)
        bare["resolved_lead_keys"] = [key]
        bare_status, _, _ = discovery.finalize_report(self.workspace, bare)
        self.assertEqual(1, bare_status["pending_lead_count"])

        closed_lead = lead.copy()
        closed_lead["application_status"] = "closed"
        closed_lead["availability_evidence"] = "Official page says applications closed"
        resolved = self.complete_report(plan, {"nowcoder": [closed_lead]})
        resolved["lead_resolutions"] = [{
            "lead_key": key,
            "resolution": "closed",
            "evidence": "Official page says applications closed",
            "checked_at": "2026-09-04T09:00:00+08:00",
        }]
        resolved_status, _, _ = discovery.finalize_report(self.workspace, resolved)
        self.assertEqual(0, resolved_status["pending_lead_count"])

        resurfaced = self.complete_report(plan, {"nowcoder": [closed_lead]})
        resurfaced_status, _, _ = discovery.finalize_report(self.workspace, resurfaced)
        self.assertEqual(0, resurfaced_status["pending_lead_count"])


if __name__ == "__main__":
    unittest.main()
