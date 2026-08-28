"""Syntax validation for generated artifacts.

Used both by the test suite (to prove generated output is well-formed) and
by the CLI's ``--validate`` flag (to catch template regressions before they
reach disk).
"""

from __future__ import annotations

import hcl2
import yaml


class ValidationError(ValueError):
    """Raised when generated output fails to parse."""


def validate_yaml(content: str, *, source: str = "<yaml>") -> dict:
    """Parse YAML content, raising ValidationError with context on failure."""
    try:
        return yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise ValidationError(f"Invalid YAML in {source}: {exc}") from exc


def validate_hcl(content: str, *, source: str = "<hcl>") -> dict:
    """Parse Terraform/HCL content, raising ValidationError with context."""
    import io

    try:
        return hcl2.load(io.StringIO(content))
    except Exception as exc:  # hcl2 raises lark parse errors, not a common base
        raise ValidationError(f"Invalid HCL in {source}: {exc}") from exc
