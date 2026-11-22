#!/usr/bin/env python3
"""Push all project files to GitHub via the connected GitHub MCP server.

Usage:
    python3 push_to_github.py <owner> <repo>

Reads connection details from CODEBUDDY_MCP_CONFIG so no credentials are
hard-coded. Files are sent in batches (large files isolated) via push_files.
"""

import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))

# Directories / files to skip
SKIP_DIRS = {".git", "__pycache__"}
SKIP_FILES = {"push_to_github.py"}
SKIP_PREFIXES = ("batch_", "missing_slugs")


def collect_files():
    files = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn in SKIP_FILES or fn.startswith(SKIP_PREFIXES):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, ROOT).replace(os.sep, "/")
            size = os.path.getsize(full)
            with open(full, "r", encoding="utf-8") as f:
                content = f.read()
            files.append({"path": rel, "content": content, "size": size})
    return files


def make_batches(files, max_bytes=900_000, max_count=60):
    batches, current, cur_size = [], [], 0
    for f in files:
        # isolate very large files
        if f["size"] > 600_000:
            if current:
                batches.append(current); current, cur_size = [], 0
            batches.append([f])
            continue
        if cur_size + f["size"] > max_bytes or len(current) >= max_count:
            batches.append(current); current, cur_size = [], 0
        current.append(f); cur_size += f["size"]
    if current:
        batches.append(current)
    return batches


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 push_to_github.py <owner> <repo>")
        sys.exit(1)
    owner, repo = sys.argv[1], sys.argv[2]

    cfg = json.loads(os.environ["CODEBUDDY_MCP_CONFIG"])
    g = cfg["mcpServers"]["github"]
    headers = dict(g["headers"])
    headers["Content-Type"] = "application/json"
    headers["Accept"] = "application/json, text/event-stream"

    req_id = [0]

    def call(name, args):
        req_id[0] += 1
        payload = {"jsonrpc": "2.0", "id": req_id[0],
                   "method": "tools/call",
                   "params": {"name": name, "arguments": args}}
        req = urllib.request.Request(
            g["url"], data=json.dumps(payload).encode(), headers=headers)
        raw = urllib.request.urlopen(req, timeout=180).read().decode()
        for line in raw.splitlines():
            if line.startswith("data: "):
                return json.loads(line[6:])
        try:
            return json.loads(raw)
        except Exception:
            return {"raw": raw[:1000]}

    files = collect_files()
    batches = make_batches(files)
    print(f"Pushing {len(files)} files in {len(batches)} batches to {owner}/{repo}")

    for i, batch in enumerate(batches, 1):
        payload_files = [{"path": f["path"], "content": f["content"]} for f in batch]
        print(f"  batch {i}/{len(batches)}: {len(batch)} files "
              f"({sum(f['size'] for f in batch)//1024} KB) ...")
        res = call("push_files", {
            "owner": owner, "repo": repo, "branch": "main",
            "message": (f"feat: add Student Resources Hub dataset batch {i}" if i > 1
                        else "feat: add Student Resources Hub dataset (301 offers, zh/en)"),
            "files": payload_files,
        })
        text = json.dumps(res, ensure_ascii=False)
        if res.get("result", {}).get("isError") or '"isError":true' in text.replace(" ", ""):
            print("  ERROR:", text[:1000])
            sys.exit(1)
        print("  ok")

    print("DONE")
    print(f"https://github.com/{owner}/{repo}")


if __name__ == "__main__":
    main()
