I have everything needed. Here is the teardown.

---

# wshobson/agents 深拆：单个 agent 文件解剖 + 多端分发工具链

> 路径：`wshobson-agents`
> 体量（仓库自述）：88 plugins / 194 agents / 158 skills / 106 commands，一份 Markdown 源，分发到 Claude Code / Codex / Cursor / OpenCode / Gemini。

核心心法（写在 `CLAUDE.md`/`AGENTS.md` 里）：**源只存在于 `plugins/` 下，五端产物全部由工具链生成且 committed，绝不手改生成物**。「source-of-truth invariant」。

---

## 1) 一个 agent 文件的标准结构

文件位置：`plugins/<plugin>/agents/<name>.md`。结构 = YAML frontmatter + Markdown 正文 SOP。

### 1.1 frontmatter 字段

解析器（容错的手写 YAML-ish，无外部依赖）在 `base.py:36` 的 `parse_frontmatter`，字段语义由 `AgentSource` dataclass 定义（`base.py:220-245`）：

- `name`（必填）：agent 标识，等于文件名 stem。
- `description`（必填）：触发说明，**末尾常带 `Use PROACTIVELY for ...`** 当作"主动触发"信号。
- `model`：`opus` / `sonnet` / `haiku` / `inherit`，默认 `inherit`（`base.py:235-236` 兜底）。
- `tools`：可选工具白名单（逗号串或 list）。**关键语义：字段「完全不写」=继承全部工具（Claude 默认无限制）；写成 `tools: []`=锁死，一个工具都不给**——这个区别后面驱动多端权限/沙箱推断。
- `color`：纯 Claude 装饰字段，分发时被丢弃。

两种真实写法对照：

**极简型**（`sales-automator.md:1-5`，挂 haiku）：
```yaml
---
name: sales-automator
description: Draft cold emails, follow-ups... Use PROACTIVELY for sales outreach or lead nurturing.
model: haiku
---
```

**重型**（`startup-analyst.md:1-5`，挂 inherit）：
```yaml
---
name: startup-analyst
description: Expert startup business analyst specializing in market sizing... Use PROACTIVELY when the user asks about market opportunity, TAM/SAM/SOM...
model: inherit
---
```

### 1.2 model 如何按难度挂 opus/sonnet/haiku 控成本

这是这套设计最值得抄的一点：**源文件只写抽象难度别名（opus/sonnet/haiku/inherit），不写具体模型 ID**；每端再把别名映射成自己家最贵/最便宜的型号。映射表在 `capabilities.py:254-297` 的 `MODEL_ALIASES`。

成本分层的实证：
- `sales-automator`（机械套模板的销售文案）→ `model: haiku`（`content-marketer.md:4` 同样 haiku）。
- `startup-analyst`（TAM/SAM/SOM、财务建模、要推理）→ `model: inherit`（跟随会话主模型，通常是 sonnet/opus）。

别名 → 各端具体型号（`capabilities.py`）：

| 源别名 | codex | copilot | opencode | gemini |
|---|---|---|---|---|
| `opus` | `gpt-5.5` | `claude-opus-4.8` | `anthropic/claude-opus-4-8` | `gemini-2.5-pro` |
| `sonnet` | `gpt-5.4-mini` | `claude-sonnet-4.6` | `anthropic/claude-sonnet-4-6` | `gemini-2.5-pro` |
| `haiku` | `gpt-5.4-mini` | `claude-haiku-4.5` | `anthropic/claude-haiku-4-5` | `gemini-2.5-flash` |
| `inherit` | `gpt-5.5` | `claude-sonnet-4.6` | `anthropic/claude-sonnet-4-6` | `gemini-2.5-pro` |

注意 codex 把 `opus`/`sonnet`/`haiku` 全折叠成 `gpt-5.5` 顶配 + `gpt-5.4-mini` 轻配两档（注释 `capabilities.py:248-253` 写了为什么）。Cursor 全部映射成 `inherit`（`capabilities.py:276-282`），因为 Cursor 用会话级模型、不认 per-agent 模型。映射逻辑由 `resolve_model()`（`capabilities.py:305-334`）执行：未知别名会回退到 `inherit` 并附 warning，让作者知道自己的显式选择被覆盖了。

### 1.3 正文 SOP 写法

