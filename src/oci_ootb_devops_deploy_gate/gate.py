"""Approval-gate checks for OCI DevOps deploy pipelines.

OCI DevOps is the built-in OCI build/deploy service; the standard safety
posture is that a production deploy stage is never reached without a manual
approval stage, and that a failed production deploy has a rollback path.
This module works on a static JSON description of a pipeline's stages:
each stage has a name, a type (deploy / approval / wait / rollback /
custom), an environment (staging / production / ...), and optional
depends_on stage names. All analysis is offline; no OCI calls.
"""

from dataclasses import dataclass

SEVERITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}

PRODUCTION = "production"


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str
    subject: str
    message: str


def _stages(document):
    stages = document.get("stages")
    if not isinstance(stages, list):
        raise ValueError("document must contain a top-level 'stages' list")
    for stage in stages:
        if not isinstance(stage, dict):
            raise ValueError("each stage entry must be an object")
        for field in ("name", "type"):
            if not stage.get(field):
                raise ValueError(f"stage entry missing {field!r}: {stage}")
    return stages


def _upstream_approvals(stage, by_name):
    """Approval stages reachable by walking depends_on backwards."""
    seen, stack = set(), [stage["name"]]
    while stack:
        name = stack.pop()
        if name not in by_name:
            continue  # dangling dependency; reported as GATE003 elsewhere
        current = by_name[name]
        if current["name"] in seen:
            continue
        seen.add(current["name"])
        if current["type"] == "approval" and current["name"] != stage["name"]:
            return current
        stack.extend(current.get("depends_on") or [])
    return None


def check_pipeline(document):
    stages = _stages(document)
    findings = []
    by_name = {}
    for stage in stages:
        if stage["name"] in by_name:
            findings.append(Finding("GATE003", "MEDIUM", stage["name"], "duplicate stage name"))
        by_name.setdefault(stage["name"], stage)

    # GATE003: dangling dependencies.
    for stage in stages:
        for dep in stage.get("depends_on") or []:
            if dep not in by_name:
                findings.append(Finding("GATE003", "MEDIUM", stage["name"],
                                        f"depends on unknown stage {dep!r}"))

    prod_deploys = [s for s in stages if s["type"] == "deploy" and s.get("environment") == PRODUCTION]
    rollback_present = any(s["type"] == "rollback" for s in stages)

    for stage in prod_deploys:
        gate = _upstream_approvals(stage, by_name)
        if gate is None:
            findings.append(Finding("GATE001", "HIGH", stage["name"],
                                    "production deploy is reachable without a manual approval stage"))

    # GATE002: an approval stage with nobody to approve blocks or rubber-stamps.
    for stage in stages:
        if stage["type"] == "approval" and not stage.get("approver_groups"):
            findings.append(Finding("GATE002", "MEDIUM", stage["name"],
                                    "approval stage lists no approver groups"))

    # GATE004: production deploy with no rollback stage anywhere.
    if prod_deploys and not rollback_present:
        findings.append(Finding("GATE004", "LOW", PRODUCTION,
                                "no rollback stage defined; a failed production deploy has no scripted path back"))

    return sorted(findings, key=lambda f: (SEVERITY_ORDER[f.severity], f.rule_id, f.subject, f.message))
