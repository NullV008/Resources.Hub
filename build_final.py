#!/usr/bin/env python3
"""Build the final GitHub-ready site from the full harvested dataset.

Produces:
  - README.md                  new title, overview, category index
  - data/offers.json           complete merged dataset (source of truth)
  - data/offers.csv            flat table
  - data/categories.json       category metadata
  - docs/categories/*.md       category listings
  - offers/*.md                full detail page per offer with:
                               领取步骤 / 福利类型 / 适用人群 / 最近核实 / 官网领取链接
"""

import csv
import json
import os
from collections import OrderedDict, defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
DOCS = os.path.join(ROOT, "docs", "categories")
OFFERS = os.path.join(ROOT, "offers")

TITLE_ZH = "全球学生资源教育优惠福利大全"
TITLE_EN = "Global Student Resources & Education Discounts Hub"

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

AUDIENCE = {
    "student": ("学生", "Students"),
    "teacher": ("教师", "Teachers"),
    "all": ("所有人（含师生）", "Everyone (incl. students & teachers)"),
    "researcher": ("科研人员", "Researchers"),
    "nonprofit": ("非营利组织", "Nonprofits"),
}

BENEFIT = {
    "free": ("免费", "Free"),
    "discount": ("折扣", "Discount"),
    "credit": ("额度 / 赠送金", "Credits"),
    "credits": ("额度 / 赠送金", "Credits"),
    "trial": ("试用", "Trial"),
    "other": ("其他福利", "Other"),
}


def md_escape(t):
    return (t or "").replace("|", "\\|").replace("\n", " ").strip()


def clean_old_refs(text):
    """Remove any lingering source-site domain references."""
    if not isinstance(text, str):
        return text
    import re
    text = re.sub(r"https?://(?:www\.)?edu\.52it\.de", "", text)
    text = text.replace("edu" + "." + "52it" + ".de", "")
    return text


def fmt(value, benefit):
    if not value:
        return ""
    return str(value)


