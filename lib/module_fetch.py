#!/usr/bin/env python3
"""Fetch module manifests and hooks from GitHub repos into local .harness/modules/ cache."""

import json
import os
import subprocess
import sys
import base64


def load_json(path):
    with open(path) as f:
        return json.load(f)


def gh_api(endpoint):
    """Call gh api and return parsed JSON. Returns None on failure."""
    try:
        result = subprocess.run(
            ["gh", "api", endpoint],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return None
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return None


def fetch_file_content(org, repo, path):
    """Fetch a file's content from GitHub API. Returns decoded string or None."""
    data = gh_api(f"repos/{org}/{repo}/contents/{path}")
    if data and "content" in data:
        return base64.b64decode(data["content"]).decode("utf-8")
    return None


def fetch_directory_listing(org, repo, path):
    """List files in a directory on GitHub. Returns list of {name, path, type} or empty."""
    data = gh_api(f"repos/{org}/{repo}/contents/{path}")
    if isinstance(data, list):
        return [{"name": f["name"], "path": f["path"], "type": f["type"]} for f in data]
    return []


def fetch_module(module_name, cache_dir, org="ProppyAI"):
    """Fetch a module's manifest and hooks from GitHub.

    Downloads to cache_dir/<module_name>/module.harness.json and hooks/.
    Returns (success: bool, message: str).
    """
    repo = f"module-{module_name}"
    module_dir = os.path.join(cache_dir, module_name)
    os.makedirs(module_dir, exist_ok=True)

    # Fetch manifest
    manifest_content = fetch_file_content(org, repo, "module.harness.json")
    if manifest_content is None:
        return False, f"Failed to fetch manifest from {org}/{repo}"

    # Validate it's valid JSON
    try:
        json.loads(manifest_content)
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON in manifest from {org}/{repo}: {e}"

    manifest_path = os.path.join(module_dir, "module.harness.json")
    with open(manifest_path, "w") as f:
        f.write(manifest_content)

    # Fetch hooks directory
    hooks_dir = os.path.join(module_dir, "hooks")
    os.makedirs(hooks_dir, exist_ok=True)

    hook_files = fetch_directory_listing(org, repo, "hooks")
    for hf in hook_files:
        if hf["type"] != "file":
            continue
        content = fetch_file_content(org, repo, hf["path"])
        if content:
            hook_path = os.path.join(hooks_dir, hf["name"])
            with open(hook_path, "w") as f:
                f.write(content)
            os.chmod(hook_path, 0o755)

    # Parse version from manifest
    manifest = json.loads(manifest_content)
    version = manifest.get("version", "?")

    return True, f"{module_name} ({version})"


def fetch_all_modules(deployment_path, cache_dir, org="ProppyAI"):
    """Fetch all modules declared in a deployment's harness.json.

    Returns list of (module_name, success, message).
    """
    config_path = os.path.join(deployment_path, "harness.json")
    if not os.path.isfile(config_path):
        return [("harness.json", False, "not found")]

    config = load_json(config_path)
    enabled = config.get("modules", {}).get("enabled", [])
    if not enabled:
        return [("(none)", False, "no modules enabled")]

    results = []
    for module_name in enabled:
        success, message = fetch_module(module_name, cache_dir, org)
        results.append((module_name, success, message))

    return results


def print_fetch_results(results):
    """Print fetch results in human-readable format."""
    for name, success, message in results:
        status = "\u2713" if success else "\u2717"
        print(f"  {status} {message}")


def main():
    if len(sys.argv) < 2:
        print("Usage:", file=sys.stderr)
        print("  module_fetch.py fetch <module-name> <cache-dir> [--org org]", file=sys.stderr)
        print("  module_fetch.py fetch-all <deployment-path> <cache-dir> [--org org]", file=sys.stderr)
        sys.exit(2)

    subcmd = sys.argv[1]
    org = "ProppyAI"

    # Parse --org flag
    if "--org" in sys.argv:
        idx = sys.argv.index("--org")
        if idx + 1 < len(sys.argv):
            org = sys.argv[idx + 1]

    if subcmd == "fetch":
        if len(sys.argv) < 4:
            print("Usage: module_fetch.py fetch <module-name> <cache-dir> [--org org]", file=sys.stderr)
            sys.exit(2)
        module_name = sys.argv[2]
        cache_dir = sys.argv[3]

        print(f"HARNESS \u2014 Fetching module: {module_name}\n")
        success, message = fetch_module(module_name, cache_dir, org)
        status = "\u2713" if success else "\u2717"
        print(f"  {status} {message}")
        sys.exit(0 if success else 1)

    elif subcmd == "fetch-all":
        if len(sys.argv) < 4:
            print("Usage: module_fetch.py fetch-all <deployment-path> <cache-dir> [--org org]", file=sys.stderr)
            sys.exit(2)
        deployment_path = sys.argv[2]
        cache_dir = sys.argv[3]

        print(f"HARNESS \u2014 Fetching modules from {org}...\n")
        results = fetch_all_modules(deployment_path, cache_dir, org)
        print_fetch_results(results)

        failed = sum(1 for _, s, _ in results if not s)
        total = len(results)
        print(f"\n  {total - failed}/{total} modules fetched")
        sys.exit(1 if failed > 0 else 0)

    else:
        print(f"Unknown subcommand: {subcmd}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
