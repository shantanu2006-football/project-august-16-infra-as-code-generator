"""Command-line entry point for iacgen."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from . import __version__
from .generator import generate_all, write_all
from .models import (
    SUPPORTED_DEPLOY_TARGETS,
    SUPPORTED_LANGUAGES,
    ProjectSpec,
    ProjectSpecError,
)
from .validators import ValidationError, validate_hcl, validate_yaml

_CONFIG_FIELDS = {
    "project_name",
    "language",
    "deploy_target",
    "python_version",
    "node_version",
    "aws_region",
    "gcp_region",
    "gcp_project_id",
    "port",
    "container_registry",
}


def _load_config_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        data = yaml.safe_load(text)
    elif path.suffix == ".json":
        data = json.loads(text)
    else:
        raise SystemExit(f"error: unsupported config file extension: {path.suffix}")
    if not isinstance(data, dict):
        raise SystemExit("error: config file must contain a mapping of fields")
    unknown = set(data) - _CONFIG_FIELDS
    if unknown:
        raise SystemExit(f"error: unknown config field(s): {', '.join(sorted(unknown))}")
    return data


def _build_spec(args: argparse.Namespace) -> ProjectSpec:
    values: dict = {}
    if args.config:
        values.update(_load_config_file(Path(args.config)))

    # Explicit CLI flags win over config file values.
    for field in ("project_name", "language", "deploy_target", "python_version",
                  "node_version", "aws_region", "gcp_region", "gcp_project_id",
                  "port", "container_registry"):
        cli_value = getattr(args, field, None)
        if cli_value is not None:
            values[field] = cli_value

    missing = {"project_name", "language", "deploy_target"} - values.keys()
    if missing:
        raise SystemExit(
            "error: missing required field(s): "
            f"{', '.join(sorted(missing))} (pass as flags or in --config)"
        )

    try:
        return ProjectSpec(**values)
    except ProjectSpecError as exc:
        raise SystemExit(f"error: {exc}") from exc
    except TypeError as exc:
        raise SystemExit(f"error: invalid config field: {exc}") from exc


def _validate_generated(files: dict[str, str]) -> list[str]:
    problems = []
    for path, content in files.items():
        try:
            if path.endswith((".yml", ".yaml")):
                validate_yaml(content, source=path)
            elif path.endswith(".tf"):
                validate_hcl(content, source=path)
        except ValidationError as exc:
            problems.append(str(exc))
    return problems


def cmd_generate(args: argparse.Namespace) -> int:
    spec = _build_spec(args)
    files = generate_all(spec)

    problems = _validate_generated(files)
    if problems:
        for problem in problems:
            print(f"validation error: {problem}", file=sys.stderr)
        return 1

    if args.dry_run:
        for path, content in sorted(files.items()):
            print(f"--- {path} ---")
            print(content)
        return 0

    written = write_all(spec, Path(args.output_dir))
    for path in written:
        print(f"wrote {path}")
    print(
        f"\nGenerated {len(written)} file(s) for '{spec.project_name}' "
        f"({spec.language} -> {spec.deploy_target}) in {args.output_dir}/"
    )
    return 0


def cmd_list_targets(_args: argparse.Namespace) -> int:
    print("Supported languages:", ", ".join(SUPPORTED_LANGUAGES))
    print("Supported deploy targets:", ", ".join(SUPPORTED_DEPLOY_TARGETS))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="iacgen",
        description=(
            "Generate production-ready GitHub Actions CI/CD pipelines and "
            "Terraform modules from a short project description."
        ),
    )
    parser.add_argument("--version", action="version", version=f"iacgen {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="Generate CI/CD + IaC files")
    generate.add_argument("--config", help="YAML/JSON file describing the project")
    generate.add_argument("--project-name", dest="project_name")
    generate.add_argument("--language", choices=SUPPORTED_LANGUAGES)
    generate.add_argument("--deploy-target", dest="deploy_target", choices=SUPPORTED_DEPLOY_TARGETS)
    generate.add_argument("--python-version", dest="python_version", default=None)
    generate.add_argument("--node-version", dest="node_version", default=None)
    generate.add_argument("--aws-region", dest="aws_region", default=None)
    generate.add_argument("--gcp-region", dest="gcp_region", default=None)
    generate.add_argument("--gcp-project-id", dest="gcp_project_id", default=None)
    generate.add_argument("--port", type=int, default=None)
    generate.add_argument("--container-registry", dest="container_registry", default=None)
    generate.add_argument(
        "--output-dir", default="./generated", help="Directory to write files into (default: ./generated)"
    )
    generate.add_argument(
        "--dry-run", action="store_true", help="Print generated files to stdout instead of writing them"
    )
    generate.set_defaults(func=cmd_generate)

    list_targets = subparsers.add_parser("list-targets", help="List supported languages and deploy targets")
    list_targets.set_defaults(func=cmd_list_targets)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
