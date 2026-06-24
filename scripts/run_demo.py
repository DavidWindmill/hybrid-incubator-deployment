from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx


def load_env_file(path: str | None) -> None:
    if not path:
        return
    env_path = Path(path)
    if not env_path.exists():
        raise FileNotFoundError(f"No existe el archivo de URLs: {env_path}")
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def wait_for_health(client: httpx.Client, name: str, url: str, attempts: int = 30) -> None:
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            response = client.get(f"{url}/health")
            response.raise_for_status()
            print(f"[OK] {name}: {response.json()}")
            return
        except (httpx.HTTPError, ValueError) as exc:
            last_error = exc
            time.sleep(2)
    raise RuntimeError(f"{name} no responde correctamente en {url}: {last_error}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ejecuta una demostración completa de la incubadora híbrida."
    )
    parser.add_argument("--env-file", help="Archivo KEY=VALUE generado por el despliegue.")
    parser.add_argument("--anomaly-index", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=180.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_env_file(args.env_file)

    urls = {
        "aggregator": os.getenv("AGGREGATOR_URL", "http://127.0.0.1:8000"),
        "detector": os.getenv("DETECTOR_URL", "http://127.0.0.1:8001"),
        "sensor-left": os.getenv("SENSOR_LEFT_URL", "http://127.0.0.1:8101"),
        "sensor-center": os.getenv("SENSOR_CENTER_URL", "http://127.0.0.1:8102"),
        "sensor-right": os.getenv("SENSOR_RIGHT_URL", "http://127.0.0.1:8103"),
    }
    sensor_order = [
        urls["sensor-left"],
        urls["sensor-center"],
        urls["sensor-right"],
        urls["sensor-left"],
        urls["sensor-center"],
        urls["sensor-right"],
        urls["sensor-left"],
        urls["sensor-center"],
    ]

    if not 0 <= args.anomaly_index < len(sensor_order):
        raise ValueError("El índice anómalo debe estar entre 0 y 7.")

    with httpx.Client(timeout=args.timeout, trust_env=False) as client:
        for name, url in urls.items():
            wait_for_health(client, name, url)

        reset = client.post(f"{urls['aggregator']}/reset")
        reset.raise_for_status()
        print("[OK] Agregador reiniciado")

        final_payload: dict[str, object] | None = None
        for index, sensor_url in enumerate(sensor_order):
            body = {
                "force_anomaly": index == args.anomaly_index,
                "anomaly_direction": "high",
            }
            response = client.post(f"{sensor_url}/emit", json=body)
            if response.is_error:
                print(f"[ERROR] índice={index} status={response.status_code}")
                print(response.text)
                response.raise_for_status()
            payload = response.json()
            reading = payload["reading"]
            aggregator = payload["aggregator"]
            print(
                f"indice={index} sensor={reading['sensor_id']} zona={reading['zone']} "
                f"temperatura={reading['temperature_c']} C "
                f"estado={aggregator['status']}"
            )
            if aggregator["status"] == "batch_processed":
                final_payload = aggregator

        if final_payload is None:
            raise RuntimeError("El agregador no procesó el lote de ocho lecturas.")

        detection = final_payload["detection"]
        expected_state = format(args.anomaly_index, "03b")
        if detection["detected_index"] != args.anomaly_index:
            raise AssertionError(
                f"Índice incorrecto: esperado={args.anomaly_index}, "
                f"obtenido={detection['detected_index']}"
            )
        if detection["measured_state"] != expected_state:
            raise AssertionError(
                f"Estado incorrecto: esperado={expected_state}, "
                f"obtenido={detection['measured_state']}"
            )

        print("\n[OK] Demostración completada")
        print(json.dumps(detection, ensure_ascii=False, indent=2))
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[FALLO] {exc}", file=sys.stderr)
        raise
