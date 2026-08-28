"""Data model for the project description that drives generation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

SUPPORTED_LANGUAGES = ("python", "node")
SUPPORTED_DEPLOY_TARGETS = ("aws-ecs", "aws-lambda", "gcp-cloud-run")

_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{1,38}[a-z0-9]$")

DEFAULT_PYTHON_VERSION = "3.12"
DEFAULT_NODE_VERSION = "20"
DEFAULT_AWS_REGION = "us-east-1"
DEFAULT_GCP_REGION = "us-central1"
DEFAULT_PORT = 8080


class ProjectSpecError(ValueError):
    """Raised when a project description is invalid or unsupported."""


@dataclass(frozen=True)
class ProjectSpec:
    """Describes a project well enough to generate CI/CD + IaC for it.

    Instances are validated at construction time so that every other part
    of the generator can assume the fields are well-formed.
    """

    project_name: str
    language: str
    deploy_target: str
    python_version: str = DEFAULT_PYTHON_VERSION
    node_version: str = DEFAULT_NODE_VERSION
    aws_region: str = DEFAULT_AWS_REGION
    gcp_region: str = DEFAULT_GCP_REGION
    gcp_project_id: str = "my-gcp-project"
    port: int = DEFAULT_PORT
    container_registry: str = field(default="")

    def __post_init__(self) -> None:
        if self.language not in SUPPORTED_LANGUAGES:
            raise ProjectSpecError(
                f"Unsupported language {self.language!r}. "
                f"Supported languages: {', '.join(SUPPORTED_LANGUAGES)}"
            )
        if self.deploy_target not in SUPPORTED_DEPLOY_TARGETS:
            raise ProjectSpecError(
                f"Unsupported deploy target {self.deploy_target!r}. "
                f"Supported targets: {', '.join(SUPPORTED_DEPLOY_TARGETS)}"
            )
        if not _NAME_RE.match(self.project_name):
            raise ProjectSpecError(
                "project_name must be 3-40 lowercase alphanumeric characters "
                "or hyphens, starting with a letter and not ending with a "
                f"hyphen (got {self.project_name!r})"
            )
        if not (1 <= self.port <= 65535):
            raise ProjectSpecError(f"port must be between 1 and 65535 (got {self.port})")
        if self.deploy_target == "aws-lambda" and self.language == "node" and not self.node_version.isdigit():
            raise ProjectSpecError("node_version must be a plain major version, e.g. '20'")

    @property
    def registry_or_default(self) -> str:
        """Container registry to push images to, defaulting per deploy target."""
        if self.container_registry:
            return self.container_registry
        if self.deploy_target == "aws-ecs":
            return f"{self.project_name}-repo"
        if self.deploy_target == "gcp-cloud-run":
            return f"{self.gcp_region}-docker.pkg.dev/{self.gcp_project_id}/{self.project_name}"
        return ""