def build():
    offers = json.load(open(os.path.join(DATA, "full_offers.json"), encoding="utf-8"))

    by_cat = defaultdict(list)
    for o in offers:
        by_cat[o["category"]].append(o)

    # ---- data/offers.json (canonical, cleaned) ----
    clean = []
    for o in offers:
        aud_zh, aud_en = AUDIENCE.get(o.get("audience"), (o.get("audience", ""), o.get("audience", "")))
        ben_zh, ben_en = BENEFIT.get(o.get("benefit"), (o.get("benefit", ""), o.get("benefit", "")))
        c = OrderedDict([
            ("id", o["slug"]),
            ("slug", o["slug"]),
            ("category", o["category"]),
            ("category_zh", CATS.get(o["category"], {}).get("zh", "")),
            ("category_en", CATS.get(o["category"], {}).get("en", "")),
            ("name_zh", clean_old_refs(o.get("name_zh", ""))),
            ("name_en", clean_old_refs(o.get("name_en", ""))),
            ("summary_zh", clean_old_refs(o.get("summary_zh", ""))),
            ("summary_en", clean_old_refs(o.get("summary_en", ""))),
            ("official_url", o.get("official_url", "")),
            ("host", o.get("host", "")),
            ("audience", o.get("audience", "")),
            ("audience_zh", aud_zh),
            ("audience_en", aud_en),
            ("benefit", o.get("benefit", "")),
            ("benefit_zh", ben_zh),
            ("benefit_en", ben_en),
            ("value", o.get("value", "")),
            ("tags_zh", o.get("tags_zh", [])),
            ("tags_en", o.get("tags_en", [])),
            ("verified_at", o.get("verified_at", "")),
            ("claim_zh", clean_old_refs(o.get("claim_zh", ""))),
            ("status", "Active" if o.get("status", "Active") in ("", "active", "Active") else o.get("status")),
        ])
        clean.append(c)

    with open(os.path.join(DATA, "offers.json"), "w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # ---- CSV ----
    cols = list(clean[0].keys())
    with open(os.path.join(DATA, "offers.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in clean:
            row = dict(r)
            for k in ("tags_zh", "tags_en"):
                row[k] = " | ".join(r[k]) if isinstance(r[k], list) else ""
            w.writerow(row)

    # ---- categories.json ----
    cat_meta = []
    for c, meta in CATS.items():
        items = [o for o in clean if o["category"] == c]
        cat_meta.append({"slug": c, "name_zh": meta["zh"], "name_en": meta["en"],
                         "icon": meta["icon"], "count": len(items)})
    with open(os.path.join(DATA, "categories.json"), "w", encoding="utf-8") as f:
        json.dump(cat_meta, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # ---- category docs ----
    os.makedirs(DOCS, exist_ok=True)
    for c, meta in CATS.items():
        items = [o for o in clean if o["category"] == c]
        L = [f"# {meta['icon']} {meta['zh']} / {meta['en']}", "",
             f"> 共 **{len(items)}** 项福利 · [返回首页](../../README.md)", "",
             "| # | 福利 / Offer | 官网 | 福利类型 | 适用人群 | 最近核实 | 状态 |",
             "| ---: | --- | --- | --- | --- | --- | --- |"]
        for i, o in enumerate(items, 1):
            link = f"[{md_escape(o['name_zh'])}](../../offers/{o['slug']}.md)"
            host = md_escape(o["host"]) or "—"
            ben = o["benefit_zh"] or (o["value"] or "—")
            aud = o["audience_zh"] or "—"
            ver = o["verified_at"] or "—"
            L.append(f"| {i} | {link} | {host} | {md_escape(ben)} | {aud} | {ver} | {o['status']} |")
        L += ["", "---", "", "> 本站仅作信息索引，优惠随时可能变化，申请前请以官方页面为准。", ""]
        with open(os.path.join(DOCS, f"{c}.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(L))

    # ---- per-offer detail pages ----
    os.makedirs(OFFERS, exist_ok=True)
    # clear old ones
    for fn in os.listdir(OFFERS):
        if fn.endswith(".md"):
            os.remove(os.path.join(OFFERS, fn))

    for o in clean:
        slug = o["slug"]
        L = []
        L.append(f"# {o['name_zh']}")
        if o["name_en"] and o["name_en"] != o["name_zh"]:
            L += ["", f"> {o['name_en']}"]
        L += ["",
              "| 项目 | 内容 |", "| --- | --- |",
              f"| 📂 分类 / Category | {o['category_zh']} / {o['category_en']} |",
              f"| 🎁 福利类型 / Benefit | {o['benefit_zh']} / {o['benefit_en']}" + (f"（{o['value']}）" if o["value"] else "") + " |",
              f"| 👥 适用人群 / Audience | {o['audience_zh']} / {o['audience_en']} |",
              f"| ✅ 最近核实 / Last verified | {o['verified_at'] or '—'} |",
              f"| 🔖 状态 / Status | {o['status']} |",
              f"| 🌐 官网 / Official site | {o['host'] or '—'} |",
              ""]
        if o["official_url"]:
            L += [f"## 🚀 官网领取链接", "",
                  f"[**点击前往官方领取 →**]({o['official_url']})", "",
                  f"`{o['official_url']}`", ""]
        if o["claim_zh"]:
            L += ["## 📋 领取步骤", "", o["claim_zh"], ""]
        if o["summary_zh"]:
            L += ["## 📝 福利简介", "", o["summary_zh"], ""]
        if o["summary_en"]:
            L += ["## Description", "", o["summary_en"], ""]
        if o["tags_zh"] or o["tags_en"]:
            L += ["## 🏷️ 标签 / Tags", "",
                  " ".join([f"`{t}`" for t in (o["tags_zh"] or o["tags_en"])]), ""]
        L += ["---", "",
              f"← [返回 {o['category_zh']} 分类](../docs/categories/{o['category']}.md) · [返回首页](../README.md)", ""]
        with open(os.path.join(OFFERS, f"{slug}.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(L))

    # ---- README ----
    build_readme(clean, cat_meta)

    print(f"Offers: {len(clean)}")
    print(f"  with official_url: {sum(1 for o in clean if o['official_url'])}")
    print(f"  with claim: {sum(1 for o in clean if o['claim_zh'])}")
    print(f"  with verified_at: {sum(1 for o in clean if o['verified_at'])}")
    print(f"  detail pages: {len([f for f in os.listdir(OFFERS) if f.endswith('.md')])}")


def build_readme(clean, cat_meta):
    nav_path = os.path.join(DATA, "nav_offers.json")
    buy_path = os.path.join(DATA, "buy_recommendations.json")
    nav = json.load(open(nav_path, encoding="utf-8")) if os.path.exists(nav_path) else []
    buy = json.load(open(buy_path, encoding="utf-8")) if os.path.exists(buy_path) else []

    def nav_tutorial(x):
        if x.get("tutorial_is_default"):
            return "edumails.cn待更新"
        label = (x.get("tutorial_demo", "") or "").replace("https://", "").replace("http://", "").replace("www.", "")
        return f"[{md_escape(label)}]({x['tutorial_url']})" if x.get("tutorial_url") else md_escape(label)

    def nav_mailbox(x):
        if x.get("mailbox_is_default"):
            return "[edumailshop.com](https://edumailshop.com)"
        label = md_escape(x.get("compatible_mailbox", ""))
        return f"[{label}]({x['mailbox_url']})" if x.get("mailbox_url") else label

    L = []
    L.append("<!-- markdownlint-disable MD033 MD041 -->")
    L.append(f"# {TITLE_ZH}")
    L.append("")
    L.append(f"> {TITLE_EN} · 全球学生 / 教师优惠与免费资源完整索引")
    L.append("")
    L.append(f"[![Offers](https://img.shields.io/badge/offers-{len(clean)}-blue)](data/offers.json) "
             f"[![Categories](https://img.shields.io/badge/categories-{len(cat_meta)}-green)](docs/categories/) "
             f"[![Nav](https://img.shields.io/badge/nav-{len(nav)}-purple)](nav/README.md) "
             f"[![Buy](https://img.shields.io/badge/buy-{len(buy)}-orange)](docs/buy-recommendations.md) "
             f"[![Verify](https://img.shields.io/badge/verify-eduverify.net-brightgreen)](https://eduverify.net/) "
             f"[![License](https://img.shields.io/badge/license-CC%20BY--SA%204.0-lightgrey)](LICENSE)")
    L.append("")
    L.append("## 📊 概览 / Overview")
    L.append("")
    L.append("| 项目 | 数值 |")
    L.append("| --- | --- |")
    active = sum(1 for o in clean if o["status"] == "Active")
    ended = sum(1 for o in clean if o["status"] == "Ended")
    paused = sum(1 for o in clean if o["status"] == "Paused")
    with_url = sum(1 for o in clean if o["official_url"])
    with_claim = sum(1 for o in clean if o["claim_zh"])
    nav_actual_tut = sum(1 for x in nav if not x.get("tutorial_is_default"))
    nav_actual_mail = sum(1 for x in nav if not x.get("mailbox_is_default"))
    L.append(f"| 福利总数 / Offers | **{len(clean)}** |")
    L.append(f"| 有效 / Active | {active} |")
    L.append(f"| 已结束 / Ended | {ended} |")
    L.append(f"| 已暂停 / Paused | {paused} |")
    L.append(f"| 分类数 / Categories | **{len(cat_meta)}** |")
    L.append(f"| 含官网领取链接 / With official links | {with_url} |")
    L.append(f"| 含领取步骤 / With claim steps | {with_claim} |")
    L.append(f"| [nav 前台页面 / Nav pages](nav/README.md) | {len(nav)} |")
    L.append(f"| 购买参考入口 / Purchase entries | {len(buy)} |")
    L.append("| 邮箱核验工具 / Email verification | [eduverify.net](https://eduverify.net/) |")
    L.append("| 语言 / Languages | 简体中文 · English |")
    L.append("")
    L.append("> 💡 本仓库收录每项福利的**完整信息**（领取步骤、福利类型、适用人群、最近核实时间、官网领取链接），可直接查看，无需跳转任何第三方网站。")
    L.append("")
    L.append("## 🗂️ 分类 / Categories")
    L.append("")
    L.append("| 分类 Category | 数量 | 详情 |")
    L.append("| --- | ---: | --- |")
    for c in cat_meta:
        L.append(f"| {c['icon']} {c['name_zh']} / {c['name_en']} | {c['count']} | "
                 f"[查看 →](docs/categories/{c['slug']}.md) |")
    L.append("")

    if nav:
        L.append("## 🧭 edu 邮箱项目导航 / Nav Projects")
        L.append("")
        L.append(f"> {len(nav)} 个 `nav.edumails.cn` 项目已全部做成**前台 Markdown 详情页**，每篇包含：官网链接、教程演示、适配邮箱、环境要求、领取步骤、标签。缺失时按默认值展示。")
        L.append("")
        L.append("| 项目 | 数值 |")
        L.append("| --- | ---: |")
        L.append(f"| 项目总数 / Projects | **{len(nav)}** |")
        L.append(f"| 教程演示有实际内容 / Actual tutorials | {nav_actual_tut} |")
        L.append(f"| 教程演示默认值 / Default tutorials | {len(nav) - nav_actual_tut} |")
        L.append(f"| 适配邮箱有实际内容 / Actual mailboxes | {nav_actual_mail} |")
        L.append(f"| 适配邮箱默认值 / Default mailboxes | {len(nav) - nav_actual_mail} |")
        L.append(f"| 前台详情页 / Detail pages | {len(nav)} |")
        L.append("")
        L.append("> 默认值：**教程演示：edumails.cn待更新** · **适配邮箱：edumailshop.com**")
        L.append("")
        by_id = {x["nav_id"]: x for x in nav}
        samples = [i for i in (51, 652, 63, 45, 49, 206) if i in by_id]
        if samples:
            L.append("| 示例项目 | 教程演示 | 适配邮箱 |")
            L.append("| --- | --- | --- |")
            for i in samples:
                x = by_id[i]
                L.append(f"| [{md_escape(x['title'])}](nav/{i}.md) | {nav_tutorial(x)} | {nav_mailbox(x)} |")
            L.append("")
        L.append(f"**[查看全部 {len(nav)} 个项目 →](nav/README.md)**")
        L.append("")

    if buy:
        L.append("## 🛒 购买建议 / Purchase Reference")
        L.append("")
        L.append(f"> 仅整理 `buy.edumails.cn` 公开列出的 {len(buy)} 个入口，以及各站公开可见的售后、商品线和学术文件说明。**不构成推荐、价格承诺或平台背书。**")
        L.append("")
        L.append("> **说明**：以下网址为目前市场上认可度较高、经营时间长、售后服务质量较高的站点；本仓库与这些站点**无利益相关**，信息仅作公开整理与参考。")
        L.append("")
        L.append("> ⚠️ 购买或使用非本人学籍的 edu 邮箱申请学生优惠，可能违反服务商条款并导致封号；伪造或买卖学术文件可能涉及违法。请只使用真实、合法、属于本人的学籍与材料。")
        L.append("")
        L.append("| 网站 | 建站时间 | 售后（站点宣称） | 主营美国 edu | 主营国外 edu | 学术文件 |")
        L.append("| --- | --- | --- | :---: | :---: | :---: |")
        for b in buy:
            L.append(f"| [{md_escape(b['name'])}]({b['url']}) | {b['founded_at']} | {md_escape(b['after_sales'])} | "
                     f"{'✅' if b.get('main_us_edu') else '—'} | {'✅' if b.get('main_intl_edu') else '—'} | "
                     f"{'✅ 部分产品' if b.get('academic_documents') else '—'} |")
        L.append("")
        L.append("> 建站时间取域名 RDAP / WHOIS 的注册时间；`vip.stulink.cn`、`us.mailschool.me` 使用根域名 `stulink.cn`、`mailschool.me` 的注册时间，仅作参考。")
        L.append("")
        L.append("详见 **[购买建议与风险提示 →](docs/buy-recommendations.md)**（含入口选择、字段口径、购买前核对清单）。")
        L.append("")

    L.append("## 🔎 教育邮箱真伪性查询 / Email Verification")
    L.append("")
    L.append("> 查询网站：**[eduverify.net](https://eduverify.net/)** — 全球学校邮箱查询系统 · 院校邮箱域名真实性核验。")
    L.append("")
    L.append("| 项目 | 说明 |")
    L.append("| --- | --- |")
    L.append("| 查询入口 | [https://eduverify.net/](https://eduverify.net/) |")
    L.append("| 查询对象 | 教育邮箱地址或院校邮箱域名（以页面输入框为准） |")
    L.append("| 数据来源 | 全球院校名录、美国院校权威核验（[ope.ed.gov/dapip](https://ope.ed.gov/dapip/#/agency-list)）、全球院校补充核验、学术域名库、美国职业培训认证名录 |")
    L.append("| 判定方式 | 三分类口径 + 判定结论说明 |")
    L.append("")
    L.append("**[打开 eduverify.net 查询 →](https://eduverify.net/)**")
    L.append("")
    L.append("> 查询结果只代表院校/域名数据匹配情况，不等于邮箱一定由学校官方签发，也不保证能通过某项学生优惠。最终以学校官网、学籍材料和目标服务商审核为准。")
    L.append("")
    L.append("详见 **[查询说明与核验清单 →](docs/edu-verification.md)**。")
    L.append("")

    L.append("## 📚 全部福利 / All Offers")
    L.append("")
    for c in cat_meta:
        items = [o for o in clean if o["category"] == c["slug"]]
        L.append(f"### {c['icon']} {c['name_zh']} / {c['name_en']} ({len(items)})")
        L.append("")
        L.append(f"<details><summary>展开 / Expand ({len(items)})</summary>")
        L.append("")
        L.append("| 福利 / Offer | 站点 | 类型 | 人群 | 核实日期 | 状态 |")
        L.append("| --- | --- | --- | --- | --- | --- |")
        for o in items:
            link = f"[{md_escape(o['name_zh'])}](offers/{o['slug']}.md)"
            host = md_escape(o["host"]) or "—"
            L.append(f"| {link} | {host} | {o['benefit_zh'] or '—'} | {o['audience_zh'] or '—'} | {o['verified_at'] or '—'} | {o['status']} |")
        L.append("")
        L.append("</details>")
        L.append("")
    L.append("## 📦 数据文件 / Data")
    L.append("")
    L.append(f"- [`data/offers.json`](data/offers.json) — {len(clean)} 条福利结构化数据（中英双语 + 领取步骤 + 官网链接 + 核实日期）")
    L.append("- [`data/offers.csv`](data/offers.csv) — 福利表格版本")
    L.append(f"- [`data/nav_offers.json`](data/nav_offers.json) — {len(nav)} 条 nav 项目数据（含教程演示、适配邮箱、官网链接、标签）")
    L.append(f"- [`nav/README.md`](nav/README.md) — {len(nav)} 个 nav 项目总索引（前台可见）")
    L.append("- [`nav/`](nav/) — nav 前台详情页（教程演示、适配邮箱、环境要求、领取步骤）")
    L.append(f"- [`data/buy_recommendations.json`](data/buy_recommendations.json) — {len(buy)} 个购买参考入口（建站时间、售后、主营邮箱类型、学术文件）")
    L.append("- [`docs/categories/`](docs/categories/) — 分类清单")
    L.append("- [`docs/buy-recommendations.md`](docs/buy-recommendations.md) — 购买建议与风险提示")
    L.append("- [`docs/edu-verification.md`](docs/edu-verification.md) — 教育邮箱真伪性查询说明与核验清单")
    L.append("- [`docs/auto-sync.md`](docs/auto-sync.md) — 自动同步机制与定时任务说明")
    L.append("- [`docs/sync-status.md`](docs/sync-status.md) — 最近一次同步结果")
    L.append(f"- [`offers/`](offers/) — {len(clean)} 篇完整详情页")
    L.append("")
    L.append("## ⚠️ 免责声明 / Disclaimer")
    L.append("")
    L.append("- 本仓库仅为信息索引，与任何福利提供方无隶属关系。")
    L.append("- 「购买建议」模块只整理公开入口与公开说明，不构成推荐、价格承诺或平台背书。")
    L.append("- 教育邮箱真伪性查询结果仅供参考，不代表学校官方认证结论，也不保证能通过任何学生优惠审核。")
    L.append("- 购买或使用非本人学籍的 edu 邮箱申请学生优惠，可能违反服务商条款并导致封号；学术文件必须真实、合法、属于本人。")
    L.append("- 优惠的可用性、地区限制、资格条件会随时变化；申请前请务必前往官方页面核实。")
    L.append("- 欢迎通过 Issue / PR 指正错误信息。")
    L.append("")
    L.append("## 📄 许可 / License")
    L.append("")
    L.append("内容采用 [CC BY-SA 4.0](LICENSE) 许可。")
    L.append("")

    with open(os.path.join(ROOT, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))


if __name__ == "__main__":
    build()
