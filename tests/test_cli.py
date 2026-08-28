import json

import pytest
import yaml

from iacgen.cli import main


def test_generate_writes_files(tmp_path, capsys):
    output_dir = tmp_path / "out"
    exit_code = main(
        [
            "generate",
            "--project-name",
            "my-app",
            "--language",
            "python",
            "--deploy-target",
            "aws-ecs",
            "--output-dir",
            str(output_dir),
        ]
    )
    assert exit_code == 0

    assert (output_dir / ".github/workflows/ci-cd.yml").exists()
    assert (output_dir / "terraform/main.tf").exists()
    assert (output_dir / "Dockerfile").exists()

    captured = capsys.readouterr()
    assert "Generated" in captured.out


def test_generate_dry_run_does_not_write_files(tmp_path, capsys):
    output_dir = tmp_path / "out"
    exit_code = main(
        [
            "generate",
            "--project-name",
            "my-app",
            "--language",
            "node",
            "--deploy-target",
            "gcp-cloud-run",
            "--output-dir",
            str(output_dir),
            "--dry-run",
        ]
    )
    assert exit_code == 0
    assert not output_dir.exists()

    captured = capsys.readouterr()
    assert "--- .github/workflows/ci-cd.yml ---" in captured.out
    assert "name: CI/CD" in captured.out


def test_generate_from_config_file(tmp_path):
    config_path = tmp_path / "project.yaml"
    config_path.write_text(
        yaml.dump(
            {
                "project_name": "config-app",
                "language": "python",
                "deploy_target": "aws-lambda",
                "aws_region": "eu-west-1",
            }
        )
    )
    output_dir = tmp_path / "out"

    exit_code = main(["generate", "--config", str(config_path), "--output-dir", str(output_dir)])
    assert exit_code == 0

    workflow = (output_dir / ".github/workflows/ci-cd.yml").read_text()
    parsed = yaml.safe_load(workflow)
    assert parsed["env"]["AWS_REGION"] == "eu-west-1"


def test_cli_flags_override_config_file(tmp_path):
    config_path = tmp_path / "project.json"
    config_path.write_text(json.dumps({"project_name": "from-config", "language": "python",
                                        "deploy_target": "aws-ecs"}))
    output_dir = tmp_path / "out"

    exit_code = main(
        [
            "generate",
            "--config",
            str(config_path),
            "--project-name",
            "from-cli",
            "--output-dir",
            str(output_dir),
        ]
    )
    assert exit_code == 0
    terraform = (output_dir / "terraform/variables.tf").read_text()
    assert "from-cli" in terraform
    assert "from-config" not in terraform


def test_missing_required_fields_exits_with_error():
    with pytest.raises(SystemExit):
        main(["generate", "--project-name", "my-app"])


def test_invalid_language_rejected_by_argparse():
    with pytest.raises(SystemExit):
        main(["generate", "--project-name", "my-app", "--language", "cobol", "--deploy-target", "aws-ecs"])


def test_invalid_project_name_produces_clean_error():
    with pytest.raises(SystemExit):
        main(
            [
                "generate",
                "--project-name",
                "Not Valid!",
                "--language",
                "python",
                "--deploy-target",
                "aws-ecs",
            ]
        )


def test_list_targets(capsys):
    exit_code = main(["list-targets"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "python" in captured.out
    assert "aws-ecs" in captured.out
