# 当前执行架构

本文记录仓库当前可由代码和分发产物验证的事实。创建期设计保留在
[`blueprint.md`](blueprint.md)，v0.4.0 的历史 Runtime 说明保留在
[`runtime-v0.4.md`](runtime-v0.4.md)。

## 三条现有执行链

| 执行面 | 当前真实入口 | 已自动验证 | 尚未闭环 |
|---|---|---|---|
| 插件与 SkillHub | Markdown Skill 由宿主解释执行 | 文件结构、发布版本、生成路由契约、84 条人工对照、公开知识副本一致性 | Prompt-only 不具备代码强制隔离/追踪 |
| Python Runtime | `siyu-plan` / `SiyuRuntime.plan()` | ExecutionPlan v1、Task、路由、上下文隔离、默认 metadata Trace、严格 Corpus 与相关性装配、安装态回归 | Markdown 宿主是否真正调用 Runtime；plan 本身不执行专家 Prompt |
| Knowledge Pilot | `siyu-pilot` 与离线夹具 | 盲化、数据契约、Dry Run 工具、与 Runtime 共用 `KnowledgeAssembler` | H1/H2/H3 真实人工评估 |

这三个执行面目前仍非同一条强制生产链：Markdown 宿主可以处于
Prompt-only 模式。知识分支已收敛为共用的 `CorpusLoader` 与 `KnowledgeAssembler`，
但这只证明装配机制一致；Pilot 工具可运行不能推导出知识已经改善真实回答。

## 当前可验证链路

```text
用户请求
  ├─ CLI 可用且契约哈希匹配：siyu-plan → ExecutionPlan(runtime_mode=python)
  └─ 否则：生成 route-contract.json → Prompt-only 计划(runtime_mode=prompt_only)

ExecutionPlan
  ├─ 单能力路由
  └─ 信息齐备的全盘任务 → 四官白名单上下文

本地运行状态（独立组件，不由每次 plan 自动创建）
  ├─ StateStore → .siyu-team/runs/{run_id}/
  ├─ current → 当前 run 指针
  └─ revision + 文件锁 + 原子替换 → 并发更新不覆盖

公开 approved Corpus
  ├─ CorpusLoader → manifest/hash/count/schema/安全/生命周期硬门
  └─ KnowledgeAssembler(task, decision)
       ├─ Runtime → 默认最多 12 条 + why_selected
       └─ Pilot → 同一选择逻辑，mapping 仅作期望夹具

质量与合规工具
  ├─ ScanMode 静态合规门 → 只报告可解释命中
  ├─ 粗糙度启发式 → 与违规判定、质量分分离
  └─ 独立 Judge + 完整 JudgeReport → 才有质量分与徽章
```

`plugins/.../references/route-contract.json` 与
`skillhub/.../modules/_runtime/route-contract.json` 均由 Python 常量生成，字节和
`content_sha256` 必须一致。SkillHub 包不含 Python Runtime，因此不能因为携带该契约
就宣称执行过 Runtime；Python 模式必须先用 `siyu-plan --contract-info` 完成哈希握手。
包内的严格知识查询工具只证明 Corpus 可发现，不会把 Prompt-only 模式变成
Python Runtime 模式。

三个执行文案 lint 与 Runtime 使用同一套 mode-aware 合规扫描器；SkillHub 随包携带
这套最小扫描支持，因此不会在独立安装时退回另一份粗糙词表。正常序号、否定、引用、
归因和风险说明可解释地降级，清晰的广告绝对化主张与诱导分享仍按模式阻断。

`make compliance` 只产生合规结果；`make judge` 接收独立宿主回填并生成机器可读
`JudgeReport`。只有完整维度、逐维理由、来源、模型、配置、ISO 时间和独立评审方式
同时存在时，报告才可含质量分与徽章。分数不会自动批准案例入库或知识原子；缺失
独立评审时，主编排固定记录“本轮未做独立质量评分”。`make eval` 仅保留一个版本的
deprecated 静态合规兼容别名。

## 运行状态、追踪与 Prompt 边界

