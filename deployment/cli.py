from __future__ import annotations

import argparse

from deployment.cloud import cloud_up
from deployment.config import load_spec, topological_order
from deployment.local import down, logs, status, up


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Desplegador de la incubadora híbrida")
    sub = root.add_subparsers(dest="command", required=True)

    for name in ("validate", "up", "down", "status", "logs"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--spec", required=True)
        if name == "logs":
            cmd.add_argument("--follow", action="store_true")

    cloud = sub.add_parser("cloud-up")
    cloud.add_argument("--spec", required=True)
    cloud.add_argument("--project", required=True)
    cloud.add_argument("--region", default="europe-southwest1")
    cloud.add_argument("--artifact-repository", default="incubadora-quantum")
    cloud.add_argument("--runtime-service-account")
    return root


def main() -> None:
    args = parser().parse_args()
    spec, spec_path = load_spec(args.spec)

    if args.command == "validate":
        print("Especificacion valida.")
        print("Orden de despliegue:", " -> ".join(topological_order(spec)))
    elif args.command == "up":
        up(spec, spec_path)
    elif args.command == "down":
        down(spec_path)
    elif args.command == "status":
        status(spec_path)
    elif args.command == "logs":
        logs(spec_path, args.follow)
    elif args.command == "cloud-up":
        cloud_up(
            spec,
            spec_path,
            project=args.project,
            region=args.region,
            artifact_repository=args.artifact_repository,
            runtime_service_account=args.runtime_service_account,
        )


if __name__ == "__main__":
    main()
