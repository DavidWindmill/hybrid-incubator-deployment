from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from deployment.config import service_map, topological_order
from deployment.sources import resolve_cloud_source, run


def capture(command: list[str]) -> str:
    print("+", " ".join(command), flush=True)
    return subprocess.check_output(command, text=True).strip()


def safe_tag(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.-]", "-", value)
    return clean[:100] or "latest"


def cloud_up(
    spec: dict[str, Any],
    spec_path: Path,
    *,
    project: str,
    region: str,
    artifact_repository: str,
    runtime_service_account: str | None = None,
) -> Path:
    root = spec_path.parents[1]
    workspace = root / ".deployment" / "cloud"
    workspace.mkdir(parents=True, exist_ok=True)

    services = service_map(spec)
    image_uris: dict[str, str] = {}
    image_by_name: dict[str, str] = {}

    for service in spec["services"]:
        image_name = service["deployment"]["image_name"]
        if image_name in image_by_name:
            image_uris[service["id"]] = image_by_name[image_name]
            continue
        source_dir = resolve_cloud_source(service["source"], workspace=workspace)
        revision = service["source"].get("revision", "main")
        try:
            commit = capture(["git", "-C", str(source_dir), "rev-parse", "--short=12", "HEAD"])
        except subprocess.CalledProcessError:
            commit = safe_tag(revision)
        image_uri = (
            f"{region}-docker.pkg.dev/{project}/{artifact_repository}/"
            f"{image_name}:{safe_tag(commit)}"
        )
        dockerfile = service["source"].get("dockerfile", "Dockerfile")
        run([
            "gcloud", "builds", "submit", str(source_dir),
            "--project", project,
            "--region", region,
            "--tag", image_uri,
            "--quiet",
        ])
        image_by_name[image_name] = image_uri
        image_uris[service["id"]] = image_uri

    urls: dict[str, str] = {}
    for service_id in topological_order(spec):
        service = services[service_id]
        deployment = service["deployment"]
        environment: dict[str, str] = {}
        for key, value in service.get("environment", {}).items():
            if isinstance(value, dict) and "from_service" in value:
                environment[key] = urls[value["from_service"]]
            else:
                environment[key] = str(value)
        # Cloud Run inyecta PORT automáticamente.
        reserved_env = {
            "PORT",
            "K_SERVICE",
            "K_REVISION",
            "K_CONFIGURATION",
        }
        environment = {
            key: value
            for key, value in environment.items()
            if key not in reserved_env
        }

        command = [
            "gcloud", "run", "deploy", deployment["service_name"],
            "--project", project,
            "--region", region,
            "--platform", "managed",
            "--image", image_uris[service_id],
            "--port", "8080",
            "--cpu", str(deployment.get("cpu", "1")),
            "--memory", str(deployment.get("memory", "512Mi")),
            "--min-instances", str(deployment.get("min_instances", 0)),
            "--max-instances", str(deployment.get("max_instances", 1)),
            "--concurrency", str(deployment.get("concurrency", 80)),
            "--quiet",
        ]

        if environment:
            command.extend([
                "--set-env-vars",
                ",".join(f"{k}={v}" for k, v in environment.items()),
            ])
        if deployment.get("public", True):
            command.append("--allow-unauthenticated")
        else:
            command.append("--no-allow-unauthenticated")
        if runtime_service_account:
            command.extend(["--service-account", runtime_service_account])
        run(command)
        url = capture([
            "gcloud", "run", "services", "describe", deployment["service_name"],
            "--project", project,
            "--region", region,
            "--format=value(status.url)",
        ])
        urls[service_id] = url
        print(f"[OK] {service_id}: {url}")

    output_lines = [
        f"{name}={urls[service_id]}"
        for name, service_id in spec.get("outputs", {}).items()
    ]
    output_path = root / ".deployment" / "cloud-deployment.env"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(output_lines) + "\n", encoding="utf-8")
    print(f"Despliegue completado. URLs: {output_path}")
    return output_path
