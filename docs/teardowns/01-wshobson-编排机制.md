我已经把两套编排范式、状态机制、卡点机制、子专家派发与回收、预设团队、并行 launch 措辞全部抓到一手代码。证据充分，可以产出 teardown 了。

---

# wshobson/agents 多专家编排机制 · 深拆 teardown

> 全部引用来自本地 `wshobson-agents`，标 `文件:行号`。抓不到的地方我会明确标注。

## 0. 先给结论：它有"两套"完全不同的编排范式

读完真文件后最重要的发现是——这个仓库的"多专家编排"不是一套机制，而是**两套并存、互不依赖**的范式。私域专家团要照搬，必须先选边：

| | 范式 A：单 orchestrator + 文件状态机 | 范式 B：真·多 agent Team |
|---|---|---|
| 代表文件 | `full-stack-orchestration/commands/full-stack-feature.md`、`backend-development/commands/feature-development.md` | `agent-teams/` 整个 plugin |
| 谁在编排 | **一个** slash command（orchestrator 本体），自己串行走流程 | 一个 `team-lead` agent + 一群长驻 teammate |
| 派发子专家用什么 | `Task` 工具，`subagent_type` 指名 | `Agent` 工具 spawn 进 team + `TaskCreate/TaskUpdate` 派活 |
| 状态存哪 | `.full-stack-feature/state.json` + 每步落 `NN-xxx.md` 文件 | 团队运行时 `TaskList` + `~/.claude/teams/{name}/config.json` |
| 卡点 | `PHASE CHECKPOINT` + `AskUserQuestion` | 主要靠 `--plan-first` 在 spawn 前卡一次 |
| 依赖 | 无需实验开关，纯 prompt 编排 | 需 `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`（`team-spawn.md:12`） |
| 适配团长四角色 | **直接对位**（诊断→策略→执行→复盘 = 串行四 Step） | 适配并行专家组、辩论组 |

对"团长(诊断官→策略官→执行官→复盘官)"这种**有先后依赖、要人审、要可中断续跑**的链条，**范式 A 是可以原样照搬的母版**。范式 B 的价值在于"并行专家投票/竞争假设"那类子环节。下面分别拆。

---

## 1. 编排到底怎么实现的

### 1.1 范式 A：orchestrator 就是一个写死流程的 slash command

orchestrator 不是 agent，是 command（`commands/*.md`）。它开篇先用一段**铁律**把"AI 自由发挥"摁死，这是整套机制能跑稳的根：

`full-stack-orchestration/commands/full-stack-feature.md:8-18`
```
## CRITICAL BEHAVIORAL RULES
You MUST follow these rules exactly. Violating any of them is a failure.
1. Execute steps in order. Do NOT skip ahead, reorder, or merge steps.
2. Write output files. Each step MUST produce its output file in `.full-stack-feature/`
   before the next step begins. Read from prior step files -- do NOT rely on context window memory.
3. Stop at checkpoints. ... you MUST stop and wait for explicit user approval ... Use the AskUserQuestion tool.
4. Halt on failure. If any step fails ... STOP immediately.
5. Use only local agents. All `subagent_type` references use agents bundled with this plugin or `general-purpose`.
6. Never enter plan mode autonomously. ... This command IS the plan -- execute it.
```

第 2 条是整个机制的灵魂：**不靠上下文记忆传递状态，靠落盘文件传递**。每个 Step 读上一步的 `.md`，写自己的 `.md`。这让长流程不怕上下文窗口溢出、不怕中途崩。

**拆解任务**：orchestrator 不动态拆，任务是**写死的 9 个 Step / 3 个 Phase**（`:68`、`:227`、`:482`）。"拆解"发生在作者写这个 command 时，不是运行时。这正是它稳的原因——流程是确定性的。

**按 subagent_type 派发**：每个需要专家的 Step 用 `Task` 工具，prompt 里**手动把前序文件内容内联进去**（不是让子专家自己去读，是 orchestrator 注入）：