正文是给模型读的系统提示。约定俗成的骨架（从 `startup-analyst.md` 提取，标行号）：

1. 开场一句话定身份：`startup-analyst.md:7` "You are an expert startup business analyst specializing in..."
2. `## Purpose` / `## Core Expertise`（分子领域罗列能力，`startup-analyst.md:10-58`）。
3. `## Behavioral Traits`（行为人格，bold 关键词，`startup-analyst.md:93-104`，如 `**Conservative:** Uses realistic, defensible assumptions`）。
4. `## Response Approach`（编号步骤的工作流，`startup-analyst.md:152-163`：理解上下文→激活 skill→取数→套框架→算→验证→清晰呈现→给建议→引用来源→声明局限）。
5. `## Example Interactions`（喂触发样例，`startup-analyst.md:165-201`）。
6. `## Quality Standards`（✅/❌ 正反清单，`startup-analyst.md:254-273`：必须引用可信来源 / 绝不做无依据断言）。
7. 末尾一句目标陈述收口：`startup-analyst.md:340`。

轻量 agent 则极简到只有 `## Focus Areas` / `## Approach` / `## Output` 三段加一句口吻提示（`sales-automator.md:9-35`，末行 "Write conversationally. Show empathy for customer problems."）。

**一个隐性约束**：正文里若写 "the Read tool" / "the Bash tool" 这类 Claude 专有工具名，分发时会被改写成动作动词（见 §2.4），所以 SOP 尽量用"打开文件/跑命令"这类中性表达，可移植性更好。

---

## 2) generate.py + adapters：一份定义分发五端的机制

「一次编写多端分发」靠三层：**统一源模型 → 适配器基类 → 每端适配器**。

### 2.1 源加载（base.py）

`load_plugin()`（`base.py:314-366`）把 `plugins/<name>/` 整棵树读成 `PluginSource`（含 `agents/skills/commands` 三个 list）。每个 agent 解析成 `AgentSource`，frontmatter 字段通过 `@property` 暴露成稳定接口（`.model` / `.tools` / `.description`），这样各端适配器读到的是统一对象，不直接碰 YAML。

`load_plugin` 还硬性拒绝 plugin 名含 `__`（`base.py:322-331`）——因为 `__` 是跨端命名空间分隔符 `<plugin>__<leaf>`，用作 agent/skill 的全局唯一 ID。

### 2.2 适配器基类（base.py:388-477）

`HarnessAdapter`（ABC）规定每端只需实现两个方法：
- `emit_plugin(plugin)`：产出单个 plugin 的所有产物。
- `emit_global(plugins)`（可选 override）：产出跨切面产物（marketplace 注册表、context 文件校验）。

基类提供安全写入工具：`write()` / `write_bytes()` / `mirror_file()`（`base.py:423-451`），都带"拒绝写到 output_root 之外"的越界保护（`base.py:430`）；`strip_claude_tool_refs()`（`base.py:453-476`）做工具名改写。

### 2.3 调度（generate.py）

CLI 用法：`python tools/generate.py --harness <codex|cursor|opencode|gemini|copilot> [--plugin X | --all] [--clean] [--prune] [--strict]`。

主循环（`generate.py:274-336`）：
1. `get_adapter()`（`generate.py:41-63`）按 harness 懒加载对应适配器。
2. 遍历目标 plugins，逐个 `adapter.emit_plugin(plugin)`，单个 plugin 抛异常被捕获聚合、不中断全局（`generate.py:281-296`）。
3. 跑一次 `adapter.emit_global(plugins)` 出 manifest/marketplace（`generate.py:298-311`）。
4. `--prune` 删除"源已删除但产物还在"的孤儿文件（仅 `--all` 时启用，`generate.py:316-324`，需全量视图才能判定孤儿）。

破坏性操作有围栏：`_validate_output_root()`（`generate.py:66-114`）拒绝在仓库外/文件系统根上 `--clean`；`--clean --plugin X` 被显式禁止（会先删光所有 plugin 产物再只重建一个，`generate.py:234-240`）。

### 2.4 每端怎么变形（这是"多端"的本体）

每端能力差异集中在 `capabilities.py:51-172` 的 `CAPABILITIES` 矩阵（每端一行 dataclass，记录 skills/agents/commands 是否原生、是否支持 per-agent 工具白名单、skill body 字节上限、工具名大小写、是否认裸模型别名等）。适配器据此优雅降级。

