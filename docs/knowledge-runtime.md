# Knowledge Runtime 数据契约

本文档描述 `KnowledgeAtomV2` 契约、稳定 ID、知识路径发现，以及已接入 Runtime 的
增长分层注入（v1.2.8 起）与 skills 绑定消费（v1.3.x 起）。

## 真源与隔离

- JSONL 是可审计真源，索引只能作为可重建派生物。
- `public`、`expert_private`、`client_private` 三层严格隔离。
- `client_private` 必须有 `client_id`，且禁止 `exportable=true`。
- 只有经人工审核的 `approved` 原子才具备进入正式检索的资格；发布批次门在后续 PR 实现。

## 稳定 ID

- `source_id = src_ + sha256(normalized_source_identity)[:12]`
- `atom_id = ka_ + sha256(source_id + locator + local_index)[:16]`

ID 由代码生成。修改来源身份、来源定位或来源内序号会得到新 ID；调整无关展示字段不会改变 ID。

## 路径优先级

读取候选按以下顺序发现：

1. `SIYU_KNOWLEDGE_HOME`
2. `~/.siyu-team/knowledge/`
3. 仓库 `knowledge/`
4. Python package resources
5. 独立 Skill bundle 的 `modules/_knowledge/`

私有写入只允许进入显式环境变量目录或 `~/.siyu-team/knowledge/`。默认创建权限为目录 `0700`；后续写文件必须使用 `0600`。

## V1 迁移边界

`migrate_v1_atom()` 将旧示例迁移为 `draft + exportable=false + evidence_grade=D`。迁移不会自动批准知识，也不会把旧摘录当作已验证行业事实。

## 尚未实现

- 导入、人工审阅、隐私审计与 CLI
- 本地检索、KnowledgeBundle 和冲突处理（SkillHub 包已随包分发 `modules/_knowledge/` 静态副本）
- 正式语料、发布批次与版本升级

## 公开方法层（v1.2.4/v1.2.8）

`knowledge/00-methodology/用增方法映射-餐饮零售.md` 是可引用的增长方法真源（非 Atom JSONL）。Skill 与问诊可直接引用；**不等于**已批准 Atom，也不自动进入 Runtime 检索。


## 增长分层 L0/L1（已实现文档路由）

- 选择器：`siyu_team.knowledge.growth_layers`
- `route_task` 对非市场调研任务自动注入：
  - 无业态 → `L0-通用用户增长原则.md`
  - catering/retail → L0 + `L1-餐饮零售用增Know-how.md`
- 正式集原子：`knowledge/04-atoms/growth-layers.approved.jsonl`（`load_growth_atoms(industry)`）
- **仍不**把 draft 原子自动当 approved 检索真源；Pilot 正式集规则不变
- 旧文 `用增方法映射-餐饮零售.md` 降级为中间稿

## 诊断上下文注入（v1.2.8）

- `SiyuRuntime.plan` 在 `diagnosis` / `strategy_review` 时调用 `format_growth_atoms_for_context(industry)`
- 计划字段：`growth_atoms`、`growth_load_note`
- 全盘诊断：写入四位专家 `shared_fields`（`growth_atoms` / `growth_load_note` / `knowledge_refs`）
- Trace：`growth_atoms.attached`
- 轻问诊 skill 优先消费计划中的原子列表

增长原子自 v1.2.8 起为 **approved 正式集**，进 Pilot 夹具与诊断上下文；重建用 `tools/build_growth_atoms.py`。

## skills 绑定消费（v1.3.x）

- 每条 v2 原子的 `skills` 字段是「原子 → skill」的绑定声明，构建期由
  `tools/build_growth_atoms.py` 对照 `plugins/**/SKILL.md` 目录名硬校验（悬空即失败）。
- 运行时：`format_growth_atoms_for_context` 输出的每行带 `skills`，四官可按归属取干货；
  `filter_atoms_by_skills` / `select_atoms_for_skill` 供按 skill 过滤。
- skill 侧：被绑定的能力 skill 在 SKILL.md「绑定的增长干货原子」小节给出
  `tools/atoms_query.py --skills <name>` 查询入口（双轨兼容 v1/v2）。
- 回归：`tests/test_growth_layers.py::SkillBindingTests` 做绑定双向对账；
  `make atoms` 卡本体校验与夹具零漂移。
