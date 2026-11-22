#!/usr/bin/env python3
"""Generate the main README.md from data/offers.json and data/categories.json."""

import json
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")

SOURCE = "https://edu.52it.de"
REPO_NAME = "student-resources-hub"


def md_escape(text):
    return (text or "").replace("|", "\\|").replace("\n", " ").strip()


def main():
    with open(os.path.join(DATA, "offers.json"), "r", encoding="utf-8") as f:
        offers = json.load(f)
    with open(os.path.join(DATA, "categories.json"), "r", encoding="utf-8") as f:
        cats = json.load(f)

    by_cat = defaultdict(list)
    for o in offers:
        by_cat[o["category"]].append(o)

    total = len(offers)

    L = []
    L.append("<!-- markdownlint-disable MD033 MD041 -->")
    L.append(f"# 学生资源福利汇总 · Student Resources Hub")
    L.append("")
    L.append("> 一个由社区整理的**学生 / 教师优惠与免费资源**清单，汇总自 [edu.52it.de](https://edu.52it.de/)。")
    L.append("> A community-curated index of **student & educator discounts and free resources**, sourced from [edu.52it.de](https://edu.52it.de/).")
    L.append("")
    L.append(f"[![Offers](https://img.shields.io/badge/offers-{total}-blue)](data/offers.json) "
             f"[![Categories](https://img.shields.io/badge/categories-{len(cats)}-green)](data/categories.json) "
             "[![License](https://img.shields.io/badge/license-CC%20BY--SA%204.0-lightgrey)](LICENSE) "
             "[![Data](https://img.shields.io/badge/data-JSON%20%7C%20CSV-orange)](data/)")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## 📊 概览 / Overview")
    L.append("")
    L.append(f"| 项目 | 数值 |")
    L.append(f"| --- | --- |")
    active = sum(1 for o in offers if o.get("status") == "Active")
    ended = sum(1 for o in offers if o.get("status") == "Ended")
    paused = sum(1 for o in offers if o.get("status") == "Paused")
    with_claim = sum(1 for o in offers if o.get("claim_zh") or o.get("claim_en"))
    L.append(f"| 福利总数 / Offers | **{total}** |")
    L.append(f"| 有效 / Active | {active} |")
    L.append(f"| 已结束 / Ended | {ended} |")
    L.append(f"| 已暂停 / Paused | {paused} |")
    L.append(f"| 分类数 / Categories | **{len(cats)}** |")
    L.append(f"| 含领取步骤 / With claim steps | {with_claim} |")
    L.append(f"| 语言 / Languages | 简体中文 · English |")
    L.append(f"| 数据来源 / Source | [{SOURCE}]({SOURCE}) |")
    L.append(f"| 最后抓取 / Snapshot | 2026-11-22 |")
    L.append("")
    L.append("## 🗂️ 分类 / Categories")
    L.append("")
    L.append("| 分类 Category | 数量 Count | 详情 Detail |")
    L.append("| --- | ---: | --- |")
    for c in cats:
        L.append(f"| {c['icon']} {c['name_zh']} / {c['name_en']} | {c['count']} | "
                 f"[查看 →](docs/categories/{c['slug']}.md) |")
    L.append("")
    L.append("## 🔥 精选福利 / Featured")
    L.append("")
    featured_slugs = [
        "github-student-developer-pack", "jetbrains-free-student-license",
        "figma-education", "canva-design-tool", "notion-ai-notes",
        "azure-for-students", "google-gemini-for-students", "microsoft-office-365-student-edition",
    ]
    by_slug = {o["slug"]: o for o in offers}
    L.append("| 福利 / Offer | 简介 / Description |")
    L.append("| --- | --- |")
    for s in featured_slugs:
        o = by_slug.get(s)
        if not o:
            continue
        name = o["name_zh"] or o["name_en"]
        desc = md_escape(o["desc_zh"]) or md_escape(o["desc_en"])
        if len(desc) > 90:
            desc = desc[:87] + "…"
        L.append(f"| [{name}]({o['source_zh']}) | {desc} |")
    L.append("")
    L.append("## 📚 全部福利 / All Offers")
    L.append("")
    L.append("> 完整清单按分类拆分为独立文档；也可用结构化数据自行筛选。")
    L.append("")
    for c in cats:
        slug = c["slug"]
        items = by_cat.get(slug, [])
        L.append(f"### {c['icon']} {c['name_zh']} / {c['name_en']} ({len(items)})")
        L.append("")
        L.append(f"<details><summary>展开 / Expand ({len(items)})</summary>")
        L.append("")
        L.append("| 福利 / Offer | 站点 | 标签 |")
        L.append("| --- | --- | --- |")
        for o in items:
            name = md_escape(o["name_zh"]) or md_escape(o["name_en"])
            name_en = md_escape(o["name_en"])
            label = name if (not name_en or name_en == name) else f"{name} / {name_en}"
            dom = md_escape(o["domain"]) or "—"
            badges = " ".join([f"`{md_escape(b)}`" for b in (o["badges_zh"] or o["badges_en"])[:3]])
            L.append(f"| [{label}]({o['source_zh']}) | {dom} | {badges} |")
        L.append("")
        L.append("</details>")
        L.append("")
    L.append("## 📦 数据文件 / Data")
    L.append("")
    L.append("- [`data/offers.json`](data/offers.json) — 完整结构化数据（中英双语，含 slug、分类、域名、简介、标签、来源链接）")
    L.append("- [`data/offers.csv`](data/offers.csv) — 表格版本，适合 Excel / pandas 分析")
    L.append("- [`data/categories.json`](data/categories.json) — 分类元数据与数量")
    L.append("- [`docs/categories/`](docs/categories/) — 按分类拆分的 Markdown 清单")
    L.append("- [`offers/`](offers/) — 每项福利独立页面（301 篇，含简介、领取步骤、标签）")
    L.append("")
    L.append("字段说明 / Schema:")
    L.append("")
    L.append("```json")
    L.append("{")
    L.append('  "id": "figma-education",')
    L.append('  "slug": "figma-education",')
    L.append('  "category": "design",')
    L.append('  "name_zh": "Figma 教育版",')
    L.append('  "name_en": "Figma Education",')
    L.append('  "domain": "figma.com",')
    L.append('  "desc_zh": "...", "desc_en": "...",')
    L.append('  "badges_zh": [], "badges_en": [],')
    L.append('  "source_zh": "https://edu.52it.de/zh/offer/figma-education",')
    L.append('  "source_en": "https://edu.52it.de/en/offer/figma-education"')
    L.append("}")
    L.append("```")
    L.append("")
    L.append("## ⚠️ 免责声明 / Disclaimer")
    L.append("")
    L.append("- 本仓库仅为信息索引，不隶属于 edu.52it.de 或任何福利提供方。")
    L.append("- 优惠的可用性、地区限制、资格条件会随时变化；申请前请务必前往官方页面核实。")
    L.append("- 数据来自公开网页抓取，可能存在偏差或过期；欢迎通过 Issue / PR 指正。")
    L.append("")
    L.append("## 🤝 贡献 / Contributing")
    L.append("")
    L.append("欢迎提交 Issue 或 Pull Request 修正错误信息、补充缺失福利。详见 [CONTRIBUTING.md](CONTRIBUTING.md)。")
    L.append("")
    L.append("## 📄 许可 / License")
    L.append("")
    L.append("内容采用 [CC BY-SA 4.0](LICENSE) 许可，转载请署名原站 [edu.52it.de](https://edu.52it.de/)。")
    L.append("")

    out = os.path.join(ROOT, "README.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print(f"Wrote {out} ({len(L)} lines, {total} offers)")


if __name__ == "__main__":
    main()