`full-stack-feature.md:133-156`（Step 2 派数据库专家）
```
Use the Task tool to launch a database architecture agent:
Task:
  subagent_type: "general-purpose"
  description: "Design database schema and data models for $FEATURE"
  prompt: |
    You are a database architect. Design the database schema ...
    ## Requirements
    [Insert full contents of .full-stack-feature/01-requirements.md]
    ## Deliverables
    1. Entity relationship design ...
Save the agent's output to `.full-stack-feature/02-database-design.md`.
```

注意 `subagent_type` 的命名规则是 `{plugin-name}-{agent-name}`，例如 `full-stack-feature.md:351` 的 `"full-stack-orchestration-test-automator"`、`feature-development.md:129` 的 `"backend-development-backend-architect"`。在 `backend-development/agents/` 里有同名 `.md` 真身。**没有专属专家的步骤就退化成 `"general-purpose"`**（如设计/文档步骤），这是铁律第 5 条"无跨 plugin 依赖"的落地。

### 1.2 Step 内如何并行 launch —— 关键措辞

并行的实现就是一句 prompt 指令 + 一个 response 里发多个 Task。原话：

`full-stack-feature.md:345`
```
Launch three agents in parallel using multiple Task tool calls in a single response:
```
`feature-development.md:250` 一字不差地复用了这句。

随后 `7a/7b/7c` 三个 Task 块（`:347-432`）分别派 test-automator / security-auditor / performance-engineer，**互不读对方输出、都只读已落盘的实现文件**——所以能真并行（无依赖）。这是它能并行的前提：并行的三个专家共享同一批输入文件，彼此不互为输入。

### 1.3 子专家结果如何回收整合

回收是 orchestrator 手动做的两步：**落盘 + 合并**。

`full-stack-feature.md:434-454`
```
After all three complete, consolidate results into `.full-stack-feature/07-testing.md`:
# Testing & Validation: $FEATURE
## Test Suite        [Summary from 7a -- files created, coverage areas]
## Security Findings [Summary from 7b -- findings by severity]
## Performance Findings [Summary from 7c -- findings by impact]
## Action Items      [List any critical/high findings that need to be addressed before delivery]
```
紧接着 `:456`：`If there are Critical or High severity findings ... address them now before proceeding.` —— 整合不只是拼接，还带**质量门**：高危必须当场修。

### 1.4 范式 B：真 Team 的派发与回收（对照）

范式 B 用的是另一组工具。`team-lead` agent 的 `tools` 行直接暴露了机制全貌：

`agent-teams/agents/team-lead.md:4`
```
tools: Read, Glob, Grep, Bash, Agent, TeamCreate, TeamDelete, TaskCreate, TaskList, TaskGet, TaskUpdate, SendMessage
```

派发链路（`team-feature.md:59-78`）：`TeamCreate` 建团 → `Agent` 工具 spawn 每个 implementer（带 `name`/`subagent_type`/`prompt`）→ `TaskCreate` 建任务 → `TaskUpdate` 设 `blockedBy` 依赖 + 设 `owner` 派活。

回收链路是**子专家主动回报**，不是 orchestrator 轮询抓取。`team-implementer.md:54-58`：
```
### Phase 5: Report
- Mark your task as completed via TaskUpdate
- Message the team lead with a summary of changes
- Note any integration concerns for other teammates
```
team-lead 侧靠 `Monitor TaskList for progress`（`team-feature.md:82`）感知完成。这是事件/消息驱动，比范式 A 的"派完就等返回值"更复杂，也更脆（需要实验开关）。

---

## 2. 状态与卡点

### 2.1 state.json —— 进度持久化的真身

范式 A 的 `state.json` 是整个续跑能力的核心。完整初始结构：

`full-stack-feature.md:44-58`
```json
{
  "feature": "$ARGUMENTS",
  "status": "in_progress",
  "stack": "auto-detect",
  "api_style": "rest",
  "complexity": "medium",
  "current_step": 1,
  "current_phase": 1,
  "completed_steps": [],
  "files_created": [],
  "started_at": "ISO_TIMESTAMP",
  "last_updated": "ISO_TIMESTAMP"
}
```

