# oci-ootb-devops-deploy-gate

**Built-in services project (OOTB): OCI DevOps + OCI Notifications**, with a custom offline checker on top. The standard safety posture for OCI DevOps deploy pipelines is that production is never reached without a manual approval stage, the approval has real approvers, and a failed production deploy has a rollback path. This repo ships the Terraform template for that wiring plus a checker that verifies a pipeline's stage graph actually enforces it.

## What is custom code vs native service configuration

- **Native (OCI built-in features):** the DevOps project, environments, deploy pipeline, MANUAL_APPROVAL stage, and ONS notification wiring in `infra/main.tf`. That is configuration of OCI's own services, via Terraform.
- **Custom:** the Python checker in `src/` that reads a static JSON description of pipeline stages and answers "is production actually gated?" by walking `depends_on` backwards from every production deploy stage.
- **What ran:** the checker and its 16 unit tests executed locally and in CI (Python 3.10/3.11/3.12), plus the seeded demo below.
- **What is template-only:** the Terraform in `infra/` has NOT been plan/apply validated against a tenancy. It is a structural template only; validate against the current OCI provider docs before any real apply. Nothing here talks to a live tenancy.

## What it is NOT (more honest limits)

- The checker works on a static JSON stage list. It does not call the OCI API to read live pipelines, and it does not model run-time stage results, triggers, or parameters - only the declared dependency graph.
- "Approval reaches production" is checked transitively through `depends_on`; exotic pipeline shapes (fan-out that bypasses the gate elsewhere) are out of scope.

## Rules

| Rule | Severity | Finding |
| --- | --- | --- |
| GATE001 | HIGH | Production deploy stage reachable without a manual approval stage upstream |
| GATE002 | MEDIUM | Approval stage lists no approver groups |
| GATE003 | MEDIUM | Duplicate stage name, or dependency on an unknown stage |
| GATE004 | LOW | Production deploys exist but no rollback stage is defined |

Exit code 2 when any GATE001 fires; 1 on unreadable or malformed input; 0 otherwise.

## Run the local checker

Requires Python 3.10+, no third-party dependencies.

```sh
PYTHONPATH=src python3 -m oci_ootb_devops_deploy_gate samples/ungated-pipeline.json
PYTHONPATH=src python3 -m oci_ootb_devops_deploy_gate samples/gated-pipeline.json
```

Or the end-to-end demo:

```sh
sh demo.sh
```

Expected demo output: the ungated pipeline flags the ungated production deploy (HIGH), the approver-less approval stage, the dangling dependency and the missing rollback, and exits 2; the gated pipeline reports zero findings and exits 0.

## Terraform wiring (template)

```sh
cd infra
cp terraform.tfvars.example terraform.tfvars   # fill in the compartment + topic OCIDs
terraform init && terraform plan
```

This is a template - do NOT apply without reviewing against the current OCI provider docs. It was not validated against a live tenancy.

## Test

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```
