"""Real-world integration tests — parse/roundtrip/CLI on production-grade configs.

Covers: Docker Compose v3, GitHub Actions, Kubernetes Deployment, Ansible
playbooks, and the existing k8s fixtures in tests/fixtures/.  Each test
validates data fidelity across format conversions that real users run.
"""
import json
import os
import sys

import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.configforge import (
    HAS_HCL,
    HAS_TOML,
    convert,
    detect_format,
    parse_text,
)

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")

# ── Inline fixtures ────────────────────────────────────────────────────────────

DOCKER_COMPOSE = """\
version: '3.8'
services:
  web:
    image: nginx:1.25-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - app
    networks:
      - frontend
    restart: unless-stopped
  app:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: postgres://db:5432/myapp
      DEBUG: "false"
      WORKERS: "4"
    volumes:
      - ./app:/app
      - static_files:/app/static
    depends_on:
      db:
        condition: service_healthy
    networks:
      - frontend
      - backend
    restart: unless-stopped
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: myapp
      POSTGRES_USER: postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - backend
    restart: unless-stopped
volumes:
  postgres_data:
  static_files:
networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge
    internal: true
"""

GITHUB_ACTIONS = """\
name: CI
on:
  push:
    branches:
      - main
      - develop
  pull_request:
    branches:
      - main
    types:
      - opened
      - synchronize
      - reopened
  schedule:
    - cron: '0 6 * * 1'
env:
  PYTHON_VERSION: '3.12'
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version:
          - '3.10'
          - '3.11'
          - '3.12'
          - '3.13'
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"
      - name: Run tests
        run: pytest tests/ -q --tb=short
        env:
          PYTHONPATH: .
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        if: matrix.python-version == '3.12'
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - run: pip install ruff
      - run: ruff check .
"""

K8S_DEPLOYMENT = """\
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
  namespace: production
  labels:
    app: myapp
    version: v1.2.3
    environment: production
  annotations:
    deployment.kubernetes.io/revision: "5"
spec:
  replicas: 3
  selector:
    matchLabels:
      app: myapp
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  template:
    metadata:
      labels:
        app: myapp
        version: v1.2.3
    spec:
      containers:
        - name: myapp
          image: registry.example.com/myapp:v1.2.3
          ports:
            - containerPort: 8080
              protocol: TCP
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: myapp-secrets
                  key: database-url
            - name: REDIS_URL
              valueFrom:
                configMapKeyRef:
                  name: myapp-config
                  key: redis-url
          resources:
            requests:
              memory: "128Mi"
              cpu: "100m"
            limits:
              memory: "256Mi"
              cpu: "500m"
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 15
            periodSeconds: 20
          readinessProbe:
            httpGet:
              path: /ready
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 10
      nodeSelector:
        kubernetes.io/os: linux
      terminationGracePeriodSeconds: 60
"""

ANSIBLE_PLAYBOOK = """\
---
- name: Deploy application stack
  hosts: webservers
  become: true
  gather_facts: true
  vars:
    app_version: "1.2.3"
    app_port: 8080
    app_user: appuser
    deploy_dir: /opt/myapp
  pre_tasks:
    - name: Update apt cache
      apt:
        update_cache: true
        cache_valid_time: 3600
  tasks:
    - name: Create application directory
      file:
        path: "{{ deploy_dir }}"
        state: directory
        owner: "{{ app_user }}"
        mode: '0755'
    - name: Install Python requirements
      pip:
        requirements: "{{ deploy_dir }}/requirements.txt"
        virtualenv: "{{ deploy_dir }}/venv"
    - name: Start and enable service
      systemd:
        name: myapp
        state: started
        enabled: true
        daemon_reload: true
  handlers:
    - name: restart application
      systemd:
        name: myapp
        state: restarted
"""

HCL_TERRAFORM = """\
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

variable "environment" {
  type    = string
  default = "production"
}

resource "aws_s3_bucket" "app_assets" {
  bucket = "myapp-assets"
  tags = {
    Name        = "App Assets"
    Environment = "production"
  }
}

resource "aws_security_group" "web" {
  name        = "web-sg"
  description = "Security group for web tier"

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
"""


# ── Helpers ────────────────────────────────────────────────────────────────────

