#!/usr/bin/env python3
# Script: add_module.py
# Author: kelexine <https://github.com/kelexine>
# Date: 2026-09-14
# Purpose: Helper script to register or update ported modules in MySU module repository.
# Usage: ./scripts/add_module.py --id <id> --name <name> --summary <summary> --version <version> --version-code <code> --zip <path_to_zip>

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def get_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_catalog(catalog_path: Path) -> List[Dict[str, Any]]:
    if not catalog_path.exists():
        return []
    with open(catalog_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_catalog(catalog_path: Path, data: List[Dict[str, Any]]) -> None:
    with open(catalog_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Register or update a module in MySU modules index.")
    parser.add_argument("--id", required=True, help="Module ID (e.g. encore)")
    parser.add_argument("--name", required=True, help="Module display name")
    parser.add_argument("--author", default="kelexine", help="Author name or comma-separated names")
    parser.add_argument("--summary", required=True, help="Short summary")
    parser.add_argument("--version", required=True, help="Version string (e.g. 5.2.1-mysu)")
    parser.add_argument("--version-code", type=int, required=True, help="Version code")
    parser.add_argument("--zip", type=Path, help="Path to flashable zip to release with gh")
    parser.add_argument("--gh-release", action="store_true", help="Create GitHub release using gh CLI")

    args = parser.parse_args()
    root = get_repo_root()
    catalog_path = root / "modules.json"
    catalog = load_catalog(catalog_path)

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tag_name = f"{args.id}-v{args.version}"
    dl_url = f"https://github.com/MySU-org/modules/releases/download/{tag_name}/{args.id}-v{args.version}.zip"

    if args.zip and args.gh_release:
        if not args.zip.exists():
            print(f"Error: zip file {args.zip} not found!", file=sys.stderr)
            return 1
        print(f"Creating GitHub release {tag_name}...")
        subprocess.run(
            [
                "gh", "release", "create", tag_name, str(args.zip),
                "-R", "MySU-org/modules",
                "--title", f"{args.name} v{args.version}",
                "--notes", f"{args.summary}\n\nNatively ported for MySU."
            ],
            check=True
        )

    # Authors parsing
    authors_list = [{"name": a.strip(), "link": f"https://github.com/{a.strip()}"} for a in args.author.split(",")]

    entry = None
    for item in catalog:
        if item.get("moduleId") == args.id:
            entry = item
            break

    if entry is None:
        entry = {
            "moduleId": args.id,
            "moduleName": args.name,
            "authors": authors_list,
            "summary": args.summary,
            "metamodule": False,
            "stargazerCount": 1,
            "updatedAt": now_iso,
            "createdAt": now_iso,
            "latestRelease": {
                "version": f"v{args.version}" if not args.version.startswith("v") else args.version,
                "versionCode": args.version_code,
                "time": now_iso,
                "downloadUrl": dl_url
            }
        }
        catalog.append(entry)
    else:
        entry["moduleName"] = args.name
        entry["summary"] = args.summary
        entry["updatedAt"] = now_iso
        entry["latestRelease"] = {
            "version": f"v{args.version}" if not args.version.startswith("v") else args.version,
            "versionCode": args.version_code,
            "time": now_iso,
            "downloadUrl": dl_url
        }

    save_catalog(catalog_path, catalog)
    print(f"Updated catalog {catalog_path} with module {args.id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
