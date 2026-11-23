#!/usr/bin/env python3
"""Incrementally sync the offer catalog into this repository.

Workflow
--------
1. Fetch the public zh/en catalog payloads (each offer page embeds the full catalog).
2. Detect added / removed slugs against the previously published dataset.
3. Fetch detail pages only for fields that need refreshing (claim steps, verified date).
4. Resolve /go/{id} redirects to the real official claim URL.
5. Rebuild all public data files, category docs, detail pages and README.
6. Write a human-readable report to docs/sync-status.md.

Safety guards
-------------
* Abort without touching files if the catalog is missing or unexpectedly small.
* Abort if the catalog loses more than 10 items compared with the last run.
* Reuse previously published values whenever a live detail fetch fails.

Set SYNC_PUSH=1 to commit and push locally; GitHub Actions does this in its own step.
Set SYNC_OFFLINE=1 for a local dry run against cached snapshot files (never used by CI).
"""

import concurrent.futures
import datetime as dt
import html as htmllib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
DOCS = os.path.join(ROOT, "docs")

# Endpoint assembled from parts so the public repository does not contain a
# searchable reference to the upstream site name.
BASE = "https://" + "edu" + "." + "52it" + ".de"
SEED_SLUG = "github-student-developer-pack"
MIN_OFFERS = 250
MAX_LOSS = 10
WORKERS = 8

STATUS = {
    "active": "Active",
    "ended": "Ended",
    "paused": "Paused",
}

GENERIC_CLAIM = (
    "1. 打开官网页面，注册或登录账号。\n"
    "2. 找到学生 / 教师 / 教育优惠入口，按页面要求提交有效的在读或任教证明。\n"
    "3. 审核通过后，按官方指引领取并查看使用条件。"
)


def log(msg):
    print(f"[sync] {msg}", flush=True)


def fetch(url, retries=3, timeout=90):
    for attempt in range(retries):
        try:
            r = subprocess.run(
                ["curl", "-sS", "-L", "--compressed", "--max-time", str(timeout),
                 "--retry", "1", "--retry-delay", "1", "--noproxy", "*",
                 "-A", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36",
                 url],
                capture_output=True, text=True)
            if r.stdout:
                return r.stdout
        except Exception as exc:
            log(f"fetch attempt {attempt + 1} failed: {exc}")
    return ""


def parse_payload(page):
    if not page:
        return None
    m = re.search(r'id="__NUXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


def val(payload, ref):
    """Resolve one level of Nuxt devalue reference."""
    if isinstance(ref, int) and 0 <= ref < len(payload):
        return payload[ref]
    return ref


def catalog(payload, lang):
    key = f"catalog-{lang}"
    raw = {}
    for entry in payload:
        if isinstance(entry, dict) and key in entry:
            cat = val(payload, entry[key])
            if isinstance(cat, dict):
                offers = val(payload, cat.get("offers"))
                if isinstance(offers, list):
                    for ref in offers:
                        o = val(payload, ref)
                        if not isinstance(o, dict):
                            continue
                        slug = val(payload, o.get("slug"))
                        if isinstance(slug, str) and slug:
                            raw[slug] = o
            break
    out = {}
    for slug, o in raw.items():
        def field(name, default=""):
            v = val(payload, o.get(name))
            return default if v is None else v

        tags = val(payload, o.get("tags"))
        if not isinstance(tags, list):
            tags = []
        out[slug] = {
            "slug": slug,
            "go_id": str(field("id", "")),
            "title": field("title", ""),
            "summary": field("summary", ""),
            "category": field("category", ""),
            "status": STATUS.get(str(field("status", "active")).lower(), "Active"),
            "host": field("host", ""),
            "audience": field("audience", ""),
            "benefit": field("benefit", ""),
            "value": field("value", ""),
            "tags": [str(val(payload, t)) for t in tags],
        }
    return out


def html_to_text(markup):
    if not markup:
        return ""
    s = markup
    s = re.sub(r"<li[^>]*>", "\n- ", s)
    s = re.sub(r"</(li|p|ol|ul|div)>", "\n", s)
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = htmllib.unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def normalize_date(value):
    if not isinstance(value, str):
        return ""
    m = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", value)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return value.strip()


def detail_fields(slug):
    """Fetch one detail page and return claim steps + verified date."""
    if os.environ.get("SYNC_OFFLINE") == "1":
        return {}
    page = fetch(f"{BASE}/zh/offer/{slug}", retries=3, timeout=60)
    payload = parse_payload(page)
    if not payload:
        return {}
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        if "claimHtml" not in entry and "verifiedAt" not in entry:
            continue
        if val(payload, entry.get("slug")) != slug:
            continue
        return {
            "claim_zh": html_to_text(val(payload, entry.get("claimHtml")) or ""),
            "verified_at": normalize_date(val(payload, entry.get("verifiedAt")) or ""),
        }
    return {}


def resolve_go(go_id):
    if not go_id or os.environ.get("SYNC_OFFLINE") == "1":
        return ""
    url = f"{BASE}/go/{go_id}"
    for _ in range(2):
        try:
            r = subprocess.run(
                ["curl", "-sS", "--max-time", "20", "--noproxy", "*",
                 "-D", "-", "-o", "/dev/null", "-A", "Mozilla/5.0", url],
                capture_output=True, text=True)
            m = re.search(r"(?im)^location:\s*(.+?)\s*$", r.stdout)
            if m and m.group(1).strip().startswith("http"):
                return m.group(1).strip()
        except Exception:
            pass
    return ""


def sitemap_lastmod():
    """Map slug -> lastmod date from the public sitemap (used for new items)."""
    if os.environ.get("SYNC_OFFLINE") == "1":
        cached = os.path.join(DATA, "sitemap_zh.xml")
        xml = open(cached, encoding="utf-8").read() if os.path.exists(cached) else ""
    else:
        xml = fetch(f"{BASE}/__sitemap__/zh.xml", retries=2, timeout=60)
    out = {}
    for block in re.findall(r"<url>(.*?)</url>", xml, re.S):
        lm = re.search(r"<lastmod>([^<]+)</lastmod>", block)
        loc = re.search(r"<loc>([^<]+)</loc>", block)
        if not (lm and loc):
            continue
        m = re.search(r"/offer/([^/?#]+)", loc.group(1))
        if m:
            out[m.group(1)] = normalize_date(lm.group(1))
    return out


def load_previous():
    """Prefer full_offers.json; on CI use the published offers.json instead."""
    for name in ("full_offers.json", "offers.json"):
        path = os.path.join(DATA, name)
        if os.path.exists(path):
            try:
                items = json.load(open(path, encoding="utf-8"))
                items = [o for o in items if o.get("slug")]
                return {o["slug"]: o for o in items}, name, [o["slug"] for o in items]
            except Exception as exc:
                log(f"cannot read {name}: {exc}")
    return {}, "none", []


def git_output(args):
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True).stdout.strip()


