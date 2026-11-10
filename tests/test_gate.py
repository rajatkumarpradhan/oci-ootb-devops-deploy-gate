import unittest

from oci_ootb_devops_deploy_gate.gate import check_pipeline


def gated_stages():
    return [
        {"name": "build", "type": "custom"},
        {"name": "deploy-staging", "type": "deploy", "environment": "staging", "depends_on": ["build"]},
        {"name": "approval-prod", "type": "approval", "depends_on": ["deploy-staging"], "approver_groups": ["release-managers"]},
        {"name": "deploy-prod", "type": "deploy", "environment": "production", "depends_on": ["approval-prod"]},
        {"name": "rollback-prod", "type": "rollback", "depends_on": ["deploy-prod"]},
    ]


def ids(findings):
    return {f.rule_id for f in findings}


class TestGate(unittest.TestCase):
    def test_gated_pipeline_has_no_findings(self):
        self.assertEqual(check_pipeline({"stages": gated_stages()}), [])

    def test_gate001_ungated_production_deploy(self):
        stages = [s for s in gated_stages() if s["name"] != "approval-prod"]
        for s in stages:
            if s["name"] == "deploy-prod":
                s["depends_on"] = ["deploy-staging"]
        findings = check_pipeline({"stages": stages})
        gate001 = [f for f in findings if f.rule_id == "GATE001"]
        self.assertEqual(len(gate001), 1)
        self.assertEqual(gate001[0].severity, "HIGH")

    def test_gate001_transitive_dependency_counts(self):
        # approval -> wait -> deploy still counts as gated.
        stages = gated_stages()
        stages.append({"name": "hold", "type": "wait", "depends_on": ["approval-prod"]})
        for s in stages:
            if s["name"] == "deploy-prod":
                s["depends_on"] = ["hold"]
        self.assertNotIn("GATE001", ids(check_pipeline({"stages": stages})))

    def test_gate002_approval_without_approvers(self):
        stages = gated_stages()
        for s in stages:
            if s["name"] == "approval-prod":
                s["approver_groups"] = []
        self.assertIn("GATE002", ids(check_pipeline({"stages": stages})))

    def test_gate003_dangling_dependency(self):
        stages = gated_stages()
        stages[0]["depends_on"] = ["nope"]
        self.assertIn("GATE003", ids(check_pipeline({"stages": stages})))

    def test_gate003_duplicate_stage_name(self):
        stages = gated_stages()
        stages.append(dict(stages[0]))
        self.assertIn("GATE003", ids(check_pipeline({"stages": stages})))

    def test_gate004_no_rollback(self):
        stages = [s for s in gated_stages() if s["type"] != "rollback"]
        self.assertIn("GATE004", ids(check_pipeline({"stages": stages})))

    def test_gate004_not_flagged_without_production(self):
        stages = [{"name": "deploy-staging", "type": "deploy", "environment": "staging"}]
        self.assertNotIn("GATE004", ids(check_pipeline({"stages": stages})))

    def test_findings_sorted_high_first(self):
        stages = [s for s in gated_stages() if s["name"] not in ("approval-prod", "rollback-prod")]
        for s in stages:
            if s["name"] == "deploy-prod":
                s["depends_on"] = ["deploy-staging", "ghost"]
        findings = check_pipeline({"stages": stages})
        self.assertEqual(findings[0].severity, "HIGH")

    def test_missing_stages_list_rejected(self):
        with self.assertRaises(ValueError):
            check_pipeline({"items": []})

    def test_stage_missing_name_rejected(self):
        with self.assertRaises(ValueError):
            check_pipeline({"stages": [{"type": "deploy"}]})

    def test_stage_missing_type_rejected(self):
        with self.assertRaises(ValueError):
            check_pipeline({"stages": [{"name": "x"}]})


if __name__ == "__main__":
    unittest.main()
