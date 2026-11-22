#!/usr/bin/env python3
"""Build GitHub-ready artifacts from the harvested offer data.

Reads data/category_*.json, merges into a single canonical dataset, then
generates:
  - data/offers.json     (full structured dataset)
  - data/offers.csv      (flat table)
  - data/categories.json (category metadata + counts)
  - docs/categories/*.md (one readable page per category)
"""

import csv
import json
import os
from collections import OrderedDict

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
DOCS = os.path.join(ROOT, "docs", "categories")

CATEGORIES = OrderedDict([
    ("ai",            {"zh": "AI 助手",        "en": "AI Assistants",     "icon": "🤖"}),
    ("dev",           {"zh": "开发者工具",      "en": "Developer Tools",   "icon": "🛠️"}),
    ("cloud",         {"zh": "云计算与托管",    "en": "Cloud & Hosting",   "icon": "☁️"}),
    ("productivity",  {"zh": "效率工具",        "en": "Productivity",      "icon": "⚡"}),
    ("design",        {"zh": "设计与创意",      "en": "Design & Creative", "icon": "🎨"}),
    ("learning",      {"zh": "学习与科研",      "en": "Learning & Research", "icon": "📚"}),
    ("security",      {"zh": "安全与隐私",      "en": "Security & Privacy", "icon": "🔒"}),
    ("entertainment", {"zh": "娱乐与影音",      "en": "Entertainment",     "icon": "🎬"}),
    ("shopping",      {"zh": "购物与生活",      "en": "Shopping & Living", "icon": "🛒"}),
])

SOURCE_SITE = "https://edu.52it.de"

OFFER_URL = "{site}/{lang}/offer/{slug}"


def load_all():
    offers = []
    seen = set()
    for cat in CATEGORIES:
        path = os.path.join(DATA, f"category_{cat}.json")
        if not os.path.exists(path):
            print(f"WARN missing {path}")
            continue
        with open(path, "r", encoding="utf-8") as f:
            rows = json.load(f)
        for r in rows:
            slug = r.get("slug", "").strip()
            if not slug:
                continue
            if slug in seen:
                print(f"WARN duplicate slug {slug}; skipping")
                continue
            seen.add(slug)
            r["category"] = cat
            offers.append(r)
    return offers


def enrich(offers):
    out = []
    for r in offers:
        slug = r["slug"]
        item = OrderedDict()
        item["id"] = slug
        item["slug"] = slug
        item["category"] = r["category"]
        item["category_zh"] = CATEGORIES[r["category"]]["zh"]
        item["category_en"] = CATEGORIES[r["category"]]["en"]
        item["name_zh"] = r.get("name_zh", "") or ""
        item["name_en"] = r.get("name_en", "") or ""
        item["domain"] = r.get("domain", "") or ""
        item["desc_zh"] = r.get("desc_zh", "") or ""
        item["desc_en"] = r.get("desc_en", "") or ""
        item["badges_zh"] = r.get("badges_zh", []) or []
        item["badges_en"] = r.get("badges_en", []) or []
        item["source_en"] = OFFER_URL.format(site=SOURCE_SITE, lang="en", slug=slug)
        item["source_zh"] = OFFER_URL.format(site=SOURCE_SITE, lang="zh", slug=slug)
        # Official link: badge/domain is not a full URL, keep domain only.
        item["official_domain"] = item["domain"]
        out.append(item)
    return out


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def write_csv(path, offers):
    cols = ["id", "category", "category_zh", "category_en", "name_zh", "name_en",
            "domain", "desc_zh", "desc_en", "badges_zh", "badges_en",
            "source_zh", "source_en"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in offers:
            row = dict(r)
            row["badges_zh"] = " | ".join(r["badges_zh"])
            row["badges_en"] = " | ".join(r["badges_en"])
            w.writerow(row)


def md_escape(text):
    return (text or "").replace("|", "\\|").replace("\n", " ").strip()


def category_doc(cat, meta, offers):
    lines = []
    lines.append(f"# {meta['icon']} {meta['zh']} / {meta['en']}")
    lines.append("")
    lines.append(f"> 共 **{len(offers)}** 项福利 · [返回首页](../README.md)")
    lines.append("")
    lines.append("| 福利 / Offer | 站点 | 简介 | 标签 |")
    lines.append("| --- | --- | --- | --- |")
    for r in offers:
        name = md_escape(r["name_zh"]) or md_escape(r["name_en"])
        name_en = md_escape(r["name_en"])
        display = name if not name_en or name_en == name else f"{name} / {name_en}"
        link = f"[{display}]({r['source_zh']})"
        domain = md_escape(r["domain"]) or "—"
        desc = md_escape(r["desc_zh"]) or md_escape(r["desc_en"]) or "—"
        if len(desc) > 120:
            desc = desc[:117] + "…"
        badges = " ".join([f"`{md_escape(b)}`" for b in (r["badges_zh"] or r["badges_en"])])
        lines.append(f"| {link} | {domain} | {desc} | {badges} |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"数据来源：[Student Resources Hub]({SOURCE_SITE}) · 信息可能变化，申请前请前往官方页面核实。")
    lines.append("")
    return "\n".join(lines)


def main():
    raw = load_all()
    offers = enrich(raw)
    write_json(os.path.join(DATA, "offers.json"), offers)

    # sort by category order then name
    cat_order = {c: i for i, c in enumerate(CATEGORIES)}
    offers_sorted = sorted(offers, key=lambda r: (cat_order.get(r["category"], 99), r["name_en"].lower()))

    write_csv(os.path.join(DATA, "offers.csv"), offers_sorted)

    cat_meta = []
    for cat, meta in CATEGORIES.items():
        items = [r for r in offers_sorted if r["category"] == cat]
        cat_meta.append({
            "slug": cat, "name_zh": meta["zh"], "name_en": meta["en"],
            "icon": meta["icon"], "count": len(items),
        })
        os.makedirs(DOCS, exist_ok=True)
        with open(os.path.join(DOCS, f"{cat}.md"), "w", encoding="utf-8") as f:
            f.write(category_doc(cat, meta, items))

    write_json(os.path.join(DATA, "categories.json"), cat_meta)

    print(f"Total offers: {len(offers)}")
    for c in cat_meta:
        print(f"  {c['slug']:15s} {c['count']:3d}  {c['name_en']}")


if __name__ == "__main__":
    main()
