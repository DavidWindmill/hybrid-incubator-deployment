from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class SpecificationError(ValueError):
    pass


def load_spec(path: str | Path) -> tuple[dict[str, Any], Path]:
    spec_path = Path(path).resolve()
    if not spec_path.exists():
        raise SpecificationError(f"No existe la especificacion: {spec_path}")
    data = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SpecificationError("La especificacion debe ser un objeto YAML.")
    validate_spec(data)
    return data, spec_path


def service_map(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {service["id"]: service for service in spec["services"]}


def dependencies(service: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for value in service.get("environment", {}).values():
        if isinstance(value, dict) and "from_service" in value:
            result.add(value["from_service"])
    return result


def topological_order(spec: dict[str, Any]) -> list[str]:
    services = service_map(spec)
    remaining = {key: dependencies(value) for key, value in services.items()}
    ordered: list[str] = []
    while remaining:
        ready = sorted(key for key, deps in remaining.items() if not deps)
        if not ready:
            raise SpecificationError("Existe un ciclo entre las dependencias de servicios.")
        for key in ready:
            ordered.append(key)
            remaining.pop(key)
        for deps in remaining.values():
            deps.difference_update(ready)
    return ordered


def validate_spec(spec: dict[str, Any]) -> None:
    if not isinstance(spec.get("application"), dict):
        raise SpecificationError("Falta la seccion application.")
    services = spec.get("services")
    if not isinstance(services, list) or not services:
        raise SpecificationError("services debe ser una lista no vacia.")

    ids: set[str] = set()
    deployment_names: set[str] = set()
    for service in services:
        if not isinstance(service, dict):
            raise SpecificationError("Cada servicio debe ser un objeto.")
        for field in ("id", "source", "deployment"):
            if field not in service:
                raise SpecificationError(f"El servicio carece de {field}.")
        service_id = service["id"]
        if service_id in ids:
            raise SpecificationError(f"ID de servicio duplicado: {service_id}")
        ids.add(service_id)

        deployment = service["deployment"]
        for field in ("service_name", "image_name"):
            if field not in deployment:
                raise SpecificationError(f"{service_id}.deployment carece de {field}.")
        name = deployment["service_name"]
        if name in deployment_names:
            raise SpecificationError(f"service_name duplicado: {name}")
        deployment_names.add(name)

        source = service["source"]
        if not source.get("local_path") and not source.get("repository"):
            raise SpecificationError(
                f"{service_id}.source necesita local_path o repository."
            )

    for service in services:
        for dependency in dependencies(service):
            if dependency not in ids:
                raise SpecificationError(
                    f"{service['id']} referencia un servicio inexistente: {dependency}"
                )

    outputs = spec.get("outputs", {})
    if not isinstance(outputs, dict):
        raise SpecificationError("outputs debe ser un objeto.")
    for env_name, service_id in outputs.items():
        if service_id not in ids:
            raise SpecificationError(
                f"La salida {env_name} referencia un servicio inexistente: {service_id}"
            )

    topological_order(spec)
