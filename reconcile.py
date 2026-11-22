#!/usr/bin/env python3
"""Reconcile harvested category cards with the canonical sitemap.

Any offer slug present in the sitemap but missing from the harvested card
files gets a stub entry (name from sitemap, category from sitemap, status
marked as unknown/paused). This guarantees the archive covers all offers.
"""

import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")

CAT_NAMES = {
    "ai": ("AI 助手", "AI Assistants"),
    "cloud": ("云计算与托管", "Cloud & Hosting"),
    "design": ("设计与创意", "Design & Creative"),
    "dev": ("开发者工具", "Developer Tools"),
    "entertainment": ("娱乐与影音", "Entertainment"),
    "learning": ("学习与科研", "Learning & Research"),
    "productivity": ("效率工具", "Productivity"),
    "security": ("安全与隐私", "Security & Privacy"),
    "shopping": ("购物与生活", "Shopping & Living"),
}


def load(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    sm = load(os.path.join(DATA, "sitemap_all.json"))
    if not sm:
        print("No sitemap_all.json; skipping reconciliation.")
        return

    sm_by_slug = {s["slug"]: s for s in sm}

    harvested = {}
    for cat in CAT_NAMES:
        for r in load(os.path.join(DATA, f"category_{cat}.json")):
            harvested[r["slug"]] = r

    missing = [s for s in sm if s["slug"] not in harvested]
    print(f"Sitemap offers: {len(sm)}")
    print(f"Harvested offers: {len(harvested)}")
    print(f"Missing from card harvest: {len(missing)}")

    if missing:
        # Append missing offers into their category card file as stubs
        for cat in CAT_NAMES:
            cat_missing = [s for s in missing if s.get("category") == cat]
            if not cat_missing:
                continue
            path = os.path.join(DATA, f"category_{cat}.json")
            rows = load(path)
            for s in cat_missing:
                rows.append({
                    "slug": s["slug"],
                    "category": cat,
                    "name_zh": "",
                    "name_en": s.get("name_en", ""),
                    "domain": "",
                    "desc_zh": "",
                    "desc_en": "",
                    "badges_zh": [],
                    "badges_en": ["Paused/Ended" if s.get("status") else ""],
                    "status": s.get("status", ""),
                })
            with open(path, "w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False, indent=2)
                f.write("\n")
            print(f"  Added {len(cat_missing)} stub(s) to {cat}")

    # Remove badges_en entries that are empty strings
    for cat in CAT_NAMES:
        path = os.path.join(DATA, f"category_{cat}.json")
        rows = load(path)
        changed = False
        for r in rows:
            for key in ("badges_zh", "badges_en"):
                if key in r and isinstance(r[key], list):
                    cleaned = [b for b in r[key] if isinstance(b, str) and b.strip()]
                    if cleaned != r[key]:
                        r[key] = cleaned
                        changed = True
        if changed:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False, indent=2)
                f.write("\n")


if __name__ == "__main__":
    main()