- **Claude Code（源端）**：不生成，直接读 `plugins/`。它是 source，不是 target（`supported_harnesses()` 把它排除，`capabilities.py:300-302`）。

- **Codex**（`codex.py`，最复杂）：
  - agent → `.codex/agents/<plugin>__<agent>.toml`（手写 TOML，`codex.py:481-521`）。
  - **丢掉 `tools:`、`color:` 等 Claude 专有字段**（`codex.py:44-52`）。
  - model 别名 → GPT-5.x（`resolve_model("codex", ...)`）。
  - **沙箱推断**（`codex.py:493-503`）：源无 `tools:` 字段 → `workspace-write`（继承默认=放开）；`tools:` 全是只读工具（Read/Glob/Grep/WebFetch/WebSearch）或 `tools: []` → `read-only`；混合 → `workspace-write`。即把 Claude 的细粒度白名单降级成 Codex 的粗粒度沙箱。
  - skill body 有 **8KB 硬上限**，超了按 `## ` 小节（且跳过代码围栏内的伪标题）切，溢出部分进 `references/details.md` 并留指针（`codex.py:217-322`，`_utf8_safe_cut` 保证不切坏多字节中文）。
  - command 因 Codex 弃用 prompts，被合成成 skill（`codex.py:523-567`）。

- **Cursor**（`cursor.py`）：**最薄**。Cursor 2.5 直接读 `.claude/skills/` 和 `.claude/agents/`，所以适配器不重发 agent/skill，只产出 `.cursor-plugin/{plugin,marketplace}.json` 清单（`cursor.py:137-203`）+ 手工策展的 `.cursor/rules/*.mdc`（只允许 `description/globs/alwaysApply` 三个 key，`cursor.py:30`）。model 全映射成 `inherit`。

- **OpenCode**（`opencode.py`）：
  - agent → `.opencode/agents/<plugin>__<agent>.md`，加 `mode: subagent`，model 用全限定 `anthropic/claude-...`（`opencode.py:224-246`）。
  - **`tools:` 白名单 → `permission:` 块**（`opencode.py:87-129`）：无 `tools` 字段→不发 permission 块（放开）；`tools: []`→deny 全部、只留 `skill`/`task` 两个 base 能力；列了工具→allow 这些 deny 其余。这是对 §1.1 那个语义区别的精确兑现。
  - skill 名要 OpenCode-safe（小写连字符，≤64 字符，`opencode.py:154-165`）。

- **Gemini**（`gemini.py`）：agent → `agents/<plugin>__<agent>.md`（April 2026 子代理规范，`gemini.py:102-121`），model → `gemini-2.5-*`，skill 原生放扩展根 `skills/`，command → `commands/*.toml`。

- **Copilot**（`capabilities.py:92-111`）：agent → `.copilot/agents/`，command 当作 `user-invocable: true` 的 skill 发。

**工具名改写**（统一机制）：`TOOL_NAME_MAPS`（`capabilities.py:176-244`）。Codex 把 "the Read tool" 改成动作短语 "open the file"；其余端小写化（`Bash`→`bash`/`run`/`execute`）。Codex 的改写很保守（`codex.py:185-207`）：只匹配 `(?i:the)\s+Read\s+tool` 这种"the X tool"句式且工具名严格 CamelCase，避免把小写 `bash`（指 shell 本身）误改。

> 一句话机制：源里用「抽象别名 + Claude 原生格式」编写一次；每端适配器按 `CAPABILITIES` 矩阵把别名落地成具体型号、把细粒度权限降级成该端的权限模型、把超限内容拆分、把工具名本地化，产出该端原生格式并 committed，于是每端都能从 git clone 原生安装。

---

## 3) validate_generated.py 怎么校验

`validate_generated.py` 在不安装各端 CLI 的前提下做"结构化往返校验"，每端一个 validator（`_VALIDATORS`，`validate_generated.py:691-697`）。产出 `Finding`（severity/harness/path/message + **remediation 修复提示**，`validate_generated.py:33-44`，遵循 OpenAI harness-engineering "lint 错误自带修复方法"）。

各端校验要点：