更新动作**散落在每一步末尾**，是手动指令而非自动 hook。典型一句：

`full-stack-feature.md:127`
```
Update `state.json`: set `current_step` to 2, add `"01-requirements.md"` to `files_created`, add step 1 to `completed_steps`.
```

注意 `current_step` 的值在到卡点时会写成字符串 `"checkpoint-1"`（`:203`）、`"checkpoint-2"`（`:458`），完成时写 `"complete"`（`:558`）——**用 current_step 这一个字段同时编码了"普通步/卡点/完结"三种态**，这是个很省的设计。

### 2.2 续跑 / 防重入 —— Pre-flight 的 session 检测

每次启动先查 state.json 决定续跑还是重开，这让流程**可中断、可恢复、幂等**：

`full-stack-feature.md:23-38`
```
### 1. Check for existing session
Check if `.full-stack-feature/state.json` exists:
- If it exists and `status` is `"in_progress"`: Read it, display the current step, and ask the user:
    Found an in-progress full-stack feature session:
    Feature: [name from state]
    Current step: [step from state]
    1. Resume from where we left off
    2. Start fresh (archives existing session)
- If it exists and `status` is `"complete"`: Ask whether to archive and start fresh.
```

### 2.3 PHASE CHECKPOINT —— 怎么卡点等人审

卡点是一段固定模板：先展示前序产物摘要，再用 `AskUserQuestion` 给 3 选项，**未选"批准"绝不进下一 Phase**。

`full-stack-feature.md:207-223`（CHECKPOINT 1 全文）
```
## PHASE CHECKPOINT 1 -- User Approval Required
You MUST stop here and present the architecture for review.
Display a summary of the database design and architecture from
.full-stack-feature/02-database-design.md and .../03-architecture.md ... and ask:

  Architecture and database design are complete. Please review:
  - .full-stack-feature/02-database-design.md
  - .full-stack-feature/03-architecture.md
  1. Approve -- proceed to implementation
  2. Request changes -- tell me what to adjust
  3. Pause -- save progress and stop here

Do NOT proceed to Phase 2 until the user selects option 1.
If they select option 2, revise and re-checkpoint. If option 3, update `state.json` and stop.
```

三选项的语义很关键：**Approve=前进 / Request changes=原地回炉重审（不前进）/ Pause=落盘退出（靠 state.json 下次续）**。卡点和 state.json 是一对——Pause 之所以能用，全靠 2.2 的续跑机制兜底。

> 诚实标注：范式 A 里**没有**自动化的"卡点超时""审批人鉴权"之类机制，卡点完全靠 prompt 纪律 + `AskUserQuestion` 的人工点击。`CHECKPOINT` 关键词在仓库里全部出现在这类 command prompt 中（grep 命中 14 个 command，全是同一模板的复制），没有任何代码层强制。

---

## 3. 一个 orchestrator 文件的完整骨架（逐段讲）

以 `full-stack-feature.md` 为母版，骨架是固定七段式：

```
① Frontmatter
   ---
   description: "<一句话说清这个 orchestrator 干嘛>"
   argument-hint: "<必填参数> [--可选 flag]"      # :2-3
   ---

② CRITICAL BEHAVIORAL RULES                        # :8-18
   "You MUST follow these rules exactly. Violating any is a failure."
   6 条铁律：按序执行 / 落盘不靠记忆 / 卡点停 / 失败停 / 只用本地 agent / 不自进 plan 模式
   —— 这一段是"防 AI 自由发挥"的护栏，是稳定性的根，必须有

③ Pre-flight Checks                                # :19-64
   1) 查 state.json → 决定续跑/重开（幂等入口）
   2) 初始化 state.json（写死字段结构）
   3) 解析 $ARGUMENTS 里的 flag 和主参数（抽出 $FEATURE 之类变量）

④ Phase 1 (Interactive) — 交互收集 + 落盘            # :68-127
   Step 1: 用 AskUserQuestion 一次问一个问题收需求
           → 写 01-requirements.md
           → Update state.json
   Step 2..3: 用 Task 派专家，prompt 内联前序 .md
           → 各自落盘 02..03.md → 更新 state

⑤ PHASE CHECKPOINT 1 — 人审卡点                     # :207-223
   展示摘要 → AskUserQuestion 三选项 → 不批准不前进

⑥ Phase 2 / CHECKPOINT 2 / Phase 3 ...              # :227-558
   重复"派专家→落盘→更新 state"的节奏；
   测试段用"多 Task 单 response"并行；
   每个 Phase 末一个 CHECKPOINT

⑦ Completion                                        # :562-593
   state.json: status="complete"
   打印 final summary（列全部产出文件 + Next Steps）
```