- `TraceRecorder` 默认 `metadata`，不保存原始 `source_text`、客户上下文或完整路由
  理由；只保留长度、SHA256、kind、risk、route、知识定位和错误码等元数据。
  `redacted` 与 `full` 只能通过 `--trace-level` 显式选择。Recorder 启动及写入后按
  TTL、总字节数和文件数上限清理旧 JSONL。
- `StateStore` 把状态隔离在 `.siyu-team/runs/{run_id}/`，每个 run 有自己的
  `state.json`、`task.json`、`outputs/` 和 `traces/`；`.siyu-team/current` 只是
  当前 run 指针。更新在文件锁内完成，`revision` 与可选 `expected_revision` 提供
  compare-and-swap 冲突检测。
- 旧 `.siyu-team/state.json` 只读复制到新 run，旧文件原样保留。迁移不会删除或
  继续回写用户的旧状态。
- `SiyuRuntime.plan()` 在生成四官面板时检查 `required_any_of` 与上下文大小；任一官
  不足就不返回整组 `agent_contexts`，并以 `context_incomplete` warning 和澄清字段
  收口。`build_isolated_officer_prompt()` 在真正派发前再执行一次同样的 fail-closed
  检查，避免绕过计划层直接构造 Prompt。
- 用户输入、外部知识/证据和官员输出均编码为 `untrusted_data`。数据块内要求忽略
  上文、读取密钥、调用工具或执行命令的文字只可作为待分析数据；Host 对官员输出
  校验最低结构和大小，并以 `data_only` 材料收口。
- `siyu-save` 默认只存结构化结论，写盘前展示敏感信息掩码预览，并等待用户明确选择
  脱敏保存、原文保存或取消。“原文”不等于保存完整对话。该约束当前属于 Markdown
  Skill 契约，尚无 Python 写入器强制。

## 公开知识分发与装配

- 仓库 `knowledge/`、wheel 的 `siyu_team/knowledge/data/` 和 SkillHub
  `modules/_knowledge/` 保持 manifest 与 approved JSONL 字节一致。
- `CorpusLoader` 只发现 approved 正式集，不回退 draft；对 manifest、原始字节哈希、
  数量、Schema、唯一 ID、批准/可见性/可分发、隐私和生命周期执行硬门。
- malformed JSON 默认 fail-closed；只有显式 `--lenient` 用于开发排查时才能跳过单行。
- `KnowledgeAssembler` 按结构化任务、路由、skill 绑定、业态与适用边界
  做确定性相关性排序，不再取文件前 40 条。
- `atoms_query.py` 默认查询同一严格 Corpus，结果携带 corpus 版本和哈希。

## 行业能力状态

- `catering`：`supported_with_industry_pack`，可引用真实存在的餐饮行业目录。
- `retail`：`generic_only`，可复用公开的餐饮零售 L1 方法层，但不声称有独立零售行业目录。
- `edu`：`generic_only`，只使用通用 L0，不声称有教培行业包。

路由不得为 `generic_only` 生成不存在的 `knowledge/02-industry/<industry>/` 路径。

## 自动事实检查

```bash
python tools/check_links.py
python tools/render_route_contract.py --check
python tools/sync_public_knowledge.py --check
python tools/build_skillhub_bundle.py --check
python tools/check_route_contracts.py
make check
```

检查覆盖仓库及已提交 SkillHub 包的 Markdown 本地链接、Python 路由目标、知识引用、
行业能力声明、公开知识原子绑定与三副本一致性。干净构建的
SkillHub 包和 wheel 安装态也有独立回归。

## 安全与产品边界

- `knowledge/03-majia-sop/` 只允许公开占位 README；真实 SOP 不进入仓库或分发包。
- 连接器是明确抛出未实现错误的骨架，不代表已接通外部系统。
- H1、H2、H3 均仍为 `Not Evaluated`；不得把工具 Dry Run 写成业务验证通过。
- 严格加载、相关性装配和安装态回归是工程证据，不是“知识飞轮”或“同行共建”已成立的证据。
- 当前版本不新增 Skill、角色或行业包；先完成 Runtime、分发、知识和质量语义对齐。
- run_id 隔离解决本地运行状态覆盖，不代表长期客户档案已经具备 tenant/workspace
  权限隔离或加密存储。
