# 私域「一条条能干货」库（知识原子）

「知识原子」就是把长语料拆成可检索、可追溯、可反向绑定 skill 的最小陈述。公开仓库只保存 schema 与脱敏示例；真实语料固定写入 `knowledge/03-majia-sop/atoms.jsonl`，受 `.gitignore` 保护。

## 三层知识分工

1. 高频判断与必要案例内联在 `SKILL.md`，单文件不超过 8KB。
2. 深度方法论放在 skill 的 `references/` 或 `modules/_knowledge/00-methodology/`。
3. 全量真实语料原子化后放入私有 `atoms.jsonl`，只通过指针查询，不复制到公开层。

## 双轨 Schema：v1 私有库 / v2 正式集

本目录同时存在两套合法格式，**不要混淆**：

| 轨道 | 文件 | ID 形态 | 校验真源 |
|---|---|---|---|
| v1（私有语料轨） | `knowledge/03-majia-sop/atoms.jsonl`、本目录 `atoms.example.jsonl` | `{季度}_{序号}`，如 `2026Q3_001` | `tools/atoms_validate.py` 内置规则（见下表） |
| v2（公开正式集轨） | 本目录 `growth-layers.approved.jsonl` | `ka_` + 16 位十六进制（内容寻址，代码生成） | `schema/atom-v2.schema.json` + `src/siyu_team/knowledge/models.py` |

`tools/atoms_validate.py` 与 `tools/atoms_query.py` 已双轨兼容（按行嗅探 `schema_version`），
两轨都做 id 唯一性与 skills 存在性校验；`make atoms` 把两个公开文件与 Pilot 夹具同步一起卡进 `make check`。

## v1 Schema（私有语料轨）

| 字段 | 类型 | 规则 |
|---|---|---|
| `id` | string | `{季度}_{序号}`，如 `2026Q3_001`；全文件唯一 |
| `knowledge` | string | 人工提炼的独立陈述句，不能为空 |
| `original` | string | 脱敏原文，最多 200 字 |
| `source` | string | 本地语料相对路径；不写个人隐私或外部密钥 |
| `date` | string | `YYYY-MM-DD` |
| `topics` | string[] | 1—10 个受控主题 |
| `skills` | string[] | 至少绑定一个仓库内真实存在的 skill 目录 |
| `type` | string | `principle`、`method`、`case`、`anti-pattern`、`insight`、`tool` |
| `confidence` | string | `high`=亲历实测；`medium`=观察归纳；`low`=转述待验证 |

## 主题枚举

`社群运营`、`内容运营`、`用户增长`、`转化`、`留存`、`复购`、`合规`、`活动`、`话术`、`数据`

首版保持十类以内；需要新增主题时先更新本文件与 validator，不能在数据里自由造同义词。

## 半自动流程

```bash
# 1. 按段落切候选草稿；knowledge 故意留空
python3 tools/atoms_extract.py <语料目录> --output /tmp/atoms-draft.jsonl

# 2. 人工补 knowledge、topics、skills、type、confidence，并核对脱敏与日期

# 3. 校验最终文件
python3 tools/atoms_validate.py modules/_knowledge/04-atoms/atoms.example.jsonl

# 4. 按 skill、主题、类型或关键词查询
python3 tools/atoms_query.py --file modules/_knowledge/04-atoms/atoms.example.jsonl --skills siyu-pyq
python3 tools/atoms_query.py --file modules/_knowledge/04-atoms/atoms.example.jsonl 留存 欢迎语
```

`atoms_extract.py` 不做自动提炼。草稿里的空 `knowledge` 会被 validator 拦下，必须人工定稿后才能进入正式库。

## 公开与私有边界

- `atoms.example.jsonl`：公开脱敏测试数据，不含真实品牌、人名、客户数据和私有阈值。
- `knowledge/03-majia-sop/atoms.jsonl`：真实原子库，不提交、不复制进文档、不出现在 commit。
- 原文含敏感内容时，在进入私有库前也应做最小化处理；本地纯文本不等于加密存储。

## 增长正式集（L0/L1）

- 文件：`growth-layers.approved.jsonl`（公开方法，可进 Git）
- 重建：`PYTHONPATH=src python3 tools/build_growth_atoms.py`
- 主题：每条恰好一个 Pilot 主题（`add_wechat` / `activity_increment` / `repurchase_recall`）+ `growth_l0` 或 `growth_l1_catering`
- 任务计划/问诊诊断：`load_growth_atoms(industry)` 优先读本文件
- Pilot 夹具：`tests/fixtures/pilot/growth-approved-atoms.jsonl` + `growth-task-atom-map.json`
- 本机私有副本（0600）：`~/.siyu-team/knowledge/approved/growth-layers.atoms.jsonl`

