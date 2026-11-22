# 🔄 自动同步说明 / Auto Sync

本仓库通过定时任务持续跟踪公开福利目录：当上游新增、移除或更新项目时，仓库中的数量统计、分类清单、详情页和 README 会一起重建，不需要手工改数字。

## 工作方式

1. **抓取目录**：读取上游中英文目录数据；目录完整嵌入在页面服务端渲染数据中。
2. **发现变化**：按项目标识（slug）对比上次已发布数据，识别新增与移除项目。
3. **补齐详情**：抓取详情页，提取领取步骤和最近核实日期；抓取失败时沿用上次已核实内容。
4. **解析官网链接**：通过官方跳转端点解析真实领取地址。
5. **重建前台**：重新生成 `data/offers.json`、`data/offers.csv`、`docs/categories/*.md`、`offers/*.md` 和 `README.md`。
6. **提交推送**：如果生成结果有变化，定时任务自动提交并推送到 `main` 分支。

数量统计（例如福利总数、分类数、nav 项目数、购买入口数）全部由数据长度动态生成；上游从 301 个增加到 302 个时，徽章、概览表、分类数量、README 正文和数据文件描述会同步变成 302，无需手动修改。

## 当前定时任务

已配置 WorkBuddy 定时任务：**每天 08:00（北京时间）** 自动执行同步脚本，并在有改动时提交推送到 GitHub。

任务流程：运行 `python3 sync_from_source.py` → 检查文件变化 → `git commit` → `git push origin main`；若上游不可用或数据异常，脚本会中止且不推送任何内容。

## GitHub Actions（可选）

本地已准备好工作流文件 `.github/workflows/sync.yml`，每天 UTC 03:30 运行，也支持手动触发。当前推送使用的 Classic PAT 未勾选 `workflow` 权限，GitHub 拒绝写入该文件，因此它尚未在仓库中生效。

启用方式二选一：

1. 给 PAT 增加 `workflow` scope 后重新推送该文件；或
2. 在 GitHub 网页端手动新建文件 `.github/workflows/sync.yml`，粘贴本地同名文件内容后提交。

启用后可在 **Actions → Sync offer catalog → Run workflow** 手动触发。

## 安全约束

- 目录数据缺失或数量异常减少时直接中止，不会用空数据覆盖仓库。
- 详情页或跳转链接抓取失败时保留上次已核实的字段，不会生成空白详情页。
- 同步结果记录到 [`docs/sync-status.md`](sync-status.md)，包括新增/移除项目和字段回退数量。

## 本地手动同步

```bash
python3 sync_from_source.py
```

如需在本地同步后直接提交推送：

```bash
SYNC_PUSH=1 python3 sync_from_source.py
```

> 本地运行需要可访问上游站点；若受网络环境影响，脚本会保留已有数据并中止，不会破坏仓库内容。
