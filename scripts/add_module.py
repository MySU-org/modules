#!/usr/bin/env python3
# Script: add_module.py
# Author: kelexine <https://github.com/kelexine>
# Date: 2026-10-20
# Purpose: All-in-one automation script to build, package, release, catalog, and commit MySU modules.
# Usage: ./scripts/add_module.py --path <path_to_module_project> [--build] [--no-commit] [--no-release]

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def get_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def parse_module_prop(prop_path: Path) -> Dict[str, str]:
    """Parse a module.prop key-value file."""
    if not prop_path.exists():
        raise FileNotFoundError(f"module.prop not found at {prop_path}")

    props: Dict[str, str] = {}
    with open(prop_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                props[k.strip()] = v.strip()
    return props


def find_prop_in_tree(module_path: Path) -> Optional[Path]:
    """Search for module.prop in the module directory tree."""
    candidates = [
        module_path / "module.prop",
        module_path / "metamodule" / "module.prop",
        module_path / "target" / "module" / "module.prop",
        module_path / "src" / "module.prop",
    ]
    for c in candidates:
        if c.exists():
            return c

    # Recursive fallback
    for p in module_path.rglob("module.prop"):
        if "target" not in p.parts or "target/module" in str(p):
            return p
    return None


def clean_version(version: str) -> str:
    """Normalize version string by stripping leading v."""
    return version.lstrip("v")


def load_catalog(catalog_path: Path) -> List[Dict[str, Any]]:
    if not catalog_path.exists():
        return []
    with open(catalog_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_catalog(catalog_path: Path, data: List[Dict[str, Any]]) -> None:
    with open(catalog_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def build_module_zip(module_path: Path) -> Path:
    """Build or locate flashable zip from module path."""
    build_sh = module_path / "build.sh"
    if build_sh.exists() and os.access(build_sh, os.X_OK | os.R_OK):
        print(f"[*] Executing {build_sh}...")
        subprocess.run(["bash", str(build_sh)], cwd=str(module_path), check=True)

    # Search for built zip files in target/ or root
    zips: List[Path] = []
    target_dir = module_path / "target"
    if target_dir.exists():
        zips.extend(target_dir.glob("*.zip"))
    zips.extend(module_path.glob("*.zip"))

    # Filter out temp/partial zips
    valid_zips = [z for z in zips if not z.name.startswith(".")]
    if valid_zips:
        # Sort by modification time, most recent first
        valid_zips.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return valid_zips[0]

    # If no zip and target/module or module dir exists, create zip
    staging_dir = target_dir / "module" if (target_dir / "module").exists() else module_path
    if (staging_dir / "module.prop").exists():
        out_target = target_dir if target_dir.exists() else module_path
        out_zip = out_target / f"{module_path.name}.zip"
        print(f"[*] Packaging directory {staging_dir} into {out_zip}...")
        shutil.make_archive(str(out_zip.with_suffix("")), "zip", str(staging_dir))
        return out_zip

    raise RuntimeError(f"Could not build or locate a valid .zip in {module_path}")


def create_module_detail(
    module_id: str,
    module_name: str,
    summary: str,
    author: str,
    version: str,
    version_code: int,
    now_iso: str,
    tag_name: str,
    dl_url: str,
    zip_size: int,
    readme_text: Optional[str] = None,
) -> Dict[str, Any]:
    """Create the module detail JSON structure."""
    if not readme_text:
        readme_text = f"""# {module_name}

{summary}

## 📥 Installation

1. Download the latest release from the Releases section.
2. Install via MySU Manager **OR** via CLI:

```bash
adb push {module_id}-v{clean_version(version)}.zip /sdcard/
adb shell su -c 'mysud module install /sdcard/{module_id}-v{clean_version(version)}.zip'
```

3. Reboot your device.

## 👥 Credits & Acknowledgements

* **Author:** {author}
"""

    return {
        "moduleId": module_id,
        "moduleName": module_name,
        "readme": readme_text,
        "readmeHTML": f"<pre>{readme_text}</pre>",
        "homepageUrl": f"https://github.com/MySU-org/{module_id}",
        "sourceUrl": f"https://github.com/MySU-org/{module_id}",
        "url": f"https://github.com/MySU-org/{module_id}",
        "latestRelease": {
            "version": f"v{clean_version(version)}",
            "versionCode": version_code,
            "time": now_iso,
            "downloadUrl": dl_url,
        },
        "releases": [
            {
                "name": f"{module_name} v{clean_version(version)}",
                "tagName": tag_name,
                "publishedAt": now_iso,
                "descriptionHTML": f"<h3>{module_name} v{clean_version(version)} for MySU</h3><p>{summary}</p>",
                "releaseAssets": [
                    {
                        "name": f"{module_id}-v{clean_version(version)}.zip",
                        "downloadUrl": dl_url,
                        "size": zip_size,
                        "downloadCount": 0,
                    }
                ],
            }
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="All-in-one MySU module packager, release publisher, and catalog updater."
    )
    parser.add_argument("-p", "--path", type=Path, help="Path to module project directory")
    parser.add_argument("--id", help="Module ID (overrides module.prop)")
    parser.add_argument("--name", help="Module display name (overrides module.prop)")
    parser.add_argument("--author", help="Author name (overrides module.prop)")
    parser.add_argument("--summary", help="Summary text (overrides module.prop)")
    parser.add_argument("--version", help="Version string (overrides module.prop)")
    parser.add_argument("--version-code", type=int, help="Version code (overrides module.prop)")
    parser.add_argument("--metamodule", action="store_true", help="Force mark as metamodule")
    parser.add_argument("--zip", type=Path, help="Explicit path to flashable zip file")
    parser.add_argument("--build", action="store_true", help="Trigger build script in module path")
    parser.add_argument(
        "--no-release", action="store_true", help="Do not create/update GitHub release"
    )
    parser.add_argument(
        "--no-commit", action="store_true", help="Do not create git commit after updating"
    )

    args = parser.parse_args()
    root = get_repo_root()
    catalog_path = root / "modules.json"
    catalog = load_catalog(catalog_path)

    prop_data: Dict[str, str] = {}
    readme_content: Optional[str] = None

    if args.path:
        module_dir = args.path.resolve()
        if not module_dir.is_dir():
            print(f"Error: {module_dir} is not a directory!", file=sys.stderr)
            return 1

        prop_file = find_prop_in_tree(module_dir)
        if prop_file:
            print(f"[*] Found module.prop at {prop_file}")
            prop_data = parse_module_prop(prop_file)

        readme_file = module_dir / "README.md"
        if readme_file.exists():
            readme_content = readme_file.read_text(encoding="utf-8")

    # Resolve metadata fields
    module_id = args.id or prop_data.get("id")
    if not module_id:
        print("Error: Module ID not found. Specify --id or provide a valid module.prop", file=sys.stderr)
        return 1

    module_name = args.name or prop_data.get("name", module_id)
    author = args.author or prop_data.get("author", "kelexine")
    summary = args.summary or prop_data.get("description", f"{module_name} for MySU")
    version_str = args.version or prop_data.get("version", "1.0.0")
    ver_clean = clean_version(version_str)

    version_code_raw = args.version_code or prop_data.get("versionCode", 1000)
    try:
        version_code = int(version_code_raw)
    except ValueError:
        version_code = 1000

    is_metamodule = (
        args.metamodule
        or prop_data.get("metamodule") in ("1", "true", "True")
        or "meta" in module_id.lower()
    )

    print(f"=== MySU Module Processor: {module_name} ({module_id}) ===")
    print(f"• Version: v{ver_clean} (Code: {version_code})")
    print(f"• Author: {author}")
    print(f"• Metamodule: {is_metamodule}")
    print(f"• Summary: {summary}")

    # Resolve or build flashable zip
    zip_path: Optional[Path] = args.zip
    if not zip_path and args.path:
        if args.build or not (args.path / "target").exists():
            zip_path = build_module_zip(args.path)
        else:
            # Look for existing zip
            try:
                zip_path = build_module_zip(args.path)
            except RuntimeError:
                pass

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tag_name = f"{module_id}-v{ver_clean}"
    target_asset_name = f"{module_id}-v{ver_clean}.zip"
    dl_url = f"https://github.com/MySU-org/modules/releases/download/{tag_name}/{target_asset_name}"
    zip_size = 0

    # Handle GitHub release creation
    if not args.no_release and zip_path and zip_path.exists():
        zip_size = zip_path.stat().st_size
        print(f"[*] Preparing release {tag_name} with asset {zip_path.name} ({zip_size} bytes)...")

        # Ensure asset is copied with canonical name for upload
        canonical_zip = zip_path.parent / target_asset_name
        if canonical_zip != zip_path:
            shutil.copy2(zip_path, canonical_zip)

        # Check if release already exists
        check_proc = subprocess.run(
            ["gh", "release", "view", tag_name, "-R", "MySU-org/modules"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        if check_proc.returncode == 0:
            print(f"[*] Release {tag_name} already exists. Uploading/overwriting asset...")
            subprocess.run(
                [
                    "gh", "release", "upload", tag_name, str(canonical_zip),
                    "-R", "MySU-org/modules", "--clobber",
                ],
                check=True,
            )
        else:
            print(f"[*] Creating new GitHub release {tag_name}...")
            subprocess.run(
                [
                    "gh", "release", "create", tag_name, str(canonical_zip),
                    "-R", "MySU-org/modules",
                    "--title", f"{module_name} v{ver_clean}",
                    "--notes", f"{summary}\n\nNatively ported for MySU.",
                ],
                check=True,
            )
        print(f"[✓] Release published: {dl_url}")

    # Authors list
    authors_list = [
        {"name": a.strip(), "link": f"https://github.com/{a.strip()}"}
        for a in author.split(",")
    ]

    # Update or insert into catalog
    entry = None
    for item in catalog:
        if item.get("moduleId") == module_id:
            entry = item
            break

    if entry is None:
        entry = {
            "moduleId": module_id,
            "moduleName": module_name,
            "authors": authors_list,
            "summary": summary,
            "metamodule": is_metamodule,
            "stargazerCount": 1,
            "updatedAt": now_iso,
            "createdAt": now_iso,
            "latestRelease": {
                "version": f"v{ver_clean}",
                "versionCode": version_code,
                "time": now_iso,
                "downloadUrl": dl_url,
            },
        }
        catalog.append(entry)
    else:
        entry["moduleName"] = module_name
        entry["summary"] = summary
        entry["metamodule"] = is_metamodule
        entry["updatedAt"] = now_iso
        entry["latestRelease"] = {
            "version": f"v{ver_clean}",
            "versionCode": version_code,
            "time": now_iso,
            "downloadUrl": dl_url,
        }

    save_catalog(catalog_path, catalog)
    print(f"[✓] Updated catalog at {catalog_path}")

    # Generate module detail JSON
    detail_dir = root / "modules"
    detail_dir.mkdir(parents=True, exist_ok=True)
    detail_path = detail_dir / f"{module_id}.json"

    detail_data = create_module_detail(
        module_id=module_id,
        module_name=module_name,
        summary=summary,
        author=author,
        version=ver_clean,
        version_code=version_code,
        now_iso=now_iso,
        tag_name=tag_name,
        dl_url=dl_url,
        zip_size=zip_size,
        readme_text=readme_content,
    )

    with open(detail_path, "w", encoding="utf-8") as f:
        json.dump(detail_data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"[✓] Updated module manifest at {detail_path}")

    # Git commit
    if not args.no_commit:
        git_status = subprocess.run(
            ["git", "status", "--porcelain", "modules.json", str(detail_path)],
            cwd=str(root),
            capture_output=True,
            text=True,
        )
        if git_status.stdout.strip():
            print("[*] Staging and creating git commit...")
            subprocess.run(["git", "add", "modules.json", str(detail_path)], cwd=str(root), check=True)
            commit_subject = f"feat(catalog): register {module_name} v{ver_clean}"
            commit_body = (
                f"Registers and updates {module_name} ({module_id}) v{ver_clean} in the MySU module catalog.\n\n"
                f"- modules.json: update catalog entry with release v{ver_clean} metadata\n"
                f"- modules/{module_id}.json: update manifest details and assets\n\n"
                "Signed-off-by: kelexine <frankiekelechi@gmail.com>"
            )
            subprocess.run(
                ["git", "commit", "-m", commit_subject, "-m", commit_body],
                cwd=str(root),
                check=True,
            )
            print("[✓] Committed successfully! You can now run:")
            print("    git push origin main")
        else:
            print("[*] No catalog changes to commit.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