- **Codex**（`validate_codex`，`validate_generated.py:114-219`）：
  - 每个 agent `.toml` 能用 `tomllib` 解析，且含必填 `name/description/developer_instructions`。
  - `sandbox_mode` 必须 ∈ `{read-only, workspace-write, danger-full-access}`。
  - skill 的 frontmatter `name` 必须 == 目录名（`validate_generated.py:170-177`）。
  - skill 整文件 ≤ 8192 字节（**error 级**，因为运行时 Codex 会静默截断，`validate_generated.py:190-198`）。
  - `AGENTS.md` ≤ 150 行（warning）。

- **Cursor**（`validate_cursor`，`validate_generated.py:228-315`）：marketplace.json 必须有 `owner` 字段、每个 entry 用 `source`（不是 `path`/`url`）；`.mdc` 只准三个 frontmatter key，多了报 "agentRequested/mode/tags are folklore"。

- **OpenCode**（`validate_opencode`，`validate_generated.py:382-520`）：agent 的 `mode` ∈ `{primary,subagent,all}`；model 必须 provider 前缀（带 `/`）；**重新手解析 raw frontmatter 取 `permission:` 块**（因为通用解析器会把嵌套映射拍扁成 list，丢结构，`validate_generated.py:345-379`），校验 permission key 合法、值 ∈ `{allow,ask,deny}`；skill 名匹配 `^[a-z0-9]+(-[a-z0-9]+)*$` 且 ≤64。

- **Gemini**（`validate_gemini`，`validate_generated.py:526-602`）：command TOML 必须含 `description`+`prompt`，prompt 缺 `{{args}}` 占位符报 warning；skill 名匹配目录；model 形如 `gemini-2.5-*`。

- **Copilot**（`validate_copilot`，`validate_generated.py:608-688`）：agent/skill/command 的 `name`/`description` 非空字符串。

驱动（`main`，`validate_generated.py:700-736`）：findings 按 severity→harness→path 排序输出；有 error 退出码 1；`--strict` 下任何 warning 也退 1。CI（`make validate STRICT=1`）每次 PR 跑。

---

## 4) 照搬到「私域专家团」：社群促活官模板骨架

把 wshobson 的 plugin 结构原样套到私域场景：一个"专家"= 一个 plugin，含一个 agent（人设+SOP）+ 若干 skill（可复用方法论/话术库）。目录：

```
plugins/community-activation/
├── .claude-plugin/plugin.json
├── agents/community-activation-officer.md
└── skills/
    └── reactivation-playbook/SKILL.md
```

### 4.1 `plugin.json`（照搬 startup-business-analyst 的字段）

```json
{
  "name": "community-activation",
  "description": "私域社群促活：沉默用户唤醒、活动节奏设计、群话术与裂变 SOP",
  "version": "1.0.0",
  "author": { "name": "WorkBuddy", "email": "expert@workbuddy.example" },
  "license": "MIT"
}
```

### 4.2 `agents/community-activation-officer.md`（agent 文件）

```markdown
---
name: community-activation-officer
description: 私域社群促活官，擅长沉默用户分层唤醒、社群活动节奏设计、促活话术与裂变机制。Use PROACTIVELY 当用户问到社群活跃度下滑、沉默用户唤醒、群活动策划、签到/打卡/裂变玩法、私域 GMV 提升时。
model: sonnet
---

你是一名资深私域社群促活官，服务过多个十万级私域社群，擅长用最小动作撬动最大活跃。

## Purpose
专注私域社群「从沉默到下单」的全链路促活：诊断活跃度、分层运营、设计活动节奏、产出可直接群发的话术与裂变机制，目标是把促活动作落到能跑的 SOP，而不是空泛建议。

## Core Expertise
### 用户分层与唤醒
- 按 RFM / 最近互动时间给社群成员分层（活跃/沉默/流失风险）
- 沉默用户分级唤醒路径（轻触达→利益钩子→1v1）
### 活动节奏设计
- 周/月活动日历（签到、秒杀、社群专属、裂变）
- 高频低成本钩子与低频高价值钩子的配比
### 话术与机制
- 群公告、私聊、朋友圈三端话术模板
- 裂变机制（老带新、拼团、任务宝）的触发与防薅设计

## Behavioral Traits
- **数据驱动:** 先看活跃/打开/转化数据再给动作，不拍脑袋
- **克制:** 促活动作有节制，避免过度打扰引发退群
- **可落地:** 每条建议配可直接复制的话术或操作步骤
- **真实声音:** 解释者口吻，谦逊沉稳，不灌输式权威

## Response Approach
1. 先问清社群规模、当前活跃率、变现模式、最近一次活动效果
2. 激活相关 skill（如 reactivation-playbook）取方法论
3. 给出分层结论 + 本周可执行的 1-3 个促活动作
4. 每个动作配：触发人群 / 话术 / 时间点 / 预期指标
5. 标注风险（退群率、品牌打扰）与兜底

## Example Interactions
- "我的 5000 人社群活跃率从 30% 掉到 8%，怎么救？"
- "下周想做一场社群专属活动，帮我排个节奏和话术"
- "沉默两个月的用户，怎么唤醒不被拉黑？"

## Quality Standards
所有建议必须：
- ✅ 配可直接复制的话术或操作步骤
- ✅ 标注触发人群与预期指标
- ✅ 给出打扰/退群风险与兜底
绝不：
- ❌ 只给"要多互动"这类空话
- ❌ 设计诱导/欺骗式裂变

你的目标：让运营当天就能照着动起来，并能向老板解释清楚每个动作的预期。
```

