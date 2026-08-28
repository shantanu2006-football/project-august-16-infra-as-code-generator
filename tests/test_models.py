import pytest

from iacgen.models import ProjectSpec, ProjectSpecError


def test_valid_spec_constructs():
    spec = ProjectSpec(project_name="my-app", language="python", deploy_target="aws-ecs")
    assert spec.project_name == "my-app"
    assert spec.python_version == "3.12"


@pytest.mark.parametrize("language", ["ruby", "go", "PYTHON", ""])
def test_unsupported_language_rejected(language):
    with pytest.raises(ProjectSpecError):
        ProjectSpec(project_name="my-app", language=language, deploy_target="aws-ecs")


@pytest.mark.parametrize("target", ["heroku", "azure-app-service", ""])
def test_unsupported_deploy_target_rejected(target):
    with pytest.raises(ProjectSpecError):
        ProjectSpec(project_name="my-app", language="python", deploy_target=target)


@pytest.mark.parametrize(
    "name",
    ["My-App", "-my-app", "my-app-", "a", "my_app", "my app", "a" * 41],
)
def test_invalid_project_name_rejected(name):
    with pytest.raises(ProjectSpecError):
        ProjectSpec(project_name=name, language="python", deploy_target="aws-ecs")


@pytest.mark.parametrize("port", [0, -1, 65536, 100000])
def test_invalid_port_rejected(port):
    with pytest.raises(ProjectSpecError):
        ProjectSpec(project_name="my-app", language="python", deploy_target="aws-ecs", port=port)


def test_registry_defaults_per_target():
    ecs = ProjectSpec(project_name="my-app", language="python", deploy_target="aws-ecs")
    assert ecs.registry_or_default == "my-app-repo"

    cloud_run = ProjectSpec(project_name="my-app", language="python", deploy_target="gcp-cloud-run")
    assert "my-app" in cloud_run.registry_or_default
    assert cloud_run.gcp_region in cloud_run.registry_or_default

    lambda_spec = ProjectSpec(project_name="my-app", language="python", deploy_target="aws-lambda")
    assert lambda_spec.registry_or_default == ""


def test_explicit_container_registry_overrides_default():
    spec = ProjectSpec(
        project_name="my-app",
        language="python",
        deploy_target="aws-ecs",
        container_registry="123456789012.dkr.ecr.us-east-1.amazonaws.com/custom-repo",
    )
    assert spec.registry_or_default == "123456789012.dkr.ecr.us-east-1.amazonaws.com/custom-repo"
