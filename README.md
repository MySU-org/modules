# MySU Modules Repository

> Official self-hosted module catalog and distribution index for MySU.

## What is this?
A central, self-hosted distribution index and release host for modules running natively on the **MySU** root ecosystem (`window.mysu`, `@mysu-org/mysu`). It provides catalog metadata consumed by the MySU Android Manager's module repository tab with zero reliance on legacy or external infrastructure.

## Features
- **Pure MySU native execution**: Modules communicate directly with `/data/adb/mysu/bin` and `window.mysu`.
- **Self-hosted catalog**: Manifests (`modules.json`) and detail specs (`modules/<moduleId>.json`) hosted directly on GitHub.
- **Automated validation**: GitHub Actions CI to verify JSON schemas and release asset availability.
- **Porting automation**: Integrated CLI utilities to register and publish ported modules.

## Installation
Modules hosted in this repository can be installed directly through the **MySU Manager** application under the **Repository** tab, or downloaded manually and flashed via:

```bash
/data/adb/mysu/bin/mysud module install /path/to/module.zip
```

## Usage

### Catalog Endpoint
MySU Manager queries the catalog index at:
```
https://raw.githubusercontent.com/MySU-org/modules/main/modules.json
```

Detailed per-module manifests are fetched on-demand from:
```
https://raw.githubusercontent.com/MySU-org/modules/main/modules/<moduleId>.json
```

### Registering a Module
To register or update a module in the catalog:

```bash
./scripts/add_module.py \
  --id encore \
  --name "Encore Tweaks" \
  --author "Rem01Gaming,kelexine" \
  --summary "Universal Android Performance, Battery & Thermal Tweaks" \
  --version 5.2.1-mysu \
  --version-code 1552 \
  --zip /path/to/encore-v5.2.1-mysu.zip \
  --gh-release
```

## Architecture

```mermaid
flowchart LR
    Manager["MySU Manager (Android)"] -->|GET /modules.json| RepoIndex["modules.json (Catalog)"]
    Manager -->|GET /modules/{id}.json| Detail["modules/{id}.json (Detail)"]
    Manager -->|Download Zip| Releases["GitHub Releases Asset"]
```

## Contributing
- **Branch naming**: `<type>/<short-slug>` (e.g., `feat/add-module-name`)
- **Commit convention**: Conventional Commits (`feat`, `fix`, `chore`, etc.) with `Signed-off-by`.
- Ensure all ported modules adhere strictly to native MySU standards (`window.mysu`, `@mysu-org/mysu`) with zero legacy branding.

## License
GPL-3.0-or-later

<!-- generated: antigravity-cli | gemini-3.5-flash | 2026-09-14 -->
