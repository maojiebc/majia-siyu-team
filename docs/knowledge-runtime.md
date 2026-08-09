# Knowledge Runtime 数据契约

本文档描述公开 `KnowledgeAtomV2` 从仓库真源、wheel package data 到 SkillHub
的分发契约，以及 Runtime 与 Pilot 共用的严格加载和相关性装配。

## 真源、副本与隔离

- JSONL 是可审计真源，索引只能是可重建派生物。
- `public`、`expert_private`、`client_private` 三层严格隔离。
- 含 PII 或客户秘密的原子一律不得 `exportable=true`；
  `client_private` 还必须有 `client_id`。
- 公开 Runtime 只消费经人工审批的 approved 原子，不会回退 draft。

公开知识有三份字节一致的发布副本：

```text
knowledge/                                      # 仓库真源
  └─ manifest.json + 04-atoms/*.approved.jsonl
       │  tools/sync_public_knowledge.py
       ▼
src/siyu_team/knowledge/data/                   # wheel package data
       │  tools/build_skillhub_bundle.py
       ▼
skillhub/majia-siyu/modules/_knowledge/         # SkillHub 副本
```

`tools/sync_public_knowledge.py --check` 和安装态回归保证三处 manifest、approved JSONL、
`corpus_hash`、`atom_count` 和 Schema 版本一致。私有知识不在公开同步白名单内。

## 稳定 ID

- `source_id = src_ + sha256(normalized_source_identity)[:12]`
- `atom_id = ka_ + sha256(source_id + locator + local_index)[:16]`

ID 由代码生成。修改来源身份、来源定位或来源内序号会得到新 ID；
调整无关展示字段不会改变 ID。

## 发现与严格 CorpusLoader

默认候选根目录按以下优先级发现：

1. `SIYU_KNOWLEDGE_HOME`；
2. `~/.siyu-team/knowledge/`；
3. 仓库 `knowledge/`；
4. Python package resources；
5. 独立 SkillHub bundle 的 `modules/_knowledge/`。

`KnowledgePathResolver.approved_corpus_candidates()` 只返回 approved 候选，因此高优先级根目录中的
draft 不会遮蔽低优先级的 approved 正式集。所有 approved 来源缺失时，
Loader 返回带明确 warning 的空 Corpus；只要候选正式集存在，其契约损坏就
fail-closed。

`CorpusLoader` 的硬门包括：

- manifest 必填字段，以及顶层与 `public_corpora` descriptor 一致；
- approved JSONL 原始字节 SHA-256、非空行数、Atom Schema 版本和唯一 ID；
- `review_status=approved`、`visibility=public`、`exportable=true`；
- no PII、no client secret；
- valid-from 已到、未过期、未被活跃新版 supersede；
- rejected、retired、future-valid、expired 和被替代原子不进入正式 Corpus；
- approved 原子必须有 precondition、action、metric 或不适用说明，
  以及 failure mode/counterexample。

malformed JSON 默认使整个候选集失败。显式 `--lenient` 只允许开发排查时跳过
无法解析的单行，不会关闭 manifest、哈希、数量、重复 ID 或安全门。

## KnowledgeAssembler

`KnowledgeAssembler(task, decision)` 是 Runtime 和 Pilot 的统一选择入口。它：

- 先消费 `CorpusLoader` 产生的安全 Corpus；
- 正规化 route skill slug，再结合 skill 绑定、任务类型、目标、文本、
  业态、主题、场景和 applicability 选择；
- 默认最多返回 12 条，不再按文件顺序取前 40 条；
- 以相关分、置信度、证据等级和稳定 ID 做确定性排序；
- 为每条结果输出 `why_selected`、`source_id`、`locator` 和完整适用边界。

行业层选择保留当前产品承诺：

- 未声明业态与 `edu` 只使用 L0；
- `catering` 和 `retail` 可共享已发布的“餐饮零售” L1；
- `retail` 仍为 `generic_only`，不宣称有独立零售行业册。

`ExecutionPlan.knowledge` 记录 `corpus_version`、`corpus_hash`、
`selection_count` 与所选原子，可用于回放和审计。

## Runtime、Pilot 与查询

Runtime 使用结构化 Task 和 RouteDecision 调用 Assembler，再将选择结果写入
`ExecutionPlan.knowledge` 与受限上下文。Pilot 使用同一个 Assembler；人工 mapping
只用作期望选择夹具，不再直接装配 prompt。

这只证明生产与 Pilot 的选择机制对齐。在完成真实评审前，
H1 知识价值、H2 贡献动力、H3 审核吞吐仍全部是 `Not Evaluated`；
不得把 Dry Run、夹具或安装态回归表述为知识效果或同行共建已成立。

`tools/atoms_query.py` 默认通过同一个 `CorpusLoader` 发现公开 Corpus，
可在仓库、安装 wheel 的 package data 与 SkillHub 副本上作。

```bash
python3 tools/atoms_query.py --skills siyu-qunfa
python3 tools/atoms_query.py --topics repurchase_recall --limit 10
python3 tools/atoms_query.py 复购 召回
```

查询结果携带 corpus 版本与哈希。没有合法公开 Corpus 时正常返回 0 条；
候选正式集损坏时默认 fail-closed。

## 生成与验收

```bash
PYTHONPATH=src python3 tools/build_growth_atoms.py
python3 tools/atoms_validate.py knowledge/04-atoms/growth-layers.approved.jsonl
python3 tools/sync_public_knowledge.py --check
python3 tools/build_skillhub_bundle.py --check
make atoms
make check
```

`growth-layers.approved.jsonl` 的 manifest 状态是 `editorial-approved`：它表示已通过
结构、完整性与安全门，不代表已完成真实效果验证。
