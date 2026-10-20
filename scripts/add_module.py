#!/usr/bin/env python3
# Script: add_module.py
# Author: kelexine <https://github.com/kelexine>
# Date: 2026-09-14
# Purpose: Helper script to register or update ported modules in MySU module repository.
# Usage: ./scripts/add_module.py --id <id> --name <name> --summary <summary> --version <version> --version-code <code> --zip <path_to_zip> [--module-path <path_to_module_source>]

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


def create_module_detail(args: argparse.Namespace, now_iso: str, tag_name: str, dl_url: str) -> Dict[str, Any]:
    """Create the module detail JSON structure."""
    # Determine if we should try to read the actual README from module source
    readme_content = f"""# {args.name}

{args.summary}

## ✨ Key Features

* Feature information would be here when available from module source.

## 📥 Installation

1. Download the latest release from the Releases section.
2. Install via KernelSU Manager **OR** via ADB:

```bash
adb push {args.id}-v{args.version}.zip /sdcard/
adb shell su -c 'mysud module install /sdcard/{args.id}-v{args.version}.zip'
```

3. Reboot.

## 👥 Credits & Acknowledgements

* **Author:** {args.author}

## 📄 License
Distribution
Licensed under **GPL-3.0**."""

    # Simple HTML version - in a real implementation, you'd convert markdown to HTML properly
    readme_html = f"""<h1>{args.name}</h1>
<p>{args.summary}</p>
<h2>✨ Key Features</h2>
<ul>
<li>Feature information would be here when available from module source.</li>
</ul>
<h2>📥 Installation</h2>
<ol>
<li>Download the latest release from the Releases section.</li>
<li>Install via KernelSU Manager <strong>OR</strong> via ADB:</li>
</ol>
<pre><code>adb push {args.id}-v{args.version}.zip /sdcard/
adb shell su -c 'mysud module install /sdcard/{args.id}-v{args.version}.zip'
</code></pre>
<ol start="3">
<li>Reboot.</li>
</ol>
<h2>👥 Credits & Acknowledgements</h2>
<ul>
<li><strong>Author:</strong> {args.author}</li>
</ul>
<h2>📄 License</h2>
<p>Distribution<br>
Licensed under <strong>GPL-3.0</strong>.</p>"""

    # Try to get the actual README if module path is provided and exists
    # This is optional enhancement for future
    module_path = getattr(args, 'module_path', None)
    if module_path:
        readme_path = Path(module_path) / "README.md"
        if readme_path.exists():
            try:
                readme_content = readme_path.read_text(encoding="utf-8")
                # For HTML, we'd ideally use a markdown converter, but for now use simple wrapping
                readme_html = f"<pre>{readme_content}</pre>"  # Simplistic
            except Exception as e:
                print(f"Warning: Could not read README from {readme_path}: {e}", file=sys.stderr)

    return {
        "moduleId": args.id,
        "moduleName": args.name,
        "readme": readme_content,
        "readmeHTML": readme_html,
        "homepageUrl": f"https://github.com/MySU-org/{args.id}",
        "sourceUrl": f"https://github.com/MySU-org/{args.id}",
        "url": f"https://github.com/MySU-org/{args.id}",
        "latestRelease": {
            "version": f"v{args.version}" if not args.version.startswith("v") else args.version,
            "versionCode": args.version_code,
            "time": now_iso,
            "downloadUrl": dl_url
        },
        "releases": [
            {
                "name": f"{args.name} v{args.version}",
                "tagName": tag_name,
                "publishedAt": now_iso,
                "descriptionHTML": f"<h3>{args.name} v{args.version} for MySU</h3><p>{args.summary}</p>",
                "releaseAssets": [
                    {
                        "name": f"{args.id}-v{args.version}.zip",
                        "downloadUrl": dl_url,
                        "size": 0,  # Will be updated if we have the actual file
                        "downloadCount": 0
                    }
                ]
            }
        ]
    }


def save_module_detail(detail_path: Path, data: Dict[str, Any]) -> None:
    """Save the module detail JSON file."""
    with open(detail_path, "w", encoding="utf-8") as f:
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
    parser.add_argument("--module-path", type=Path, help="Path to module source directory (for README)")

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
        # Update the asset size in the release data if we have the file
        # Note: This would require updating the detail data after creation, but we'll keep it simple for now

    # Authors parsing
    authors_list = [{"name": a.strip(), "link": f"https://github.com/{a.strip()}"} for a in args.author.split(",")]

    # Create or update catalog entry
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

    # Create or update module detail file
    detail_path = root / "modules" / f"{args.id}.json"
    detail_data = create_module_detail(args, now_iso, tag_name, dl_url)
    
    # If we have the actual zip file, update the size in the release data
    if args.zip and args.zip.exists():
        detail_data["releases"][0]["releaseAssets"][0]["size"] = args.zip.stat().st_size
    
    save_module_detail(detail_path, detail_data)
    print(f"Updated module detail {detail_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
