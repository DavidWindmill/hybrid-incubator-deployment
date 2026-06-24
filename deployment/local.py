from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import yaml

from deployment.config import dependencies, service_map, topological_order
from deployment.sources import resolve_local_source, run


def workspace_for(spec_path: Path) -> Path:
    root = spec_path.parents[1]
    workspace = root / ".deployment"
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def build_images(spec: dict[str, Any], spec_path: Path, workspace: Path) -> dict[str, str]:
    images: dict[str, str] = {}
    built: set[str] = set()
    source_cache: dict[str, Path] = {}

    for service in spec["services"]:
        deployment = service["deployment"]
        image_name = deployment["image_name"]
        image_tag = f"{image_name}:local"
        images[service["id"]] = image_tag
        if image_name in built:
            continue
        source_repr = str(service["source"])
        source_dir = source_cache.get(source_repr)
        if source_dir is None:
            source_dir = resolve_local_source(
                service["source"], spec_path=spec_path, workspace=workspace
            )
            source_cache[source_repr] = source_dir
        dockerfile = service["source"].get("dockerfile", "Dockerfile")
        run([
            "docker", "build", "-f", str(source_dir / dockerfile),
            "-t", image_tag, str(source_dir),
        ])
        built.add(image_name)
    return images


def render_environment(
    service: dict[str, Any], services: dict[str, dict[str, Any]]
) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in service.get("environment", {}).items():
        if isinstance(value, dict) and "from_service" in value:
            target = services[value["from_service"]]
            target_name = target["deployment"]["service_name"]
            result[key] = f"http://{target_name}:8080"
        else:
            result[key] = str(value)
    result.setdefault("PORT", "8080")
    return result


def generate_compose(
    spec: dict[str, Any], images: dict[str, str], workspace: Path
) -> Path:
    services_by_id = service_map(spec)
    compose_services: dict[str, Any] = {}
    for service_id in topological_order(spec):
        service = services_by_id[service_id]
        deployment = service["deployment"]
        name = deployment["service_name"]
        entry: dict[str, Any] = {
            "image": images[service_id],
            "environment": render_environment(service, services_by_id),
            "restart": "unless-stopped",
            "healthcheck": {
                "test": [
                    "CMD", "python", "-c",
                    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3)",
                ],
                "interval": "5s",
                "timeout": "4s",
                "retries": 30,
                "start_period": "20s",
            },
        }
        public_port = deployment.get("public_port")
        if public_port:
            entry["ports"] = [f"{public_port}:8080"]
        deps = dependencies(service)
        if deps:
            entry["depends_on"] = {
                services_by_id[dep]["deployment"]["service_name"]: {
                    "condition": "service_healthy"
                }
                for dep in sorted(deps)
            }
        compose_services[name] = entry

    compose = {
        "name": spec["application"]["id"],
        "services": compose_services,
    }
    compose_path = workspace / "compose.generated.yaml"
    compose_path.write_text(
        yaml.safe_dump(compose, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return compose_path


def write_outputs(spec: dict[str, Any], workspace: Path) -> Path:
    services = service_map(spec)
    lines: list[str] = []
    for name, service_id in spec.get("outputs", {}).items():
        service = services[service_id]
        port = service["deployment"].get("public_port")
        if not port:
            continue
        lines.append(f"{name}=http://127.0.0.1:{port}")
    path = workspace / "deployment.env"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def up(spec: dict[str, Any], spec_path: Path) -> Path:
    workspace = workspace_for(spec_path)
    images = build_images(spec, spec_path, workspace)
    compose_path = generate_compose(spec, images, workspace)
    run([
        "docker", "compose", "-f", str(compose_path),
        "up", "--detach", "--wait", "--wait-timeout", "300",
    ])
    env_path = write_outputs(spec, workspace)
    print(f"Servicios iniciados. URLs: {env_path}")
    return env_path


def compose_command(spec_path: Path, arguments: list[str]) -> None:
    workspace = workspace_for(spec_path)
    compose_path = workspace / "compose.generated.yaml"
    if not compose_path.exists():
        raise FileNotFoundError("No existe compose.generated.yaml. Ejecuta primero up.")
    run(["docker", "compose", "-f", str(compose_path), *arguments])


def down(spec_path: Path) -> None:
    compose_command(spec_path, ["down", "--remove-orphans"])


def status(spec_path: Path) -> None:
    compose_command(spec_path, ["ps"])


def logs(spec_path: Path, follow: bool = False) -> None:
    args = ["logs"]
    if follow:
        args.append("--follow")
    compose_command(spec_path, args)
