"""Renders CI/CD pipelines and Terraform modules for a ProjectSpec."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from .models import ProjectSpec

_TERRAFORM_DIR_BY_TARGET = {
    "aws-ecs": "aws_ecs",
    "aws-lambda": "aws_lambda",
    "gcp-cloud-run": "gcp_cloud_run",
}

_LAMBDA_RUNTIME = {
    "python": "python{version}",
    "node": "nodejs{version}.x",
}

_LAMBDA_HANDLER = {
    "python": "app.handler",
    "node": "index.handler",
}


def _jinja_env() -> Environment:
    return Environment(
        loader=PackageLoader("iacgen", "templates"),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        autoescape=select_autoescape(enabled_extensions=(), default=False),
    )


def _base_context(spec: ProjectSpec) -> dict:
    return {
        "project_name": spec.project_name,
        "language": spec.language,
        "deploy_target": spec.deploy_target,
        "python_version": spec.python_version,
        "node_version": spec.node_version,
        "aws_region": spec.aws_region,
        "gcp_region": spec.gcp_region,
        "gcp_project_id": spec.gcp_project_id,
        "port": spec.port,
        "registry_or_default": spec.registry_or_default,
    }


def render_pipeline(spec: ProjectSpec) -> str:
    """Render the GitHub Actions CI/CD workflow YAML for this spec."""
    env = _jinja_env()
    template = env.get_template("github_actions/ci-cd.yml.j2")
    return template.render(**_base_context(spec))


def render_terraform(spec: ProjectSpec) -> dict[str, str]:
    """Render every Terraform file for this spec's deploy target.

    Returns a mapping of filename (e.g. "main.tf") to rendered contents.
    """
    env = _jinja_env()
    tf_dir = _TERRAFORM_DIR_BY_TARGET[spec.deploy_target]
    context = _base_context(spec)

    if spec.deploy_target == "aws-lambda":
        version = spec.python_version if spec.language == "python" else spec.node_version
        context["lambda_runtime"] = _LAMBDA_RUNTIME[spec.language].format(version=version)
        context["lambda_handler"] = _LAMBDA_HANDLER[spec.language]

    template_names = _list_templates(env, f"terraform/{tf_dir}")
    rendered = {}
    for name in template_names:
        template = env.get_template(f"terraform/{tf_dir}/{name}")
        output_name = name.removesuffix(".j2")
        rendered[output_name] = template.render(**context)
    return rendered


def render_dockerfile(spec: ProjectSpec) -> str | None:
    """Render a Dockerfile for container-based deploy targets, else None.

    AWS Lambda deploys a zip package rather than a container image, so no
    Dockerfile is produced for that target.
    """
    if spec.deploy_target == "aws-lambda":
        return None
    env = _jinja_env()
    template = env.get_template(f"docker/Dockerfile.{spec.language}.j2")
    return template.render(**_base_context(spec))


def _list_templates(env: Environment, prefix: str) -> list[str]:
    names = [
        name[len(prefix) + 1 :]
        for name in env.loader.list_templates()  # type: ignore[union-attr]
        if name.startswith(prefix + "/")
    ]
    if not names:
        raise FileNotFoundError(f"No templates found under {prefix!r}")
    return sorted(names)


def generate_all(spec: ProjectSpec) -> dict[str, str]:
    """Render every generated file for a spec as {relative_path: contents}."""
    files = {".github/workflows/ci-cd.yml": render_pipeline(spec)}

    for filename, content in render_terraform(spec).items():
        files[f"terraform/{filename}"] = content

    dockerfile = render_dockerfile(spec)
    if dockerfile is not None:
        files["Dockerfile"] = dockerfile

    return files


def write_all(spec: ProjectSpec, output_dir: Path) -> list[Path]:
    """Render every generated file for a spec and write it to output_dir.

    Returns the list of file paths written, relative to output_dir being
    resolved to absolute paths.
    """
    output_dir = Path(output_dir)
    written: list[Path] = []
    for relative_path, content in generate_all(spec).items():
        destination = output_dir / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
        written.append(destination)
    return written
