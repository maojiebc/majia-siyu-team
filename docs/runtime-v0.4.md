# v0.4.0 Runtime 架构说明（含 v1.4.2 稳定化注记）

> 本文保留 v0.4.0 引入结构化 Runtime 时的设计背景。以下运行状态、追踪与
> Prompt 安全描述已按 v1.4.2 的当前实现校正；最新能力边界仍以
> [`architecture-current.md`](architecture-current.md) 和
> [`capability-status.md`](capability-status.md) 为准。

v0.4.0 的核心变化，是在现有 Skill 前增加一个可验证的计划层。自然语言不再直接决定要调用哪个能力，而是先转成结构化任务，再由确定性路由选择当前唯一一步。

## 请求链路

```text
用户请求
  ↓
Task Schema
  ↓
RouteDecision
  ├─ 高频执行：siyu-pyq / siyu-qunfa / siyu-huashu
  ├─ 动态事实：siyu-market-research → 证据快照 → 问诊或全盘评审
  ├─ 轻问诊：siyu-wenzhen
  ├─ 全盘升舱：siyu-onboard → 四官 → 团长 → 质量门
  └─ 档案管理：siyu-save / restore / report
```

Runtime 只生成执行计划，不直接调用模型。Skill 仍负责业务产出，这样已有插件和安装方式保持兼容。

## 核心对象

### Task

定义在 `src/siyu_team/task.py`，固定以下字段：

- `kind`：朋友圈、群发、话术、市场调研、问诊、全盘评审、存档等任务类型。
- `channel`：朋友圈、群聊、私聊、多渠道或未知。
- `goal`：转化、留存、获客、互动、信任、诊断或归档。
- `industry` / `stage`：行业与业务阶段。
- `risk` / `need_compliance_check`：输入风险与合规要求。
- `context`：可序列化的结构化业务字段。

非法枚举、非布尔合规字段、不可 JSON 序列化的上下文会在路由前失败。

### RouteDecision

定义在 `src/siyu_team/routing.py`，输出：

- 当前唯一 `skill`；
- 可解释的路由理由；
- 是否仍需补信息；
- 必填字段；
- 阶段重点与知识库引用。

整盘评审缺少行业或阶段时，只返回待补字段，不创建四官上下文。

厂商、产品、价格、功能、案例、政策、平台规则和公司存续等动态事实，确定性路由到 `siyu-market-research`。该路径不加载内部行业知识作为事实来源；候选对象必须来自本次公开网络检索，完成带日期和链接的证据快照后，才进入问诊或全盘评审。

### AgentContext

定义在 `src/siyu_team/context.py`。公关、产品、广告、合规四官各有独立字段白名单：

- 公关官只看品牌、口碑和客户反馈；
- 产品官只看权益、内容资产和客户需求；
- 广告官只看权益、预算、指标和漏斗；
- 合规官读取已脱敏的原始请求、授权和数据收集方式。

Prompt 负责角色表达，代码负责信息边界。未知角色直接拒绝。每位内置专家还配置
`required_any_of` 与上下文大小上限。`SiyuRuntime.plan()` 会先检查整组四官上下文；
任一官缺少最小业务字段时不返回整组 `agent_contexts`，而是给出
`context_incomplete` warning 和需要补齐的澄清字段。真正构造隔离 Prompt 时还会
再次调用 `assert_dispatchable()`，防止调用方绕过计划层后让专家凭空补全。

用户输入、外部知识或证据、官员输出都通过 `security.py` 编码为
`<untrusted_data>` 数据块。固定策略明确声明数据块内的“忽略上文”、读取密钥、
调用工具或执行命令均不可执行。Host 只把官员输出当待评审数据，并校验最低结构和
大小上限，不把其中的文本提升为系统指令。

## 可恢复与可追踪

`StateStore` 不再把所有会话写进单一状态文件。每个运行使用独立目录：

```text
.siyu-team/
  current
  runs/{run_id}/
    state.json
    task.json
    outputs/
    traces/
```

`.siyu-team/current` 是当前 run 的文本指针；已经绑定 run 的 `StateStore` 实例仍只写
自己的目录，因此切换 current 不会让两个会话互相覆盖。状态包含单调递增的
`revision`，更新在文件锁内重新读取并原子替换；调用方还可传
`expected_revision` 做 compare-and-swap，过期写入会明确报 revision 冲突。

旧 `.siyu-team/state.json` 仅作为迁移输入：首次读取时复制到新 run、补齐 schema、
run_id 与 revision，并保留旧文件原样，不删除、不继续回写。状态目录与文件权限收紧
为 0700/0600。

`TraceRecorder` 为每轮计划生成 `trace_id`，按 JSONL 记录事件。追踪级别为：

- `metadata`：默认，只保留 task_id、kind、risk、原文长度与 SHA256、route、知识定位和错误码等不可逆元数据；
- `redacted`：显式开启，保存经手机号、证件号、邮箱和常见凭据规则脱敏后的内容；
- `full`：显式开启，保存原始内容，调用方应自行承担本地明文风险。

Recorder 启动及写入后都会清理超过 TTL、文件数或总字节容量上限的旧记录。独立
`siyu-plan` 默认仍写 `.siyu-team/traces/`；与 `StateStore` 编排联用时，应把
`--trace-dir` 指向当前 run 的 `traces/`。两处均受 `.gitignore` 保护。

## CLI

```bash
PYTHONPATH=src python3 -m siyu_team.cli \
  "群发三轮没人打开，问题出在哪？" \
  --industry catering
```

输出是 JSON 执行计划。加 `--no-trace` 可只预览、不落追踪。

默认 metadata 无需参数；只有明确需要内容审计时才使用：

```bash
siyu-plan "群转化下降，先诊断" --trace-level redacted
siyu-plan "仅限本机授权审计" --trace-level full
```

## 客户档案保存

`siyu-save` 默认只从对话提取主诉摘要、已确认结论、否决方向、待验证假设和下一步，
不复制完整聊天、Trace、官员原始输出或外部文档全文。写盘前必须先展示敏感信息的
掩码预览，并等待用户明确选择“脱敏后保存 / 原文保存 / 取消”；未选择不得创建目录
或文件。“原文保存”只影响结构化草稿的脱敏方式，不会扩展成完整对话备份。

这套保存控制当前由 Markdown Skill 约束，尚不是 Python 文件写入器的代码级强制。

## 质量门

```bash
make check
```

当前会执行：

1. Runtime、路由、状态、追踪级别、Prompt 边界、质量门和连接器回归测试；
2. SKILL frontmatter、目录名和 8KB 上限检查；
3. VERSION、marketplace、README 徽章一致性检查；
4. 全库 footer、用户措辞和护城河占位检查。

GitHub Actions 额外执行 Ruff 与 mypy。

## 当前边界

以下能力尚未在 v0.4.0 完成：

- Runtime 尚不直接执行模型或管理模型重试；
- 判官层与蒙卡层走 B 路径已实装（宿主 Agent 按 rubric 逐维评分 + 脚本加权 / Wilson 统计，`siyu-eval judge`），但需宿主参与、非全自动；
- BI、飞书、Get 笔记和 Nowledge Mem 连接器仍是薄包装；
- run_id 解决同一工作目录的运行状态互相覆盖，不等于长期客户档案已经具备
  tenant/workspace 级权限隔离；
- `siyu-save` 的预览与明示选择仍依赖宿主遵守 Skill，未由 Python 写入器强制。

这意味着 v0.4.0 完成的是“输入与派发边界工程化”，不是完整 SaaS Runtime。
