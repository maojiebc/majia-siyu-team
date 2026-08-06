# Knowledge Runtime 数据契约

当前阶段只建立 `KnowledgeAtomV2` 契约、稳定 ID 和知识路径发现，不接入 Runtime。

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

## 本阶段未实现

- 导入、人工审阅、隐私审计与 CLI
- 本地检索、KnowledgeBundle 和冲突处理
- Runtime、四官上下文和 Trace 注入
- 正式语料、发布批次与版本升级

## 公开方法层（v1.2.4/v1.2.5）

`knowledge/00-methodology/用增方法映射-餐饮零售.md` 是可引用的增长方法真源（非 Atom JSONL）。Skill 与问诊可直接引用；**不等于**已批准 Atom，也不自动进入 Runtime 检索。

