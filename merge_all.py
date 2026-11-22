#!/usr/bin/env python3
"""Merge all harvested sources into the canonical offers dataset.

Priority of sources:
  1. sitemap_all.json  -> canonical slug list, category, name_en, status
  2. sitemap_names_zh.txt -> canonical name_zh for all slugs
  3. category_*.json   -> card-level desc/badges/domain (top items)
  4. details_*.json    -> full desc + claim steps from offer detail pages

Writes data/offers.json, data/offers.csv, data/categories.json.
"""

import csv
import glob
import json
import os
from collections import OrderedDict

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
DOCS = os.path.join(ROOT, "docs", "categories")

SITE = "https://edu.52it.de"

CATS = OrderedDict([
    ("ai",            {"zh": "AI 助手",          "en": "AI Assistants",        "icon": "🤖"}),
    ("dev",           {"zh": "开发者工具",        "en": "Developer Tools",      "icon": "🛠️"}),
    ("cloud",         {"zh": "云计算与托管",      "en": "Cloud & Hosting",      "icon": "☁️"}),
    ("productivity",  {"zh": "效率工具",          "en": "Productivity",         "icon": "⚡"}),
    ("design",        {"zh": "设计与创意",        "en": "Design & Creative",    "icon": "🎨"}),
    ("learning",      {"zh": "学习与科研",        "en": "Learning & Research",  "icon": "📚"}),
    ("security",      {"zh": "安全与隐私",        "en": "Security & Privacy",   "icon": "🔒"}),
    ("entertainment", {"zh": "娱乐与影音",        "en": "Entertainment",        "icon": "🎬"}),
    ("shopping",      {"zh": "购物与生活",        "en": "Shopping & Living",    "icon": "🛒"}),
])


def load_json(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"WARN could not read {path}: {e}")
        return default if default is not None else []


def load_zh_names():
    names = {}
    path = os.path.join(DATA, "sitemap_names_zh.txt")
    if not os.path.exists(path):
        return names
    for line in open(path, "r", encoding="utf-8"):
        if "|" in line:
            slug, name = line.split("|", 1)
            names[slug.strip()] = name.strip()
    return names


def md_escape(text):
    return (text or "").replace("|", "\\|").replace("\n", " ").strip()


