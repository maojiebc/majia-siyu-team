# 公开知识原子与严格装配

本目录的 `growth-layers.approved.jsonl` 是可分发的 v2 公开正式集。
`knowledge/manifest.json` 记录其版本、发布批次、原始字节 SHA-256、原子数和
Schema 版本。`editorial-approved` 只表示完成编辑与安全门审，不表示
Pilot 或真实业务效果已验证。

## 三份发布副本

| 使用面 | 位置 | 产生方式 |
|---|---|---|
| 仓库真源 | `knowledge/` | 人工审批后更新 manifest 与 approved JSONL |
| wheel package data | `src/siyu_team/knowledge/data/` | `tools/sync_public_knowledge.py` 从仓库真源生成 |
| SkillHub | `skillhub/majia-siyu/modules/_knowledge/` | bundle 从 package data 生成 |

三处的 `manifest.json` 和 approved JSONL 必须字节一致，因而
`corpus_hash`、`atom_count`、`atom_schema_version` 一致。验证命令：

```bash
python3 tools/sync_public_knowledge.py --check
python3 tools/build_skillhub_bundle.py --check
make atoms
```

公开生成物只复制白名单目录；私有 SOP、客户数据与未审批草稿不得进入
wheel 或 SkillHub。

## v2 严格加载门

`CorpusLoader` 只发现 manifest 声明的 `*.approved.jsonl`，不回退 draft。
高优先级目录只有 draft 时，不会遮蔽低优先级的 approved 正式集。
所有合法来源都不存在时，Runtime 以“当前无可用公开知识库”降级；
一旦候选正式集存在，manifest 或 corpus 损坏则 fail-closed。

正式加载同时检查：

- manifest 必填字段，以及 manifest 顶层与 corpus descriptor 一致性；
- approved JSONL 原始字节哈希、非空行数与 `atom_count`、Atom Schema 版本；
- `atom_id` 唯一；
- `review_status=approved`、`visibility=public`、`exportable=true`；
- 不含 PII、不含客户秘密，且生命周期当日可用；
- 过期、未生效、被替代、retired 或 rejected 的原子不进入正式 Corpus；
- approved 原子必须具备成立条件、建议动作、验证指标或不适用说明，
  以及失效边界或反例。

malformed JSON 默认拒绝整个候选集。`--lenient` 只用于开发排查时跳过无法解析的行；
它不关闭 manifest、哈希、数量、重复 ID 或安全门。

## 按任务相关性装配

`KnowledgeAssembler(task, decision)` 消费严格 Corpus，而不是截取文件前 40 条。
它会正规化路由 skill slug，结合任务类型、目标、文本、业态、skill 绑定与
applicability 做确定性排序，默认最多选择 12 条。每条结果都带
`why_selected`、来源定位和适用边界，JSONL 行顺序不影响选择结果。

当前行业层承诺保持不变：

- 未声明业态与 `edu` 只选 L0；
- `catering` 与 `retail` 可共享已发布的“餐饮零售” L1；
- `retail` 仍是 `generic_only`，不宣称存在独立零售行业册。

Runtime 和 Pilot 调用同一个 Assembler。Pilot 的人工 mapping 只是“期望选择结果”
夹具，不再直接决定注入内容。这证明装配机制对齐，不是 H1/H2/H3 结论。

## 查询与校验

在仓库、安装 wheel 所带的 package data 或 SkillHub bundle 中，
`atoms_query.py` 默认发现对应的公开 Corpus，无需指向私有路径：

```bash
python3 tools/atoms_query.py --skills siyu-qunfa
python3 tools/atoms_query.py --topics activity_increment --limit 10
python3 tools/atoms_query.py 复购 召回
```

显式 `--file` 仍支持单补丁周期的 v1 兼容查询；正式 v2 查询仍由
`CorpusLoader` 执行 manifest 与安全门。

```bash
python3 tools/atoms_validate.py modules/_knowledge/04-atoms/growth-layers.approved.jsonl
PYTHONPATH=src python3 tools/build_growth_atoms.py
python3 tools/sync_public_knowledge.py --check
```

`tools/build_growth_atoms.py` 重建公开正式集和 Pilot 语料夹具；
`tests/fixtures/pilot/growth-task-atom-map.json` 仅保留为期望结果夹具。
