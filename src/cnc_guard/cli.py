"""Comandos de descarga y entrenamiento reproducibles."""

import argparse
import json
from pathlib import Path

from cnc_guard.data import download
from cnc_guard.registry import Registry
from cnc_guard.settings import Settings, project_root
from cnc_guard.training import train


def main() -> None:
    parser = argparse.ArgumentParser(description="CNC Guard - demo Erronka 1")
    parser.add_argument("command", choices=["download", "train", "demo", "prepare", "serve"])
    parser.add_argument("--dataset", choices=["ai4i", "nasa", "all"], default="ai4i")
    parser.add_argument("--root", type=Path, default=project_root())
    parser.add_argument("--data", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    settings = Settings(args.root.resolve())
    if args.command == "serve":
        import uvicorn

        from cnc_guard.api import create_app
        uvicorn.run(create_app(settings.root), host="127.0.0.1", port=8000)
        return
    registry = Registry(settings.artifacts)
    datasets = ["ai4i", "nasa"] if args.dataset == "all" else [args.dataset]
    for dataset in datasets:
        if args.command in {"download", "demo", "prepare"}:
            if dataset == "ai4i":
                metadata = download(args.data or settings.raw / "ai4i2020.csv")
            else:
                from cnc_guard import nasa
                metadata = nasa.download(settings.raw)
            print(json.dumps(metadata, indent=2))
        if args.command in {"train", "demo", "prepare"}:
            output = args.output or registry.new_run(dataset)
            if dataset == "ai4i":
                report = train(args.data or settings.raw / "ai4i2020.csv", output)
            else:
                from cnc_guard import nasa
                report = nasa.train(settings.raw, settings.processed, output)
            if not args.output:
                manifest = registry.activate(dataset, output)
                from cnc_guard.storage import Store
                Store(settings.database).register_model(manifest)
            print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
