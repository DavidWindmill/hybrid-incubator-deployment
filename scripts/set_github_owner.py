from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("owner", help="Usuario u organizacion de GitHub")
    parser.add_argument(
        "--file",
        default="specifications/application.cloud.yaml",
    )
    args = parser.parse_args()
    path = Path(args.file)
    content = path.read_text(encoding="utf-8")
    content = content.replace("GITHUB_OWNER", args.owner)
    path.write_text(content, encoding="utf-8")
    print(f"Actualizado {path} con owner={args.owner}")


if __name__ == "__main__":
    main()