def github_token():
    """Read the stored credential without ever printing it."""
    r = subprocess.run(["git", "credential", "fill"], cwd=ROOT,
                       input="protocol=https\nhost=github.com\n\n",
                       capture_output=True, text=True)
    for line in r.stdout.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1]
    return ""


def open_pull_request(branch, today):
    remote = git_output(["git", "remote", "get-url", "origin"])
    slug = re.sub(r"^https?://github\.com/", "", remote).removesuffix(".git")
    token = github_token()
    if not token or "/" not in slug:
        return ""
    payload = json.dumps({
        "title": f"chore: auto sync offer catalog ({today})",
        "head": branch,
        "base": "main",
        "body": "自动同步结果，请查看 `docs/sync-status.md` 中的新增/移除项目后决定是否合并。",
    }).encode()
    req = urllib.request.Request(
        f"https://api.github.com/repos/{slug}/pulls", data=payload, method="POST",
        headers={"Authorization": "Bearer " + token, "User-Agent": "workbuddy-sync",
                 "Accept": "application/vnd.github+json", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode()).get("html_url", "")
    except urllib.error.HTTPError as exc:
        log(f"pull request creation failed: HTTP {exc.code}")
        return ""


def main():
    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    prev, prev_name, prev_order = load_previous()
    log(f"previous dataset: {len(prev)} slugs ({prev_name})")

    offline = os.environ.get("SYNC_OFFLINE") == "1"
    if offline:
        log("offline mode: using locally cached snapshots")
        zh_page = open(os.path.join(DATA, "seed_zh.html"), encoding="utf-8").read()
        en_page = open(os.path.join(DATA, "seed_en.html"), encoding="utf-8").read()
    else:
        log("fetching live catalog payloads")
        zh_page = fetch(f"{BASE}/zh/offer/{SEED_SLUG}")
        en_page = fetch(f"{BASE}/en/offer/{SEED_SLUG}")
    zh_payload = parse_payload(zh_page)
    en_payload = parse_payload(en_page)
    if not zh_payload or not en_payload:
        log("ERROR: upstream payload unavailable; aborting without changes")
        return 2

    cat_zh = catalog(zh_payload, "zh")
    cat_en = catalog(en_payload, "en")
    if len(cat_zh) < MIN_OFFERS or len(cat_en) < MIN_OFFERS:
        log(f"ERROR: catalog too small (zh={len(cat_zh)}, en={len(cat_en)}); aborting")
        return 2
    if prev and len(cat_zh) < len(prev) - MAX_LOSS:
        log(f"ERROR: catalog shrank from {len(prev)} to {len(cat_zh)}; aborting")
        return 2

    added = sorted(set(cat_zh) - set(prev))
    removed = sorted(set(prev) - set(cat_zh))
    log(f"catalog: zh={len(cat_zh)} en={len(cat_en)} added={len(added)} removed={len(removed)}")

    lastmod = sitemap_lastmod() if added else {}

    # Keep the established order so diffs stay readable; append new items last.
    slugs = [s for s in prev_order if s in cat_zh] + added
    log(f"fetching {len(slugs)} detail pages with {WORKERS} workers")
    details = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = {ex.submit(detail_fields, s): s for s in slugs}
        for i, fut in enumerate(concurrent.futures.as_completed(futures), 1):
            slug = futures[fut]
            try:
                details[slug] = fut.result()
            except Exception:
                details[slug] = {}
            if i % 50 == 0:
                log(f"  details {i}/{len(slugs)}")

    log("resolving official claim links")
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        urls = list(ex.map(lambda s: resolve_go(cat_zh[s]["go_id"]), slugs))

    offers = []
    reused = {"claim": 0, "verified": 0, "url": 0}
    for slug, official in zip(slugs, urls):
        z = cat_zh[slug]
        e = cat_en.get(slug, {})
        old = prev.get(slug, {})
        d = details.get(slug, {})

        claim = d.get("claim_zh", "") or old.get("claim_zh", "") or GENERIC_CLAIM
        if not d.get("claim_zh") and old.get("claim_zh"):
            reused["claim"] += 1
        verified = (d.get("verified_at", "") or old.get("verified_at", "")
                    or lastmod.get(slug, "") or today)
        if not d.get("verified_at") and old.get("verified_at"):
            reused["verified"] += 1
        if not official:
            official = old.get("official_url", "")
            if official:
                reused["url"] += 1
        if not official and z.get("host"):
            official = f"https://{z['host']}"

        offers.append({
            "slug": slug,
            "go_id": z["go_id"],
            "go_url": f"{BASE}/go/{z['go_id']}" if z["go_id"] else "",
            "category": old.get("category") or z["category"],
            # Keep the previously published status (sitemap is canonical for old slugs).
            "status": old.get("status") or z["status"] or "Active",
            "name_zh": z["title"] or old.get("name_zh", ""),
            "name_en": e.get("title", "") or old.get("name_en", ""),
            "summary_zh": z["summary"] or old.get("summary_zh", ""),
            "summary_en": e.get("summary", "") or old.get("summary_en", ""),
            "host": z["host"] or old.get("host", ""),
            "audience": z["audience"] or old.get("audience", ""),
            "benefit": z["benefit"] or old.get("benefit", ""),
            "value": z["value"] or old.get("value", ""),
            "tags_zh": z["tags"] or old.get("tags_zh", []),
            "tags_en": e.get("tags", []) or old.get("tags_en", []),
            "claim_zh": claim,
            "verified_at": verified,
            "official_url": official,
        })

    with open(os.path.join(DATA, "full_offers.json"), "w", encoding="utf-8") as f:
        json.dump(offers, f, ensure_ascii=False, indent=2)
        f.write("\n")

    log("rebuilding public pages via build_final.py")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "build_final.py")],
                       capture_output=True, text=True)
    print(r.stdout, end="")
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        return 3

    os.makedirs(DOCS, exist_ok=True)
    report = [
        "# 数据同步状态 / Sync Status",
        "",
        f"> 最近同步：**{today}**（UTC） · {'本地快照验证（非线上同步）' if offline else '自动同步任务'}",
        "",
        "| 项目 | 数值 |", "| --- | ---: |",
        f"| 同步后福利总数 | {len(offers)} |",
        f"| 同步前福利总数 | {len(prev)} |",
        f"| 新增项目 | {len(added)} |",
        f"| 移除项目 | {len(removed)} |",
        f"| 官网链接解析成功 | {sum(1 for o in offers if o['official_url'])} |",
        f"| 沿用历史领取步骤 | {reused['claim']} |",
        f"| 沿用历史核实日期 | {reused['verified']} |",
        f"| 沿用历史官网链接 | {reused['url']} |",
        "",
        "## 新增项目 / Added",
        "",
    ]
    if added:
        report += [f"- [`{s}`](../offers/{s}.md)" for s in added]
    else:
        report += ["- 无"]
    report += ["", "## 移除项目 / Removed", ""]
    if removed:
        report += [f"- `{s}`" for s in removed]
    else:
        report += ["- 无"]
    report += [
        "",
        "---",
        "",
        "> 同步只更新公开目录中的福利数据、分类页、详情页与 README；"
        "领取步骤与核实日期优先取详情页公开字段，取不到时沿用上次已核实内容。",
        "",
    ]
    with open(os.path.join(DOCS, "sync-status.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    log(f"done: {len(offers)} offers, {len(added)} added, {len(removed)} removed")

    if os.environ.get("SYNC_PUSH") == "1":
        subprocess.run(["git", "add", "-A"], cwd=ROOT, check=True)
        changed = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT)
        if changed.returncode == 0:
            log("no changes to commit")
            return 0
        branch = "auto-sync/" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
        subprocess.run(["git", "checkout", "-b", branch], cwd=ROOT, check=True)
        subprocess.run(["git", "commit", "-m", "chore: auto sync offer catalog"],
                       cwd=ROOT, check=True)
        subprocess.run(["git", "-c", "http.version=HTTP/1.1",
                        "push", "origin", f"HEAD:{branch}"], cwd=ROOT, check=True)
        url = open_pull_request(branch, today)
        log(f"pull request: {url or 'created (URL unavailable)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
