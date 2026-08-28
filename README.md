# iacgen — Infra-as-Code / CI-CD Generator

Generate a production-ready GitHub Actions CI/CD pipeline and a matching
Terraform module from a one-line description of a project: its language and
where it deploys.

## Problem statement

Every new service in a polyglot org re-derives the same boilerplate: a
GitHub Actions workflow that lints, tests, builds an image (or a Lambda
zip), and deploys it, plus a Terraform module that actually stands up the
target infrastructure. Hand-writing (or copy-pasting from the last repo)
these files is slow and error-prone — a missing colon in the workflow YAML
or a stray brace in a `.tf` file is only caught after a failed CI run or a
bad `terraform plan`.

`iacgen` takes a small, validated description of a project —
**language** (`python` or `node`) and **deploy target** (`aws-ecs`,
`aws-lambda`, or `gcp-cloud-run`) — and renders both artifacts from real
Jinja2 templates. Every combination it can produce is covered by a test
that actually parses the output with a YAML/HCL parser, so a broken
template fails `pytest`, not a teammate's CI run.

## Architecture & design decisions

```
src/iacgen/
├── models.py       # ProjectSpec: the validated project description
├── generator.py     # Renders templates -> in-memory files / disk
├── validators.py     # Parses generated YAML/HCL to prove it's well-formed
├── cli.py            # argparse-based `iacgen` command
└── templates/
    ├── github_actions/ci-cd.yml.j2      # one workflow template, branched
    │                                     # by {{ language }} / {{ deploy_target }}
    ├── terraform/aws_ecs/*.tf.j2         # one directory of .tf templates
    ├── terraform/aws_lambda/*.tf.j2      # per deploy target
    ├── terraform/gcp_cloud_run/*.tf.j2
    └── docker/Dockerfile.{python,node}.j2
```

Key decisions:

- **Real templating, not string concatenation.** Every generated file is a
  [Jinja2](https://jinja.palletsprojects.com/) template rendered with a
  `StrictUndefined` environment (a template referencing an unset variable
  raises immediately instead of silently emitting `None`/blank).
- **A `ProjectSpec` dataclass is the single source of truth.** It validates
  language, deploy target, project name (DNS/resource-name-safe), and port
  at construction time (`models.py`), so every downstream template can
  assume its inputs are well-formed — no defensive checks scattered through
  the templates.
- **One workflow template, `{% if %}`-branched**, rather than 6 near-duplicate
  YAML files for 2 languages × 3 targets. The language controls the test/lint
  steps; the deploy target controls the build+deploy jobs. This keeps the
  templates maintainable and avoids drift between near-identical copies.
- **Terraform is split one directory per deploy target** (`aws_ecs/`,
  `aws_lambda/`, `gcp_cloud_run/`) rather than one giant conditional module,
  because ECS, Lambda, and Cloud Run each need a genuinely different resource
  graph (task definitions + ECS service vs. a Lambda function + IAM role vs.
  a Cloud Run service + Artifact Registry repo) — collapsing them into one
  template would produce unreadable, over-conditional HCL.
- **Generated output is validated before it's written.** `iacgen generate`
  parses every `.yml`/`.yaml` file with PyYAML and every `.tf` file with
  [`python-hcl2`](https://pypi.org/project/python-hcl2/) and refuses to write
  anything if a file fails to parse. This is the same check the test suite
  runs, just wired into the CLI so a broken template can never reach disk.
- **CLI accepts flags or a config file.** `--language`/`--deploy-target`/etc.
  flags cover the "simple project description" case directly; a
  `--config project.yaml` (or `.json`) file covers repeatable/scripted use.
  Flags always win over config file values, so a config file can be a
  reusable base with one-off overrides on the command line.

## Supported matrix

| Language | Deploy targets                          |
|----------|------------------------------------------|
| `python` | `aws-ecs`, `aws-lambda`, `gcp-cloud-run`  |
| `node`   | `aws-ecs`, `aws-lambda`, `gcp-cloud-run`  |

Run `iacgen list-targets` to print this from the CLI itself.

## Setup

Requires Python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

(Or `pip install -r requirements.txt` for runtime-only use, `-r
requirements-dev.txt` to add `pytest`/`ruff`.)

## Running the tests

```bash
pytest -v      # 63 tests: every language x deploy-target combination is
                # generated and its YAML/HCL output is actually parsed
ruff check .    # lint
```

## Usage

```bash
# Generate straight from flags
iacgen generate \
  --project-name payments-api \
  --language python \
  --deploy-target aws-ecs \
  --output-dir ./out

# Or from a config file
cat > project.yaml <<EOF
project_name: payments-api
language: python
deploy_target: aws-ecs
aws_region: us-east-1
port: 8080
EOF
iacgen generate --config project.yaml --output-dir ./out

# Preview without writing anything
iacgen generate --project-name demo --language node --deploy-target gcp-cloud-run --dry-run

# List what's supported
iacgen list-targets
```

### Example output

`iacgen generate --project-name payments-api --language python --deploy-target aws-ecs --output-dir ./out`
writes:

```
out/
├── .github/workflows/ci-cd.yml   # test job (pytest+ruff) -> build & push to ECR -> deploy to ECS
├── Dockerfile                     # python:3.12-slim, EXPOSE 8080
└── terraform/
    ├── versions.tf                 # aws provider ~> 5.0
    ├── variables.tf                # project_name, container_port, task_cpu/memory, ...
    ├── main.tf                     # ECR repo, ECS cluster/service/task def, IAM, security group,
    │                                 CloudWatch log group, on the default VPC
    └── outputs.tf                  # ecr_repository_url, ecs_cluster_name, ecs_service_name
```

The generated `ci-cd.yml` for that command starts:

```yaml
name: CI/CD

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  AWS_REGION: us-east-1
  PROJECT_NAME: payments-api

jobs:
  test:
    name: Test
    runs-on: ubuntu-latest
    steps:
      - name: Check out code
        uses: actions/checkout@v4
      - name: Set up Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      ...
  build-and-push:
    needs: test
    ...
  deploy:
    needs: build-and-push
    ...
```

For `aws-lambda` the pipeline packages a zip and calls
`aws lambda update-function-code` instead of building a container; for
`gcp-cloud-run` it builds/pushes to Artifact Registry and deploys via
`google-github-actions/deploy-cloudrun`.

## Future work

Cut to keep this session's scope tight and correct rather than broad:

- More languages (Go, Java) and targets (Kubernetes/Helm, Azure Container
  Apps, plain EC2/VM).
- A `--validate-only` mode that checks an *existing* directory's YAML/HCL
  without regenerating it (today validation only runs on freshly rendered
  output).
- Rendering a matching `docker-compose.yml` for local development.
- An interactive `iacgen init` wizard instead of requiring flags/config
  up front.

## License

MIT — see [LICENSE](LICENSE).
