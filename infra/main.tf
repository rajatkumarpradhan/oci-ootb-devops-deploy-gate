# OCI DevOps deploy pipeline with a manual approval gate (template; NOT applied).
#
# OCI DevOps is the built-in OCI build/deploy service; the standard safety
# posture is a manual approval stage between staging and production deploys,
# plus a rollback path. The local checker in src/ verifies a pipeline's stage
# graph actually enforces that posture.
#
# This file has NOT been plan/apply validated against a tenancy - it is a
# structural template. Review against the current provider docs before any
# real apply.

terraform {
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = ">= 5.0.0"
    }
  }
}

variable "compartment_ocid" {
  type        = string
  description = "OCID of the compartment that owns the DevOps project"
}

variable "project_notification_topic_ocid" {
  type        = string
  description = "OCID of the ONS topic the DevOps project notifies"
}

resource "oci_devops_project" "app" {
  compartment_id = var.compartment_ocid
  name           = "app-delivery"
  notification_config {
    topic_id = var.project_notification_topic_ocid
  }
}

resource "oci_devops_deploy_environment" "staging" {
  project_id            = oci_devops_project.app.id
  display_name          = "staging"
  deploy_environment_type = "FUNCTION"
  function_id           = "ocid1.fnfunc.oc1..example...replace-me"
}

resource "oci_devops_deploy_environment" "production" {
  project_id              = oci_devops_project.app.id
  display_name            = "production"
  deploy_environment_type = "FUNCTION"
  function_id             = "ocid1.fnfunc.oc1..example...replace-me"
}

resource "oci_devops_deploy_pipeline" "app" {
  project_id   = oci_devops_project.app.id
  display_name = "app-deploy"
  deploy_pipeline_parameters {
    items {
      name          = "release_version"
      default_value = "latest"
    }
  }
}

resource "oci_devops_deploy_stage" "deploy_staging" {
  deploy_pipeline_id = oci_devops_deploy_pipeline.app.id
  deploy_stage_type  = "DEPLOY_FUNCTION"
  display_name       = "deploy-staging"
  deploy_stage_predecessor_collection {
    items {
      id = oci_devops_deploy_pipeline.app.id
    }
  }
  deploy_environment_id_a = oci_devops_deploy_environment.staging.id
}

resource "oci_devops_deploy_stage" "approval_prod" {
  deploy_pipeline_id = oci_devops_deploy_pipeline.app.id
  deploy_stage_type  = "MANUAL_APPROVAL"
  display_name       = "approval-prod"
  deploy_stage_predecessor_collection {
    items {
      id = oci_devops_deploy_stage.deploy_staging.id
    }
  }
  approval_policy {
    approval_policy_type         = "COUNT_BASED_APPROVAL"
    number_of_approvals_required = 1
  }
}

resource "oci_devops_deploy_stage" "deploy_prod" {
  deploy_pipeline_id = oci_devops_deploy_pipeline.app.id
  deploy_stage_type  = "DEPLOY_FUNCTION"
  display_name       = "deploy-prod"
  deploy_stage_predecessor_collection {
    items {
      id = oci_devops_deploy_stage.approval_prod.id
    }
  }
  deploy_environment_id_a = oci_devops_deploy_environment.production.id
}
