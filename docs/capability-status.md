# 能力状态表

状态词只描述仓库当前能证明的事实，不从 README 宣称反推实现。

| 状态 | 定义 |
|---|---|
| 已实现 | 生产入口和自动测试使用同一实现 |
| 仅提示词实现 | Markdown 描述了行为，但没有对应可验证 Runtime 调用 |
| 仅 Python 实现 | Python API/CLI 和测试存在，但宿主安装态未证明会调用 |
| 骨架 | 接口和边界存在，主动返回未实现 |
| 未验证 | 工具或方案存在，但缺少所需真实样本/安装态证据 |

| 能力 | 状态 | 可核验证据 | 当前边界 |
|---|---|---|---|
| Task 与确定性路由 | 仅 Python 实现 | `task.py`、`routing.py`、84 条人工路由对照 | Prompt-only 解释契约，不等于执行 Python 解析器 |
| 插件入口路由 | 仅提示词实现 | 主入口与生成的 `route-contract.json` | 与 Python 路由同源；宿主执行语义仍不可由仓库强制 |
| 四官上下文白名单 | 仅 Python 实现 | `context.py`、Runtime 隔离测试 | 宿主是否执行投影未做安装态验证 |
| Python 执行计划 CLI | 仅 Python 实现 | ExecutionPlan v1、`siyu-plan --contract-info`、wheel 干净安装回归 | 安装态能找到公开知识；Markdown 宿主是否调用 Runtime 仍不可强制 |
| SkillHub 单入口包 | 已实现 | bundle `--check`、生成路由契约、公开知识副本与默认查询回归 | 包内不包含可执行 Python Runtime，固定 Prompt-only |
| 餐饮行业知识目录 | 已实现 | `knowledge/02-industry/catering/` | 仅餐饮具有行业包 |
| 零售/教培通用回答 | 已实现 | `generic_only` 路由回归 | 零售可复用跨业态 L1，但两者都不得伪造独立行业册 |
| 公开知识 Runtime 装配 | 已实现 | `CorpusLoader`、`KnowledgeAssembler`、Runtime 与安装态回归 | approved-only 且默认最多 12 条；只证明工程装配，不证明答案效果 |
| Pilot 知识装配 | 已实现 | Pilot 与 Runtime 共用 `KnowledgeAssembler`；mapping 对照回归 | mapping 只是期望夹具；Dry Run 不是 H1/H2/H3 结果 |
| Judge 质量评分 | 仅 Python 实现 | `siyu-eval judge` 与 Judge 单测 | 需宿主独立评分并回填，主编排未闭环 |
| 静态合规扫描 | 已实现 | `siyu-eval score` 与静态扫描测试 | 语境误杀仍需在稳定化版本修正 |
| 飞书/BI/Get 笔记/Nowledge 连接器 | 骨架 | `src/siyu_team/connectors/` | 未接外部 API，不可描述为可用集成 |
| H1 知识价值 | 未验证 | `docs/pilot/results/h1-knowledge-value.md` | `Not Evaluated` |
| H2 贡献动力 | 未验证 | `docs/pilot/results/h2-contribution-demand.md` | `Not Evaluated` |
| H3 审核吞吐 | 未验证 | `docs/pilot/results/h3-editorial-throughput.md` | `Not Evaluated` |

机器可检查的仓库契约见 [`architecture-current.md`](architecture-current.md)。