**逐段要点**：
- **Frontmatter 的 `argument-hint`** 既是给用户的提示，也是 orchestrator 自己 parse 的契约（`--stack/--complexity` 等）。
- **②铁律段是可移植性最高的资产**——它不含任何业务，纯粹是"如何让一个 LLM 老实走完多步流程"的通用咒语。
- **每个 Step 三件套**永远是：`Read 前序文件` → `Task 派专家(内联上下文)` → `Save 到 NN-xxx.md` + `Update state.json`。节奏极其规律，正是这种规律让它可被机械复制成 14 个变体 command。
- 子专家的 prompt 内部也有微结构：`You are a <role>` + `## <内联的上下文章节>` + `## Deliverables/Instructions`（编号清单）+ `Write ... Report what files were created`（`:139-153`）。

---

## 4. 「直接照搬到私域专家团」清单

目标团长链：**诊断官 → 策略官 → 执行官 → 复盘官**。这是一条**有序、有依赖、要人审**的链——对位**范式 A**，几乎可原样套。

### 4.1 可原样拿来的结构（标明出处 + 怎么改）

| 照搬什么 | 出处 | 改法 |
|---|---|---|
| **整个 orchestrator 骨架**（七段式，§3） | `full-stack-feature.md` 全文 | 把 9 Step 改成 4 Step；把目录 `.full-stack-feature/` 改成 `.siyu-team/`（或 `.private-domain/`） |
| **6 条 CRITICAL BEHAVIORAL RULES** | `:8-18` | **一字不改照搬**。这是纯通用护栏，和业务无关 |
| **state.json 结构 + 每步更新指令** | `:44-58`、`:127` | 字段改成业务态：`{"client":..., "status":"in_progress", "current_step":1, "completed_steps":[], "files_created":[], ...}`。`current_step` 同样用 `1→"checkpoint-1"→...→"complete"` 编码 |
| **Pre-flight session 检测（续跑/重开）** | `:23-38` | 路径改掉即可，逻辑全留——这是私域顾问场景最值钱的"接着上次聊"能力 |
| **PHASE CHECKPOINT 三选项模板** | `:207-223` | 把"架构/数据库"换成"诊断结论""策略方案"。**复盘官后无需 CHECKPOINT**，链路末尾直接 Completion |
| **子专家 Task 派发块**（内联上下文 + 编号 Deliverables） | `:133-156` | 见下方 4.2 改写 |
| **"多 Task 单 response"并行措辞** | `:345` | 用在"诊断官"内部需要多视角并行体检时（如：流量/转化/留存三个子诊断并行），其余串行 |
| **Completion 段**（列全产物 + Next Steps） | `:562-593` | 直接套 |
| **preset-teams 的"角色表 + Task Template"写法** | `team-composition-patterns/references/preset-teams.md:1-69` | 把它当"专家团花名册"的格式母版——每个专家一行：名字/维度/聚焦领域 + 一个统一 Task 模板 |

### 4.2 四角色映射成四个 Step（直接可写）

把 §3 的骨架实例化，四个 Step 串成链，依赖靠"读上一步的 .md"自然形成：

