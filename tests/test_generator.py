import itertools

import pytest

from iacgen.generator import generate_all, render_dockerfile, render_pipeline, render_terraform
from iacgen.models import SUPPORTED_DEPLOY_TARGETS, SUPPORTED_LANGUAGES, ProjectSpec
from iacgen.validators import validate_hcl, validate_yaml

ALL_COMBOS = list(itertools.product(SUPPORTED_LANGUAGES, SUPPORTED_DEPLOY_TARGETS))


def make_spec(language: str, deploy_target: str, **overrides) -> ProjectSpec:
    defaults = dict(project_name="test-app", language=language, deploy_target=deploy_target)
    defaults.update(overrides)
    return ProjectSpec(**defaults)


@pytest.mark.parametrize("language,deploy_target", ALL_COMBOS)
def test_pipeline_is_valid_yaml_for_every_supported_combo(language, deploy_target):
    spec = make_spec(language, deploy_target)
    yaml_text = render_pipeline(spec)

    parsed = validate_yaml(yaml_text, source="ci-cd.yml")

    assert parsed["name"] == "CI/CD"
    assert "test" in parsed["jobs"]
    # YAML 1.1 treats the bare key `on` as the boolean True; GitHub's own
    # parser special-cases it back to the string "on", but PyYAML doesn't.
    triggers = parsed[True]
    assert set(triggers["push"]["branches"]) == {"main"}


@pytest.mark.parametrize("language,deploy_target", ALL_COMBOS)
def test_terraform_files_are_valid_hcl_for_every_supported_combo(language, deploy_target):
    spec = make_spec(language, deploy_target)
    files = render_terraform(spec)

    assert set(files) == {"main.tf", "variables.tf", "outputs.tf", "versions.tf"}
    for filename, content in files.items():
        parsed = validate_hcl(content, source=filename)
        assert parsed, f"{filename} parsed to an empty document"


@pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
def test_ecs_pipeline_has_build_push_and_deploy_jobs(language):
    spec = make_spec(language, "aws-ecs")
    parsed = validate_yaml(render_pipeline(spec), source="ci-cd.yml")

    jobs = parsed["jobs"]
    assert "build-and-push" in jobs
    assert "deploy" in jobs
    assert jobs["deploy"]["needs"] == "build-and-push"
    assert jobs["build-and-push"]["needs"] == "test"


@pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
def test_lambda_pipeline_skips_docker_build(language):
    spec = make_spec(language, "aws-lambda")
    yaml_text = render_pipeline(spec)
    parsed = validate_yaml(yaml_text, source="ci-cd.yml")

    assert "build-and-push" not in parsed["jobs"]
    assert "deploy" in parsed["jobs"]
    assert "docker build" not in yaml_text


def test_python_pipeline_runs_pytest_and_ruff():
    spec = make_spec("python", "aws-ecs")
    yaml_text = render_pipeline(spec)
    assert "pytest -q" in yaml_text
    assert "ruff check ." in yaml_text
    assert "npm" not in yaml_text


def test_node_pipeline_runs_npm_scripts():
    spec = make_spec("node", "gcp-cloud-run")
    yaml_text = render_pipeline(spec)
    assert "npm ci" in yaml_text
    assert "npm test" in yaml_text
    assert "pytest" not in yaml_text


def test_lambda_terraform_uses_python_runtime():
    spec = make_spec("python", "aws-lambda", python_version="3.12")
    files = render_terraform(spec)
    assert 'default     = "python3.12"' in files["variables.tf"]
    assert 'default     = "app.handler"' in files["variables.tf"]


def test_lambda_terraform_uses_node_runtime():
    spec = make_spec("node", "aws-lambda", node_version="20")
    files = render_terraform(spec)
    assert 'default     = "nodejs20.x"' in files["variables.tf"]
    assert 'default     = "index.handler"' in files["variables.tf"]


def test_ecs_terraform_references_container_port():
    spec = make_spec("python", "aws-ecs", port=9000)
    files = render_terraform(spec)
    assert "default     = 9000" in files["variables.tf"]


@pytest.mark.parametrize("deploy_target", ["aws-ecs", "gcp-cloud-run"])
def test_dockerfile_generated_for_container_targets(deploy_target):
    spec = make_spec("python", deploy_target)
    dockerfile = render_dockerfile(spec)
    assert dockerfile is not None
    assert "FROM python:3.12-slim" in dockerfile
    assert "EXPOSE 8080" in dockerfile


def test_no_dockerfile_for_lambda():
    spec = make_spec("python", "aws-lambda")
    assert render_dockerfile(spec) is None


@pytest.mark.parametrize("language,deploy_target", ALL_COMBOS)
def test_generate_all_produces_expected_file_set(language, deploy_target):
    spec = make_spec(language, deploy_target)
    files = generate_all(spec)

    assert ".github/workflows/ci-cd.yml" in files
    assert "terraform/main.tf" in files
    if deploy_target == "aws-lambda":
        assert "Dockerfile" not in files
    else:
        assert "Dockerfile" in files