def main():
    sitemap = load_json(os.path.join(DATA, "sitemap_all.json"))
    zh_names = load_zh_names()

    # card data
    cards = {}
    for path in glob.glob(os.path.join(DATA, "category_*.json")):
        for r in load_json(path):
            if r.get("slug"):
                cards[r["slug"]] = r

    # detail data
    details = {}
    for path in glob.glob(os.path.join(DATA, "details_*.json")) + glob.glob(os.path.join(DATA, "claims_*.json")):
        for r in load_json(path):
            if r.get("slug"):
                details.setdefault(r["slug"], {}).update(r)

    offers = []
    for s in sitemap:
        slug = s["slug"]
        card = cards.get(slug, {})
        det = details.get(slug, {})
        cat = s.get("category") or card.get("category") or "other"

        name_zh = zh_names.get(slug, "") or card.get("name_zh", "") or det.get("name_zh", "")
        name_en = s.get("name_en", "") or card.get("name_en", "") or det.get("name_en", "")

        desc_zh = det.get("desc_zh", "") or card.get("desc_zh", "")
        desc_en = det.get("desc_en", "") or card.get("desc_en", "")
        claim_zh = det.get("claim_zh", "") or ""
        claim_en = det.get("claim_en", "") or ""
        domain = det.get("domain", "") or card.get("domain", "")

        badges_zh = card.get("badges_zh", []) or []
        badges_en = card.get("badges_en", []) or []
        badges_zh = [b for b in badges_zh if isinstance(b, str) and b.strip()]
        badges_en = [b for b in badges_en if isinstance(b, str) and b.strip()]

        status = s.get("status", "") or ""

        # status badge from slug markers when sitemap has none
        if not status:
            low = slug.lower()
            if "ended" in low:
                status = "Ended"
            elif "paused" in low:
                status = "Paused"

        offers.append(OrderedDict([
            ("id", slug),
            ("slug", slug),
            ("category", cat),
            ("category_zh", CATS.get(cat, {}).get("zh", "")),
            ("category_en", CATS.get(cat, {}).get("en", "")),
            ("name_zh", name_zh),
            ("name_en", name_en),
            ("domain", domain),
            ("desc_zh", desc_zh),
            ("desc_en", desc_en),
            ("claim_zh", claim_zh),
            ("claim_en", claim_en),
            ("badges_zh", badges_zh),
            ("badges_en", badges_en),
            ("status", status or "Active"),
            ("source_zh", f"{SITE}/zh/offer/{slug}"),
            ("source_en", f"{SITE}/en/offer/{slug}"),
        ]))

    # write offers.json
    with open(os.path.join(DATA, "offers.json"), "w", encoding="utf-8") as f:
        json.dump(offers, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # write CSV
    cols = list(offers[0].keys()) if offers else []
    with open(os.path.join(DATA, "offers.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in offers:
            row = dict(r)
            row["badges_zh"] = " | ".join(r["badges_zh"])
            row["badges_en"] = " | ".join(r["badges_en"])
            w.writerow(row)

    # categories
    cat_meta = []
    for c, meta in CATS.items():
        items = [o for o in offers if o["category"] == c]
        cat_meta.append({
            "slug": c, "name_zh": meta["zh"], "name_en": meta["en"],
            "icon": meta["icon"], "count": len(items),
        })
    with open(os.path.join(DATA, "categories.json"), "w", encoding="utf-8") as f:
        json.dump(cat_meta, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # per-category docs (rich, with claim steps when available)
    os.makedirs(DOCS, exist_ok=True)
    for c, meta in CATS.items():
        items = [o for o in offers if o["category"] == c]
        L = [f"# {meta['icon']} {meta['zh']} / {meta['en']}", "",
             f"> 共 **{len(items)}** 项福利 · [返回首页](../../README.md)", "",
             "| # | 福利 / Offer | 站点 | 简介 / Description | 标签 / Tags | 状态 |",
             "| ---: | --- | --- | --- | --- | --- |"]
        for i, o in enumerate(items, 1):
            label = o["name_zh"] or o["name_en"]
            label_en = o["name_en"]
            disp = label if (not label_en or label_en == label) else f"{label} / {label_en}"
            link = f"[{md_escape(disp)}]({o['source_zh']})"
            dom = md_escape(o["domain"]) or "—"
            desc = md_escape(o["desc_zh"]) or md_escape(o["desc_en"]) or "—"
            if len(desc) > 110:
                desc = desc[:107] + "…"
            badges = " ".join([f"`{md_escape(b)}`" for b in (o["badges_zh"] or o["badges_en"])[:3]])
            L.append(f"| {i} | {link} | {dom} | {desc} | {badges} | {o['status']} |")
        L += ["", "---", "",
              f"数据来源：[Student Resources Hub]({SITE}) · 信息可能变化，申请前请前往官方页面核实。", ""]
        with open(os.path.join(DOCS, f"{c}.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(L))

    # per-offer detail pages (one markdown per offer)
    OFFDIR = os.path.join(ROOT, "offers")
    os.makedirs(OFFDIR, exist_ok=True)
    for o in offers:
        slug = o["slug"]
        L = [f"# {o['name_zh'] or o['name_en']}", ""]
        if o["name_en"] and o["name_en"] != o["name_zh"]:
            L += [f"**{o['name_en']}**", ""]
        L += [f"- 分类 / Category: [{o['category_zh']} / {o['category_en']}](../docs/categories/{o['category']}.md)",
              f"- 状态 / Status: {o['status']}",
              f"- 官网域名 / Domain: {o['domain'] or '—'}",
              f"- 源页面 / Source: [中文]({o['source_zh']}) · [English]({o['source_en']})", ""]
        if o["desc_zh"]:
            L += ["## 简介", "", o["desc_zh"], ""]
        if o["desc_en"]:
            L += ["## Description", "", o["desc_en"], ""]
        if o["claim_zh"]:
            L += ["## 如何领取", "", o["claim_zh"], ""]
        if o["claim_en"]:
            L += ["## How to claim", "", o["claim_en"], ""]
        if o["badges_zh"] or o["badges_en"]:
            L += ["## 标签 / Tags", "",
                  " ".join([f"`{md_escape(b)}`" for b in (o["badges_zh"] or o["badges_en"])]), ""]
        with open(os.path.join(OFFDIR, f"{slug}.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(L))

    # stats
    with_desc = sum(1 for o in offers if o["desc_zh"] or o["desc_en"])
    with_claim = sum(1 for o in offers if o["claim_zh"] or o["claim_en"])
    print(f"Offers: {len(offers)}")
    print(f"With description: {with_desc}")
    print(f"With claim steps: {with_claim}")
    for c in cat_meta:
        print(f"  {c['slug']:15s} {c['count']:3d}")


if __name__ == "__main__":
    main()