```
Step 1 诊断官  → subagent_type: "<plugin>-diagnostician"
  prompt 内联：客户原始信息（00-intake.md）
  Deliverables：现状盘点 / 核心问题 / 数据缺口
  → 写 01-diagnosis.md → update state

== PHASE CHECKPOINT 1：展示诊断结论，Approve/Request changes/Pause ==

Step 2 策略官  → subagent_type: "<plugin>-strategist"
  prompt 内联：01-diagnosis.md（注意：内联，不让它自己读）
  Deliverables：策略方向 / 私域 SOP / KPI 拆解
  → 写 02-strategy.md → update state

== PHASE CHECKPOINT 2：展示策略方案，人审 ==

Step 3 执行官  → subagent_type: "<plugin>-executor"
  prompt 内联：01 + 02
  Deliverables：落地动作清单 / 话术/素材 / 排期
  → 写 03-execution.md → update state
  （此处可用"多 Task 单 response"并行派：话术官 + 素材官 + 排期官）

Step 4 复盘官  → subagent_type: "<plugin>-reviewer"
  prompt 内联：01+02+03
  Deliverables：效果评估 / 偏差归因 / 下一轮迭代建议
  → 写 04-review.md → update state="complete"

== Completion：列出 01~04 全部产物 + Next Steps ==
```

每个 Step 用的就是 `:133-156` 那个 Task 块，**唯一要改的是 `subagent_type` 名、内联哪几个文件、Deliverables 清单**。子专家真身（4 个 `.md`）参照 `backend-development/agents/` 里的写法新建。

### 4.3 哪段**不要**照搬

- **范式 B（agent-teams 的 TeamCreate/Agent/SendMessage 那套）不要作为主链**。它需要 `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`（`team-spawn.md:12`），是实验功能，且消息驱动回收更脆。私域团长链是顺序依赖、要人审的，范式 A 更稳。
- 只在**单个 Step 内部要"多专家并行投票/竞争假设"**时，借鉴范式 B 的思想——但实现仍用范式 A 的"多 Task 单 response"即可，不必真起 Team。`team-debug.md:28-86` 的"竞争假设 ACH 方法"（生成 N 个假设→并行投查→仲裁排名）是个**可借的子模式**，若"诊断官"想做"多病因竞争诊断"可套这套仲裁模板（`team-debug.md:57-86`）。

### 4.4 一句话落地建议

照抄 `full-stack-feature.md` 为模板，全局替换：`.full-stack-feature/`→你的目录、9 Step→4 Step、`$FEATURE`→`$CLIENT`、各 `subagent_type` 与 Deliverables 换成私域四角色，**铁律段/state.json 机制/checkpoint 模板/续跑检测原样保留**。这样得到的就是一个工业级稳定的"团长 orchestrator"。

---

## 关键文件清单（绝对路径，供后续精读）

- orchestrator 母版（范式A，首选照搬）：`wshobson-agents/plugins/full-stack-orchestration/commands/full-stack-feature.md`
- orchestrator 同范式佐证：`wshobson-agents/plugins/backend-development/commands/feature-development.md`
- 团长 agent（范式B）：`wshobson-agents/plugins/agent-teams/agents/team-lead.md`
- 子专家回报端：`wshobson-agents/plugins/agent-teams/agents/team-implementer.md`
- 并行/spawn 命令：`.../plugins/agent-teams/commands/team-feature.md`、`team-spawn.md`、`team-debug.md`、`team-review.md`
- 专家团花名册格式母版：`.../plugins/agent-teams/skills/team-composition-patterns/references/preset-teams.md`
- 架构总览：`.../ARCHITECTURE.md`（model tiers 在 :89-98）、`.../AGENTS.md`

诚实标注：本仓库的 orchestration 全部是 **prompt 层编排**，state.json/CHECKPOINT/并行均为 command prompt 里的自然语言指令，没有任何 Python/代码层强制（grep `CHECKPOINT`/`state.json` 命中的均为 `commands/*.md`，唯二的代码命中 `tools/adapters/gemini.py`、`tools/tests/test_real_world.py` 与编排无关，是适配器/测试)。