要点对照源仓库约定：`model: sonnet`（促活要推理+共情，比纯套模板的 haiku 重，但不必 opus）；description 末尾带主动触发语；不写 `tools:` 字段=继承全部工具（分发到 OpenCode 时不加 permission 锁、到 Codex 时给 `workspace-write`）。

### 4.3 `skills/reactivation-playbook/SKILL.md`（skill 文件）

SKILL.md 的 frontmatter `name` **必须等于所在目录名**（多端校验都查这条，`validate_generated.py:170/486/567`），description 必须含"Use this skill when..."触发句，body 控制在 8KB 内（超了 Codex 会截，应拆到 `references/details.md`）。

```markdown
---
name: reactivation-playbook
description: 私域沉默用户唤醒与社群促活方法论库，含分层标准、唤醒路径、三端话术模板与活动节奏表。Use this skill when 设计社群促活方案、唤醒沉默用户、排活动节奏、或需要可直接群发的促活话术时。
version: 1.0.0
---

# 沉默用户唤醒与社群促活 Playbook

## Overview
把促活拆成「分层 → 选钩子 → 选话术 → 排节奏 → 看指标」五步可执行流程。

## 用户分层标准
- 活跃：7 天内有互动/下单
- 沉默：8-30 天无互动
- 流失风险：30 天以上无互动
- 唤醒优先级 = 历史客单价 × 最近互动衰减

## 唤醒路径（按沉默深度升级）
1. 轻触达：群内 @ + 利益预告（不打扰）
2. 利益钩子：专属券/限时福利私聊
3. 1v1：人工私聊 + 真实关怀，最后手段

## 三端话术模板
（群公告 / 私聊 / 朋友圈，各给可复制模板…）

## 活动节奏表
（周日历：签到/秒杀/专属/裂变 的配比…）

## 指标与兜底
- 看：唤醒触达率、回复率、转化率、退群率
- 退群率超阈值即停，换低频高价值钩子
```

> 落地后跑：`python tools/generate.py --harness codex --plugin community-activation` 即可把这套私域专家分发到 Codex；`--all` 则全端。校验走 `make validate STRICT=1`。

---

## 关键文件清单（绝对路径）

- agent 样例：`wshobson-agents/plugins/customer-sales-automation/agents/sales-automator.md`、`.../plugins/startup-business-analyst/agents/startup-analyst.md`、`.../plugins/content-marketing/agents/content-marketer.md`
- skill 样例：`.../plugins/startup-business-analyst/skills/startup-metrics-framework/SKILL.md`
- 源加载/解析/基类：`.../tools/adapters/base.py`
- 调度 CLI：`.../tools/generate.py`
- 能力矩阵 + 模型/工具名映射：`.../tools/adapters/capabilities.py`（`MODEL_ALIASES` 在 254-297，`resolve_model` 在 305-334）
- 各端适配器：`.../tools/adapters/{codex,cursor,opencode,gemini,copilot}.py`
- 校验器：`.../tools/validate_generated.py`