def _yaml_json_yaml_roundtrip(src: str) -> dict:
    """YAML → JSON → YAML and return the re-parsed dict."""
    r1 = convert(src, "json", "yaml")
    assert r1["success"], f"yaml→json failed: {r1}"
    r2 = convert(r1["output"], "yaml", "json")
    assert r2["success"], f"json→yaml failed: {r2}"
    original = yaml.safe_load(src)
    final = yaml.safe_load(r2["output"])
    return {"original": original, "final": final, "yaml_out": r2["output"]}


# ── Docker Compose ─────────────────────────────────────────────────────────────

def test_docker_compose_detects_as_yaml():
    assert detect_format(DOCKER_COMPOSE) == "yaml"


def test_docker_compose_parse_services():
    result = parse_text(DOCKER_COMPOSE, "yaml")
    data = result["data"]
    assert "services" in data
    assert "web" in data["services"]
    assert "app" in data["services"]
    assert "db" in data["services"]


def test_docker_compose_parse_image_fields():
    result = parse_text(DOCKER_COMPOSE, "yaml")
    data = result["data"]
    assert data["services"]["web"]["image"] == "nginx:1.25-alpine"
    assert data["services"]["db"]["image"] == "postgres:15-alpine"


def test_docker_compose_parse_ports():
    result = parse_text(DOCKER_COMPOSE, "yaml")
    ports = result["data"]["services"]["web"]["ports"]
    assert "80:80" in ports
    assert "443:443" in ports


def test_docker_compose_parse_volumes_and_networks():
    result = parse_text(DOCKER_COMPOSE, "yaml")
    data = result["data"]
    assert "postgres_data" in data["volumes"]
    assert "static_files" in data["volumes"]
    assert "frontend" in data["networks"]
    assert "backend" in data["networks"]
    assert data["networks"]["backend"]["internal"] is True


def test_docker_compose_yaml_to_json_roundtrip():
    rt = _yaml_json_yaml_roundtrip(DOCKER_COMPOSE)
    orig, final = rt["original"], rt["final"]
    assert final["version"] == orig["version"]
    assert set(final["services"].keys()) == set(orig["services"].keys())
    assert final["services"]["db"]["image"] == orig["services"]["db"]["image"]


def test_docker_compose_json_output_valid():
    r = convert(DOCKER_COMPOSE, "json")
    assert r["success"]
    data = json.loads(r["output"])
    assert data["services"]["app"]["environment"]["WORKERS"] == "4"
    assert data["services"]["db"]["healthcheck"]["retries"] == 5


def test_docker_compose_healthcheck_preserved_after_roundtrip():
    rt = _yaml_json_yaml_roundtrip(DOCKER_COMPOSE)
    hc = rt["final"]["services"]["db"]["healthcheck"]
    assert hc["interval"] == "10s"
    assert hc["retries"] == 5


