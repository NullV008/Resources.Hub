# 贡献指南 / Contributing

感谢你对本仓库的关注！这是一个学生优惠信息的索引仓库，欢迎任何形式的改进。

## 你可以做什么

- **纠错**: 发现失效链接、错误描述、过期福利 → 提交 Issue 或 PR
- **补充**: 新增尚未收录的学生 / 教师优惠
- **翻译**: 改进中英文表述
- **结构化**: 完善 `data/offers.json` 字段

## 数据说明

所有内容来自公开网页 [edu.52it.de](https://edu.52it.de/) 的抓取快照。

- `data/category_*.json` — 按分类的原始抓取数据
- `data/offers.json` — 合并后的统一数据集
- `data/offers.csv` — 表格版本

如需重新生成派生文件：

```bash
python3 build.py            # 合并分类数据 → offers.json / offers.csv / categories.json / docs/
python3 generate_readme.py  # 重新生成 README.md
```

## PR 规范

1. Fork 仓库并创建分支
2. 修改 `data/category_<分类>.json`（保持 schema 一致）
3. 运行 `python3 build.py && python3 generate_readme.py`
4. 提交 PR，并说明数据来源链接

## 免责声明

本仓库仅作信息索引，与 edu.52it.de 及任何福利提供方无隶属关系。优惠随时可能变化，使用前请以官方页面为准。