def test_docker_compose_cli_get(tmp_path, capsys):
    f = tmp_path / "docker-compose.yaml"
    f.write_text(DOCKER_COMPOSE)
    from core.cli import main
    rc = main(["cf", str(f), "--get", "services.web.image"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "nginx:1.25-alpine" in out


def test_docker_compose_cli_pick_services(tmp_path, capsys):
    f = tmp_path / "docker-compose.yaml"
    f.write_text(DOCKER_COMPOSE)
    from core.cli import main
    rc = main(["cf", str(f), "--pick", "services", "--to", "json"])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    # --pick with a single nested key returns the value directly (unwrapped)
    assert "web" in data
    assert "app" in data
    assert "db" in data


def test_docker_compose_cli_grep_image(tmp_path, capsys):
    f = tmp_path / "docker-compose.yaml"
    f.write_text(DOCKER_COMPOSE)
    from core.cli import main
    rc = main(["cf", str(f), "--grep", "postgres"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "postgres" in out.lower()


def test_docker_compose_cli_grep_port(tmp_path, capsys):
    f = tmp_path / "docker-compose.yaml"
    f.write_text(DOCKER_COMPOSE)
    from core.cli import main
    rc = main(["cf", str(f), "--grep", "443"])
    out = capsys.readouterr().out
    assert rc == 0


# ── GitHub Actions ─────────────────────────────────────────────────────────────

def test_github_actions_detects_as_yaml():
    assert detect_format(GITHUB_ACTIONS) == "yaml"


def test_github_actions_parse_triggers():
    result = parse_text(GITHUB_ACTIONS, "yaml")
    data = result["data"]
    # PyYAML treats 'on' as a YAML 1.1 boolean (True); access via True key
    trigger_key = True if True in data else "on"
    triggers = data[trigger_key]
    assert "push" in triggers
    assert "pull_request" in triggers
    assert "main" in triggers["push"]["branches"]


def test_github_actions_parse_jobs():
    result = parse_text(GITHUB_ACTIONS, "yaml")
    data = result["data"]
    assert "test" in data["jobs"]
    assert "lint" in data["jobs"]


def test_github_actions_parse_matrix():
    result = parse_text(GITHUB_ACTIONS, "yaml")
    matrix = result["data"]["jobs"]["test"]["strategy"]["matrix"]["python-version"]
    assert "3.10" in matrix
    assert "3.13" in matrix


def test_github_actions_yaml_to_json_roundtrip():
    rt = _yaml_json_yaml_roundtrip(GITHUB_ACTIONS)
    orig, final = rt["original"], rt["final"]
    assert set(final["jobs"].keys()) == set(orig["jobs"].keys())
    orig_matrix = orig["jobs"]["test"]["strategy"]["matrix"]["python-version"]
    final_matrix = final["jobs"]["test"]["strategy"]["matrix"]["python-version"]
    assert set(str(v) for v in final_matrix) == set(str(v) for v in orig_matrix)


def test_github_actions_cli_get_name(tmp_path, capsys):
    f = tmp_path / "ci.yml"
    f.write_text(GITHUB_ACTIONS)
    from core.cli import main
    rc = main(["cf", str(f), "--get", "name"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "CI" in out


def test_github_actions_cli_grep_uses(tmp_path, capsys):
    f = tmp_path / "ci.yml"
    f.write_text(GITHUB_ACTIONS)
    from core.cli import main
    rc = main(["cf", str(f), "--grep", "actions/checkout"])
    out = capsys.readouterr().out
    assert rc == 0


def test_github_actions_cli_pick_env(tmp_path, capsys):
    f = tmp_path / "ci.yml"
    f.write_text(GITHUB_ACTIONS)
    from core.cli import main
    rc = main(["cf", str(f), "--pick", "env", "--to", "json"])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    # --pick with a single key returns the value directly (unwrapped)
    assert data["PYTHON_VERSION"] == "3.12"


# ── Kubernetes Deployment ──────────────────────────────────────────────────────

def test_k8s_deployment_detects_as_yaml():
    assert detect_format(K8S_DEPLOYMENT) == "yaml"


def test_k8s_deployment_parse_metadata():
    result = parse_text(K8S_DEPLOYMENT, "yaml")
    meta = result["data"]["metadata"]
    assert meta["name"] == "myapp"
    assert meta["namespace"] == "production"
    assert meta["labels"]["environment"] == "production"


def test_k8s_deployment_parse_spec():
    result = parse_text(K8S_DEPLOYMENT, "yaml")
    spec = result["data"]["spec"]
    assert spec["replicas"] == 3
    assert spec["strategy"]["type"] == "RollingUpdate"
    assert spec["strategy"]["rollingUpdate"]["maxUnavailable"] == 0


def test_k8s_deployment_parse_container():
    result = parse_text(K8S_DEPLOYMENT, "yaml")
    containers = result["data"]["spec"]["template"]["spec"]["containers"]
    assert len(containers) == 1
    c = containers[0]
    assert c["name"] == "myapp"
    assert c["image"] == "registry.example.com/myapp:v1.2.3"
    assert c["ports"][0]["containerPort"] == 8080


def test_k8s_deployment_parse_resource_limits():
    result = parse_text(K8S_DEPLOYMENT, "yaml")
    resources = result["data"]["spec"]["template"]["spec"]["containers"][0]["resources"]
    assert resources["requests"]["memory"] == "128Mi"
    assert resources["limits"]["cpu"] == "500m"


def test_k8s_deployment_yaml_to_json_roundtrip():
    rt = _yaml_json_yaml_roundtrip(K8S_DEPLOYMENT)
    orig, final = rt["original"], rt["final"]
    assert final["metadata"]["name"] == orig["metadata"]["name"]
    assert final["spec"]["replicas"] == orig["spec"]["replicas"]
    orig_c = orig["spec"]["template"]["spec"]["containers"][0]
    final_c = final["spec"]["template"]["spec"]["containers"][0]
    assert final_c["image"] == orig_c["image"]


def test_k8s_deployment_json_output_is_valid():
    r = convert(K8S_DEPLOYMENT, "json")
    assert r["success"]
    data = json.loads(r["output"])
    assert data["apiVersion"] == "apps/v1"
    assert data["kind"] == "Deployment"


def test_k8s_deployment_cli_get_replicas(tmp_path, capsys):
    f = tmp_path / "deploy.yaml"
    f.write_text(K8S_DEPLOYMENT)
    from core.cli import main
    rc = main(["cf", str(f), "--get", "spec.replicas"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "3" in out


def test_k8s_deployment_cli_get_image(tmp_path, capsys):
    f = tmp_path / "deploy.yaml"
    f.write_text(K8S_DEPLOYMENT)
    from core.cli import main
    rc = main(["cf", str(f), "--get", "spec.template.spec.containers.0.image"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "myapp:v1.2.3" in out


def test_k8s_deployment_cli_pick_metadata(tmp_path, capsys):
    f = tmp_path / "deploy.yaml"
    f.write_text(K8S_DEPLOYMENT)
    from core.cli import main
    rc = main(["cf", str(f), "--pick", "metadata", "--to", "json"])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    # --pick with a single key returns the value directly (unwrapped)
    assert data["name"] == "myapp"
    assert data["namespace"] == "production"


def test_k8s_deployment_cli_grep_image(tmp_path, capsys):
    f = tmp_path / "deploy.yaml"
    f.write_text(K8S_DEPLOYMENT)
    from core.cli import main
    rc = main(["cf", str(f), "--grep", "registry.example.com"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "registry.example.com" in out


def test_k8s_deployment_cli_grep_secret(tmp_path, capsys):
    f = tmp_path / "deploy.yaml"
    f.write_text(K8S_DEPLOYMENT)
    from core.cli import main
    rc = main(["cf", str(f), "--grep", "secretKeyRef"])
    out = capsys.readouterr().out
    assert rc == 0


def test_k8s_deployment_cli_set_replicas(tmp_path, capsys):
    f = tmp_path / "deploy.yaml"
    f.write_text(K8S_DEPLOYMENT)
    from core.cli import main
    rc = main(["cf", str(f), "--set", "spec.replicas", "5"])
    out = capsys.readouterr().out
    assert rc == 0
    updated = yaml.safe_load(out)
    assert updated["spec"]["replicas"] == 5
    assert updated["metadata"]["name"] == "myapp"


# ── Kubernetes existing fixtures ───────────────────────────────────────────────

@pytest.fixture
def k8s_ingress_path():
    return os.path.join(FIXTURES, "k8s_ingress.yaml")


@pytest.fixture
def helm_values_path():
    return os.path.join(FIXTURES, "helm_values.yaml")


@pytest.fixture
def redis_deployment_path():
    return os.path.join(FIXTURES, "redis-master-deployment.yaml")


def test_fixture_k8s_ingress_parses(k8s_ingress_path):
    text = open(k8s_ingress_path).read()
    result = parse_text(text, "yaml")
    data = result["data"]
    # Multi-document YAML returns a list
    if isinstance(data, list):
        kinds = {doc["kind"] for doc in data if doc and "kind" in doc}
        assert "Deployment" in kinds or "Service" in kinds or "Namespace" in kinds
    else:
        assert "kind" in data or "apiVersion" in data


def test_fixture_k8s_ingress_yaml_to_json(k8s_ingress_path):
    text = open(k8s_ingress_path).read()
    r = convert(text, "json")
    assert r["success"]
    data = json.loads(r["output"])
    assert isinstance(data, (dict, list))


def test_fixture_helm_values_parses(helm_values_path):
    text = open(helm_values_path).read()
    result = parse_text(text, "yaml")
    assert result["format"] in ("yaml", "yaml-multi")
    assert isinstance(result["data"], (dict, list))


def test_fixture_helm_values_roundtrip(helm_values_path):
    text = open(helm_values_path).read()
    r1 = convert(text, "json", "yaml")
    assert r1["success"]
    r2 = convert(r1["output"], "yaml", "json")
    assert r2["success"]
    orig = yaml.safe_load(text)
    final = yaml.safe_load(r2["output"])
    assert type(orig) == type(final)


def test_fixture_redis_deployment_parses(redis_deployment_path):
    text = open(redis_deployment_path).read()
    result = parse_text(text, "yaml")
    data = result["data"]
    if isinstance(data, list):
        assert all(d is None or isinstance(d, dict) for d in data)
    else:
        assert isinstance(data, dict)


def test_fixture_redis_deployment_parses_gracefully(redis_deployment_path, capsys):
    text = open(redis_deployment_path).read()
    # The fixture may be a stub ("404: Not Found") or a real manifest;
    # either way parse_text must not raise.
    try:
        result = parse_text(text, "yaml")
        assert result is not None
    except Exception as exc:
        pytest.fail(f"parse_text raised unexpectedly: {exc}")


# ── Ansible Playbook ───────────────────────────────────────────────────────────

def test_ansible_playbook_detects_as_yaml():
    assert detect_format(ANSIBLE_PLAYBOOK) == "yaml"


def test_ansible_playbook_parses_as_list():
    result = parse_text(ANSIBLE_PLAYBOOK, "yaml")
    data = result["data"]
    # Ansible playbooks are YAML lists of plays
    assert isinstance(data, list)
    assert len(data) >= 1


def test_ansible_playbook_parse_play_fields():
    result = parse_text(ANSIBLE_PLAYBOOK, "yaml")
    play = result["data"][0]
    assert play["name"] == "Deploy application stack"
    assert play["hosts"] == "webservers"
    assert play["become"] is True


def test_ansible_playbook_parse_vars():
    result = parse_text(ANSIBLE_PLAYBOOK, "yaml")
    play = result["data"][0]
    assert play["vars"]["app_port"] == 8080
    assert play["vars"]["deploy_dir"] == "/opt/myapp"


def test_ansible_playbook_parse_tasks():
    result = parse_text(ANSIBLE_PLAYBOOK, "yaml")
    play = result["data"][0]
    tasks = play["tasks"]
    task_names = [t["name"] for t in tasks]
    assert "Create application directory" in task_names
    assert "Start and enable service" in task_names


def test_ansible_playbook_yaml_to_json_roundtrip():
    r = convert(ANSIBLE_PLAYBOOK, "json")
    assert r["success"]
    data = json.loads(r["output"])
    assert isinstance(data, list)
    play = data[0]
    assert play["name"] == "Deploy application stack"
    assert play["vars"]["app_port"] == 8080


def test_ansible_playbook_json_to_yaml_content_preserved():
    r1 = convert(ANSIBLE_PLAYBOOK, "json")
    assert r1["success"]
    r2 = convert(r1["output"], "yaml")
    assert r2["success"]
    final = yaml.safe_load(r2["output"])
    # Root may be list or dict depending on single-play unwrapping
    play = final[0] if isinstance(final, list) else final
    assert play["hosts"] == "webservers"
    assert play["become"] is True


# ── Terraform HCL ─────────────────────────────────────────────────────────────

requires_hcl = pytest.mark.skipif(not HAS_HCL, reason="python-hcl2 not installed")


def test_hcl_terraform_detects_as_hcl():
    assert detect_format(HCL_TERRAFORM) == "hcl"


@requires_hcl
def test_hcl_terraform_parse_resources():
    result = parse_text(HCL_TERRAFORM, "hcl")
    data = result["data"]
    assert "resource" in data


@requires_hcl
def test_hcl_terraform_parse_variables():
    result = parse_text(HCL_TERRAFORM, "hcl")
    data = result["data"]
    assert "variable" in data
    # python-hcl2 returns repeated blocks as a list of dicts
    vars_block = data["variable"]
    if isinstance(vars_block, list):
        var_names = [list(v.keys())[0] for v in vars_block if isinstance(v, dict)]
    else:
        var_names = list(vars_block.keys())
    assert "environment" in var_names


@requires_hcl
def test_hcl_terraform_to_json():
    r = convert(HCL_TERRAFORM, "json", "hcl")
    assert r["success"]
    data = json.loads(r["output"])
    assert isinstance(data, dict)


# ── Cross-format real-world conversions ────────────────────────────────────────

def test_k8s_deployment_to_toml_skipped_complex():
    """TOML does not support mixed-type arrays; YAML→TOML may fail for complex
    k8s manifests. Verify we get a graceful error or success — never a crash."""
    if not HAS_TOML:
        pytest.skip("tomllib not available")
    r = convert(K8S_DEPLOYMENT, "toml")
    # Either succeeds (simple structure handled) or returns a clear error
    assert "success" in r
    if not r["success"]:
        assert r.get("error") or r.get("message")


def test_docker_compose_to_json_schema_depth():
    """Nested Docker Compose configs (healthcheck.test as list) survive JSON
    conversion with correct types."""
    r = convert(DOCKER_COMPOSE, "json")
    assert r["success"]
    data = json.loads(r["output"])
    hc_test = data["services"]["db"]["healthcheck"]["test"]
    assert isinstance(hc_test, list)
    assert hc_test[0] == "CMD-SHELL"


def test_github_actions_boolean_values_preserved():
    """fail-fast: false must survive YAML → JSON → YAML as boolean False,
    not string 'false'."""
    rt = _yaml_json_yaml_roundtrip(GITHUB_ACTIONS)
    ff = rt["final"]["jobs"]["test"]["strategy"]["fail-fast"]
    assert ff is False, f"fail-fast should be False, got {ff!r}"


def test_k8s_deployment_integer_types_preserved():
    """replicas: 3 must remain integer through JSON conversion."""
    r = convert(K8S_DEPLOYMENT, "json")
    data = json.loads(r["output"])
    assert data["spec"]["replicas"] == 3
    assert isinstance(data["spec"]["replicas"], int)


def test_ansible_playbook_boolean_types_preserved():
    """become: true must remain bool through JSON conversion."""
    r = convert(ANSIBLE_PLAYBOOK, "json")
    data = json.loads(r["output"])
    assert data[0]["become"] is True


def test_docker_compose_internal_boolean_preserved():
    """networks.backend.internal: true must remain bool through roundtrip."""
    rt = _yaml_json_yaml_roundtrip(DOCKER_COMPOSE)
    assert rt["final"]["networks"]["backend"]["internal"] is True


def test_k8s_deployment_null_values_handled():
    """YAML with null/None values should parse and convert cleanly."""
    src = "apiVersion: v1\nkind: ConfigMap\ndata: null\nmetadata:\n  name: test\n"
    r = convert(src, "json")
    assert r["success"]
    data = json.loads(r["output"])
    assert data["data"] is None


# ── CLI operations on real-world configs ──────────────────────────────────────

def test_cli_grep_realworld_docker_network(tmp_path, capsys):
    f = tmp_path / "docker-compose.yaml"
    f.write_text(DOCKER_COMPOSE)
    from core.cli import main
    rc = main(["cf", str(f), "--grep", "bridge"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "bridge" in out


def test_cli_flatten_k8s_deployment(tmp_path, capsys):
    f = tmp_path / "deploy.yaml"
    f.write_text(K8S_DEPLOYMENT)
    from core.cli import main
    rc = main(["cf", str(f), "--flatten", "--to", "json"])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    # Flattened keys use dot notation
    flat_keys = list(data.keys())
    assert any("." in k for k in flat_keys)
    # Key data accessible
    assert any("replicas" in k for k in flat_keys)


def test_cli_validate_docker_compose(tmp_path, capsys):
    f = tmp_path / "docker-compose.yaml"
    f.write_text(DOCKER_COMPOSE)
    from core.cli import main
    rc = main(["cf", str(f), "--validate"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "valid" in out.lower() or "ok" in out.lower() or "✓" in out or "VALID" in out


def test_cli_count_github_actions(tmp_path, capsys):
    f = tmp_path / "ci.yml"
    f.write_text(GITHUB_ACTIONS)
    from core.cli import main
    # --count requires a PATH argument (counts array elements or keys)
    rc = main(["cf", str(f), "--count", "jobs"])
    out = capsys.readouterr().out
    assert rc == 0
    # jobs has 2 entries (test + lint)
    assert any(c.isdigit() for c in out)
