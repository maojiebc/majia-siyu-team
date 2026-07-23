> [!IMPORTANT]
> 本文是项目创建期的历史蓝图，保留用于追溯设计来源，其中部分“计划实现”描述已经被 v0.4.0 取代。当前实现以 [`runtime-v0.4.md`](./runtime-v0.4.md)、`src/siyu_team/` 和首页架构图为准。

下面是历史蓝图文本。

---

# 私域专家团 · 骨架蓝图

> 融合两个标杆：**wshobson 的 `plugins/` 化**(一专家=一 plugin=agent.md+skills)+ **qiaomu 的 `src/` 化**(orchestrator/host/roster/eval/routing 都是薄代码+可配置文本)。
> 红线原则(忠实 teardown)：编排走 **wshobson 范式 A**(单 orchestrator + 文件状态机,不碰需要实验开关的 agent-teams 范式 B);讨论收口走 **qiaomu HeavySkill**(四官=四 perspective 独立采样、团长=host 不投票只评质量);质量门照搬 **plugin-eval**(静态层→判官层→蒙卡层→反模式乘法惩罚→阈值 exit 1)。
> 标注约定:私域内容凡涉及马甲护城河的,只给**结构占位+示例**,统一标 `【待马甲填真实SOP】`。

---

## 1) repo 目录结构(完整目录树)

仓库名建议 `siyu-expert-team`(siyu=私域)。骨架图见上方。两套标杆怎么融合:**`plugins/` 装"角色人设+方法论"(wshobson),`src/` 装"编排+收口+质量门+连接器"(qiaomu),两者通过 `roster.py` 角色表解耦**。

```
siyu-expert-team/
├── README.md                          # 三句话方法论引擎 + 一图说明团长/四官/质检官拓扑
├── CLAUDE.md                          # source-of-truth invariant：源只在 plugins/ 与 src/，分发产物不手改
├── pyproject.toml                     # 仿 qiaomu：把 src/siyu_team 装成包，暴露 CLI 入口
├── Makefile                           # make eval / make validate STRICT=1 / make report（仿 wshobson）
│
├── plugins/                           # == wshobson 化：一个"官"= 一个 plugin ==
│   ├── _orchestrator/                 # 团长本体（编排器是 command，不是 agent）
│   │   ├── .claude-plugin/plugin.json
│   │   └── commands/
│   │       └── siyu-onboard.md        # 【核心骨架文件 3a】团长 orchestrator：调研→路由→派四官→主持收口
│   │
│   ├── private-pr-officer/            # 公关官 ← 「私域即公关」
│   │   ├── .claude-plugin/plugin.json
│   │   ├── agents/
│   │   │   └── private-pr-officer.md  # 公关官人设+SOP（frontmatter: model/description/触发语）
│   │   └── skills/
│   │       ├── trust-asset-playbook/SKILL.md      # 信任资产打法（IP/口碑/危机话术）【待马甲填】
│   │       └── crisis-response-sop/SKILL.md       # 私域舆情/差评应对 SOP【待马甲填】
│   │
│   ├── content-product-officer/       # 产品官 ← 「内容即产品」
│   │   ├── .claude-plugin/plugin.json
│   │   ├── agents/content-product-officer.md
│   │   └── skills/
│   │       ├── content-as-product/SKILL.md        # 把内容当产品做（选题/钩子/承接）【待马甲填】
│   │       └── reactivation-playbook/SKILL.md     # 社群促活官 skill【核心骨架文件 3b 落点】
│   │
│   ├── ops-ad-officer/                # 广告官 ← 「运营即广告」
│   │   ├── .claude-plugin/plugin.json
│   │   ├── agents/ops-ad-officer.md
│   │   └── skills/
│   │       ├── ops-as-ad-funnel/SKILL.md          # 每个运营动作即一次广告投放（漏斗/埋点）【待马甲填】
│   │       └── conversion-caliber/SKILL.md        # 转化口径定义库（UV→加微→首单→复购）【待马甲填】
│   │
│   └── compliance-critic/             # 质检合规官（Critic，企微合规+落地性）
│       ├── .claude-plugin/plugin.json
│       ├── agents/compliance-critic.md
│       └── skills/
│           └── wechat-compliance-redlines/SKILL.md # 企微封号红线/广告法违禁词库【部分待马甲填】
│
├── src/siyu_team/                     # == qiaomu 化：薄编排代码，全部可配置文本驱动 ==
│   ├── __init__.py
│   ├── orchestrator.py                # 团长串行四 Step 的执行壳（读 state→派官→落盘→checkpoint）
│   ├── roster.py                      # 【核心骨架文件 3f】角色=视角配置表（换 prompt 不换代码）
│   ├── host.py                        # 【核心骨架文件 3e】主持人 prompt 工厂 + 报告渲染（仿 heavy.py）
│   ├── state.py                       # 【核心骨架文件 3c】state.json 读写/续跑/防重入（仿 full-stack）
│   ├── routing.py                     # 行业×阶段 规则路由（仿 qiaomu routing.py，私域类目）
│   ├── perspectives.py                # 四官独立采样 prompt 工厂（仿 heavy.build_perspective_prompt）
│   ├── eval/                          # == plugin-eval 化质量门 ==
│   │   ├── __init__.py
│   │   ├── static.py                  # 静态层：合规违禁词/口径缺失 正则反模式（免费、确定性）
│   │   ├── judge.py                   # 判官层：锚定 rubric 调 LLM 打分
│   │   ├── monte_carlo.py             # 蒙卡层：同一诉求生成 N 份测一致性（Wilson/CP 置信区间）
│   │   ├── engine.py                  # 加权合成 + 反模式乘法惩罚 + 徽章
│   │   ├── rubrics.py                 # 【核心骨架文件 3d】私域方案 rubric 锚点（五档）
│   │   └── cli.py                     # `siyu-eval score ... --threshold 80` exit 1 硬门
│   └── connectors/                    # == 马甲工具链接入层（薄包装，各一个文件）==
│       ├── bi_platform.py                # 某 BI 平台：bi-cli/bi-ds/bi-vis 调用（取数验证口径）
│       ├── lark.py                    # 飞书：方案落 docx / 进度同步
│       ├── getnote.py                 # Get笔记：行业素材抓取
│       └── nowledge_mem.py            # Nowledge Mem：马甲 SOP 语义检索（RAG 取数）
│
├── knowledge/                         # == 知识库三层（RAG 语料，团员检索用）==
│   ├── 01-wechat-official/            # 第一层：企业微信官方文档（功能+合规底座，可公开）
│   │   ├── features/                  # 企微功能清单（群/客户/朋友圈/侧边栏…）
│   │   └── compliance/redlines.md     # 封号规则原文摘录（合规官静态层违禁词来源）
│   ├── 02-industry/                   # 第二层：行业册（先做餐饮）
│   │   └── catering/                  # 餐饮册：客单/到店/复购周期 行业基线【部分待马甲填】
│   │       ├── stages.md              # 行业×阶段定义（冷启/扩张/成熟）
│   │       └── benchmarks.md          # 餐饮私域指标基线【待马甲填真实数据】
│   └── 03-majia-sop/                  # 第三层：马甲真实 SOP（护城河，私有，git-ignore 或私仓）
│       └── README.md                  # 仅占位说明，真 SOP 不入公开库【待马甲填】
│
├── examples/
│   └── roster.example.json            # 四官+质检官角色表样例（仿 registry.example.json）
│
├── tools/                             # == wshobson 多端分发工具链（4 档才上）==
│   ├── generate.py                    # 一份源分发到 codex/cursor/opencode/gemini（仿 wshobson）
│   └── validate_generated.py          # 结构化往返校验 + 自带 remediation
│
└── .siyu-team/                        # == 运行时状态目录（git-ignore，仿 .full-stack-feature/）==
    ├── state.json                     # 当前客户诊断进度（续跑核心）
    ├── 00-intake.md                   # 客户原始信息
    ├── 01-diagnosis.md ~ 04-*.md      # 四官/各 Step 落盘产物
    └── reports/                       # 主持收口产物 deliberation.md / *.html
```

---

## 2) 每个借鉴模式落到哪个文件(逐条映射)

| teardown 里"可照搬"的点 | 出处(标杆文件:行号) | 落到本 repo 的哪个文件 |
|---|---|---|
| **编排机制·范式 A 七段式骨架** | `full-stack-feature.md` 全文 | `plugins/_orchestrator/commands/siyu-onboard.md`(prompt 编排) + `src/siyu_team/orchestrator.py`(执行壳) |
| **6 条 CRITICAL BEHAVIORAL RULES**(防自由发挥护栏) | `full-stack-feature.md:8-18` | `siyu-onboard.md` 顶部,**一字不改照搬** |
| **state.json 结构 + 每步更新指令** | `full-stack-feature.md:44-58,127` | `src/siyu_team/state.py` + 运行时 `.siyu-team/state.json` |
| **Pre-flight session 检测(续跑/重开/幂等)** | `full-stack-feature.md:23-38` | `state.py` 的 `check_session()` + `siyu-onboard.md` 开头 |
| **PHASE CHECKPOINT 三选项模板**(Approve/Request changes/Pause) | `full-stack-feature.md:207-223` | `siyu-onboard.md` 每个 Step 后(诊断后、策略后) |
| **子专家 Task 派发块**(内联上下文+编号 Deliverables) | `full-stack-feature.md:133-156` | `siyu-onboard.md` 派四官的四个 Task 块 |
| **"多 Task 单 response"并行措辞** | `full-stack-feature.md:345` | `siyu-onboard.md` 派四官那一步(四官并行) |
| **Completion 段**(列全产物+Next Steps) | `full-stack-feature.md:562-593` | `siyu-onboard.md` 结尾 |
| **主持人收口·不投票只评质量** | `heavy.py:204` | `src/siyu_team/host.py` 的 `build_host_prompt()` |
| **主持人五段输出结构** | `heavy.py:212-244` | `host.py` 的 `<output_rules>` |
| **角色独立采样·互不可见 prompt** | `heavy.py:120-168` | `src/siyu_team/perspectives.py` |
| **host_mode=codex(让主控当团长)/model** | `server.py:672-691` | `orchestrator.py` 的收口分叉 |
| **多轮二审(H1 当新输入)** | `server.py:548-557` | `host.py` + `orchestrator.py`(rounds≤2) |
| **去位置偏差洗牌** | `server.py:662` | `host.py` 的 `stable_shuffle_traces()` |
| **角色=视角配置表(换 prompt 不换代码)** | `schemas.py:144-152` + `registry.example.json` | `src/siyu_team/roster.py` + `examples/roster.example.json` |
| **规则路由(行业×阶段)** | `routing.py:9-100` | `src/siyu_team/routing.py`(需新增私域 task 类目) |
| **eval 质量门·三层流水线** | `evaluation-methodology/SKILL.md:16-86` | `src/siyu_team/eval/{static,judge,monte_carlo}.py` |
| **锚定 rubric 五档** | `rubrics.md` 全文 | `src/siyu_team/eval/rubrics.py` |
| **反模式乘法惩罚 `max(0.5,1-0.05n)`** | `static.py:30-32` | `eval/static.py` 同款公式 |
| **CI exit 1 硬门 + 徽章分级** | `cli.py:91-96` + `models.py:116-134` | `eval/cli.py` + `eval/engine.py` |
| **蒙卡可靠性 + 置信区间** | `monte_carlo.py:147-153` + `stats.py` | `eval/monte_carlo.py` |
| **agent 文件解剖模板**(frontmatter+SOP 七段) | `startup-analyst.md` / `sales-automator.md` | `plugins/*/agents/*-officer.md` 四官人设 |
| **model 按难度挂 opus/sonnet/haiku** | `capabilities.py:254-297` | 四官 agent.md frontmatter 的 `model:` 字段 |
| **SKILL.md frontmatter name==目录名 + 触发句 + ≤8KB** | `validate_generated.py:170/486` | `plugins/*/skills/*/SKILL.md` |
| **多端分发(一份源→五端)** | `generate.py` + `adapters/` | `tools/generate.py`(4 档才上) |
| **往返校验 + remediation** | `validate_generated.py:33-44` | `tools/validate_generated.py`(4 档) |
| **密钥指针解耦(keychain/env)** | `registry.py:107-120` | `src/siyu_team/connectors/*`(某 BI 平台/飞书 token 走 keychain ref) |

> **明确不照搬**:wshobson 范式 B(`agent-teams` 的 TeamCreate/Agent/SendMessage)——需 `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`,消息驱动更脆。私域团长链是顺序依赖+要人审,范式 A 更稳。`code_template_quality`/`robustness` 两维在标杆里就是文档与实现的缺口(teardown 已诚实标注),本 repo eval 不引入这两维,避免照抄一个空壳。

---

## 3) 关键骨架文件的初稿

### (a) 团长 orchestrator —— `plugins/_orchestrator/commands/siyu-onboard.md`

> 母版 = `full-stack-feature.md` 七段式。四 Step = 调研诊断官 → 按行业/阶段路由 → 并行派四官 → 主持收口。铁律段/checkpoint/state 续跑**原样保留**。

```markdown
---
description: "私域专家团团长：调研诊断客户私域现状 → 按行业/阶段路由 → 并行派公关/产品/广告/合规四官 → 团长主持收口出可落地 playbook"
argument-hint: "<客户名/品类> [--industry catering|retail|edu] [--stage cold|growth|mature]"
---

## CRITICAL BEHAVIORAL RULES
You MUST follow these rules exactly. Violating any of them is a failure.
1. Execute steps in order. Do NOT skip ahead, reorder, or merge steps.
2. Write output files. Each step MUST produce its output file in `.siyu-team/`
   before the next step begins. Read from prior step files -- do NOT rely on context window memory.
3. Stop at checkpoints. When you reach a PHASE CHECKPOINT you MUST stop and wait for
   explicit user approval via the AskUserQuestion tool.
4. Halt on failure. If any step fails (尤其合规官命中 COMPLIANCE_RED), STOP immediately.
5. Use only local agents. All subagent_type references use agents bundled in this repo's plugins or `general-purpose`.
6. Never enter plan mode autonomously. This command IS the plan -- execute it.
（以上六条直接照搬 full-stack-feature.md:8-18，仅第4条补了合规红线）

## Pre-flight Checks
### 1. Check for existing session
检查 `.siyu-team/state.json` 是否存在：
- 存在且 status=="in_progress"：读出，显示 current_step，问用户 1.续跑 / 2.重开(归档旧档) / 3.退出
- 存在且 status=="complete"：问是否归档后重开
### 2. 初始化 state.json（字段见 §3c）
### 3. 解析 $ARGUMENTS：抽出 $CLIENT、--industry、--stage（缺则在 Step 0 调研里补问）

## Step 0 调研诊断（Interactive，团长亲自做）
用 AskUserQuestion 一次问一个，收齐：品类 / 阶段 / 现有私域规模 / 变现模式 / 当前核心痛点 / 可给的数据。
→ 写 `.siyu-team/00-intake.md` → Update state.json(current_step=1)
（若用户授权，可调 connectors/getnote.py 抓行业素材、bi_platform.py 验证口径，结果并入 00-intake.md）

## Step 1 按行业×阶段路由（团长决策，不花 token 的规则路由）
读 00-intake.md，调 `src/siyu_team/routing.py` 推断 task 类目，加载 knowledge/02-industry/<industry>/ 对应阶段册。
→ 写 `.siyu-team/01-routing.md`（产出：选定行业册 + 阶段重点 + 四官各自要重点回答的子问题）→ Update state

== PHASE CHECKPOINT 1 — User Approval Required ==
展示 00-intake 与 01-routing 摘要，AskUserQuestion 三选项：
  1. Approve -- 派四官评审
  2. Request changes -- 调整诊断/路由后重审（不前进）
  3. Pause -- 落盘退出（state.json 记 current_step="checkpoint-1"）
Do NOT proceed until user selects option 1.

## Step 2 并行派四官（多 Task 单 response）
Launch four agents in parallel using multiple Task tool calls in a single response:

Task(2a 公关官):
  subagent_type: "private-pr-officer-private-pr-officer"
  description: "从『私域即公关』视角评审 $CLIENT 的私域方案"
  prompt: |
    你是私域公关官，只用『私域即公关』这一个视角独立分析，不要提及其他官。
    ## 客户背景
    [内联 00-intake.md 全文]
    ## 路由结论
    [内联 01-routing.md 全文]
    ## Deliverables（按此结构输出）
    1. 信任资产现状盘点  2. 公关视角的核心问题  3. 可落地动作（触发人群/话术/时间/指标）
    4. 最脆弱的前提  5. 合规风险提示
  → 输出存到 .siyu-team/02a-pr.md
Task(2b 产品官): subagent_type:"content-product-officer-content-product-officer" …→ 02b-product.md
Task(2c 广告官): subagent_type:"ops-ad-officer-ops-ad-officer" …→ 02c-ad.md
Task(2d 合规官): subagent_type:"compliance-critic-compliance-critic"
  prompt 内联 00+01，Deliverables：企微红线核查 / 违禁词扫描 / 落地性质疑 → 02d-critic.md

四官互不读对方输出（都只读已落盘的 00+01），故可真并行。
→ Update state(completed_steps += [2a,2b,2c,2d])

## Step 3 主持收口（团长综合）
1. 跑 src/siyu_team/eval/cli.py 对四份产物打质量门分（见 §3d）。若命中 COMPLIANCE_RED → 打回对应官重做，不进收口。
2. stable_shuffle_traces 洗牌去位置偏差。
3. 用 §3e 的 host prompt 综合四官 → 写 `.siyu-team/04-playbook.md` + reports/deliberation.md(+.html)
   收口模式：默认 host_mode=codex（你这个掌握全程上下文的主控直接当团长综合）；
   需二审时 rounds=2，把第一轮综合当 H1 输入再审一遍。
→ Update state(status="complete")

== Completion ==
state.json: status="complete"。打印 final summary：
- 列出 00~04 全部产物路径
- 质量门得分 + 徽章
- Next Steps：①方案落飞书 docx(connectors/lark.py) ②埋点指标进某 BI 平台(connectors/bi_platform.py) ③复盘周期
```

### (b) 私域专家 SKILL.md 模板(以"社群促活官"为例)

> 落点 `plugins/content-product-officer/skills/reactivation-playbook/SKILL.md`。frontmatter `name` 必须==目录名,description 含触发句,body ≤8KB(超了拆 `references/`)。

```markdown
---
name: reactivation-playbook
description: 私域社群促活方法论库，含沉默用户分层、唤醒路径、三端话术模板、活动节奏表与转化口径。Use this skill when 设计社群促活方案、唤醒沉默用户、排活动节奏、或需要可直接群发的促活话术时。
version: 1.0.0
---

# 沉默用户唤醒与社群促活 Playbook（社群促活官）

## Overview
把促活拆成五步可执行流程：分层 → 选钩子 → 选话术 → 排节奏 → 看指标。
对齐方法论引擎「内容即产品」：每一个促活动作都当一个小产品来做（有钩子、有承接、有复购）。

## SOP：五步流程
### 1. 用户分层标准【待马甲填真实SOP，以下为占位示例】
- 活跃：7 天内有互动/下单
- 沉默：8–30 天无互动
- 流失风险：30 天以上无互动
- 唤醒优先级 = 历史客单价 × 最近互动衰减
### 2. 唤醒路径（按沉默深度升级）【示例占位】
1. 轻触达：群内 @ + 利益预告（不打扰）
2. 利益钩子：专属券/限时福利私聊
3. 1v1：人工私聊 + 真实关怀（最后手段）
### 3. 三端话术模板【待马甲填真实话术】
- 群公告 / 私聊 / 朋友圈，各给可直接复制模板（占位）
### 4. 活动节奏表【示例占位】
- 周日历：签到 / 秒杀 / 社群专属 / 裂变 的配比

## 交付模板（每个促活方案必须长这样）
| 动作 | 触发人群 | 话术 | 时间点 | 责任人 | 预期指标 | 风险兜底 |
|---|---|---|---|---|---|---|
| 示例：沉默唤醒券 | 沉默 8-30 天 | [话术] | 周四 20:00 | 群运营 | 触达率/回复率/转化率 | 退群率>X% 即停 |

## 成功指标（可埋点，对接某 BI 平台）
- 唤醒触达率 = 触达人数 / 沉默人数（分母=沉默用户，时间窗=单次活动）
- 回复率 / 转化率（首单）/ 复购率 / 退群率
- 红线：退群率超阈值即停，换低频高价值钩子

## 合规约束（合规官会查）
- ❌ 不设计诱导分享/欺骗式裂变  ❌ 不用绝对化用词  ❌ 不未授权批量加好友
- 裂变走企微官方允许路径；信息收集有授权口径

> 注：本 skill 的方法论框架可公开；具体话术/分层阈值/节奏配比是马甲护城河，标【待马甲填真实SOP】处由马甲注入。
```

(同款模板复制成公关官、产品官、广告官的 skill,只换标题/五步内容/指标/合规重点。)

### (c) state / 进度持久化结构 —— `.siyu-team/state.json`(由 `src/siyu_team/state.py` 读写)

> 仿 `full-stack-feature.md:44-58`,`current_step` 一个字段同时编码 普通步/卡点/完结 三态。

```json
{
  "client": "$CLIENT",
  "industry": "catering",
  "stage": "growth",
  "status": "in_progress",
  "current_step": 1,
  "completed_steps": [],
  "files_created": [],
  "officer_scores": {},
  "compliance_flags": [],
  "host_rounds": 0,
  "started_at": "ISO_TIMESTAMP",
  "last_updated": "ISO_TIMESTAMP"
}
```

`state.py` 三个核心函数(签名即可,逻辑照搬母版):
- `check_session() -> dict|None`:存在且 in_progress 则返回供续跑;幂等入口。
- `init_state(client, industry, stage)`:写死字段结构。
- `update(step=..., add_file=..., add_completed=..., status=...)`:每步末手动调。
- `current_step` 取值流转:`1 → "checkpoint-1" → 2 → ... → "complete"`(Pause 时写 `"checkpoint-N"`,靠 check_session 续跑兜底)。

### (d) 私域方案质量门 rubric —— `src/siyu_team/eval/rubrics.py`(+ `engine.py` 合成)

> 照 plugin-eval:维度加权 → 每维跨三层混合 → `composite = Σ(权重×维度分) × 100 × 反模式惩罚` → 阈值 exit 1。

**维度权重表**(替换原十维):

| 维度 | 权重 | 测什么 | 主要靠哪层 |
|---|---|---|---|
| 转化口径严谨度 | 0.22 | 漏斗每跳(UV→加微→首单→复购→裂变)分子/分母/时间窗是否写清；不把"累计注册"伪装成"月活" | judge 0.6 / static 0.4 |
| 合规安全 | 0.20 | 企微封号红线/广告法绝对化/未授权收集个人信息 | static 0.5 / judge 0.5 |
| 可落地性 | 0.18 | 一线店长能否照做，是否依赖买不到的工具/人力 | judge 0.5 / mc 0.5 |
| SOP 完整度 | 0.15 | 引流→承接→转化→复购→裂变 全链路，每环 动作/话术/责任人/时间 齐 | static 0.6 / judge 0.4 |
| ROI 可验证 | 0.10 | 可埋点指标 + 验证周期 + 失败回滚条件 | judge 0.4 / mc 0.6 |
| 触发精准度 | 0.08 | 是否真对上客户行业/客单/阶段，不是通用模板套壳 | judge 0.7 / static 0.3 |
| 资源校准 | 0.04 | 颗粒度匹配体量，小店别给 30 人中台方案 | judge 0.55 / static 0.3 / mc 0.15 |
| 风格一致 | 0.03 | 解释者口吻、不灌鸡汤金句、不炫资历（马甲 register） | static 0.7 / judge 0.3 |

权重和=1.0。

**锚定 rubric 五档示例**(给 LLM 判官,照 `rubrics.md` 0.0/0.2/0.4/0.6/0.8 格式):

```
维度「转化口径严谨度」(0.22)
0.0–0.19 — 通篇"提升转化""做大私域"，零口径、零分母、零时间窗。
0.20–0.39 — 提了转化率但口径含糊：不说分母是 UV 还是加微数，不说统计周期。
0.40–0.59 — 给了漏斗某一跳口径，但加微率/成交率/复购率至少缺一个定义。
0.60–0.79 — 每一跳都有明确口径，仅个别指标边界模糊。
0.80–1.00 — 全漏斗口径闭环，区分"累计"与"周期"，大数给约束条件。

维度「合规安全」(0.20)
0.0–0.19 — 含明确封号动作(诱导分享/外挂群发/虚拟定位)或广告法绝对化词。
…
0.80–1.00 — 合规闭环：每个拉新/裂变动作标注企微规则依据，含封号应急预案+授权同意模板。

维度「SOP 完整度」(0.15)
0.0–0.19 — 只有理念，无可执行步骤。
…
0.80–1.00 — 五环闭环，每环 动作/话术/责任人/触发时机/SLA 齐全，附首日 checklist。
```

(可落地性/ROI 可验证/触发精准度/资源校准/风格一致 同样五档,结构照搬,略。)

**静态层反模式**(`eval/static.py`,纯正则,免费):

| Flag | 触发条件 | 惩罚 severity |
|---|---|---|
| `COMPLIANCE_RED` | 命中违禁词库(诱导分享/外挂/最/第一/100%/永久) | 0.20 **+ 单独硬卡 exit 1** |
| `NO_CALIBRATION` | 出现"转化率/复购率"但无数字口径/分母 | 0.15 |
| `ABSOLUTE_CLAIM` | 广告法绝对化用词 | 0.10 |
| `NO_RESPONSIBLE_PARTY` | SOP 段无"责任人/谁来做" | 0.10 |
| `TEMPLATE_STUB` | 方案<行数阈值且无客户行业专有名词(疑似套壳) | 0.10 |
| `NO_METRIC` | 全文无任何可埋点指标名 | 0.10 |

惩罚乘法照搬 `penalty = max(0.5, 1.0 - 0.05 * count)`。

**蒙卡可靠性**(`eval/monte_carlo.py`,同一客户诉求生成 N 份测稳):
```
可靠性分 = 0.40×命中率(N份里多少给了可执行SOP而非空话)
         + 0.30×(1−CV)(关键决策如加微路径/复购周期的一致性)
         + 0.20×(1−崩溃率)(多少份漏掉合规/口径)
         + 0.10×篇幅效率
```
配 Wilson/Clopper-Pearson 置信区间,对外可说"50 次生成里 92% 命中可执行 SOP,95% CI [0.85,0.96]"。

**徽章 + CI 硬门**(`eval/cli.py`,照 `cli.py:91-96`):

| 徽章 | 方案分 | 含义 |
|---|---|---|
| Platinum ≥90 | 进案例库 |
| Gold ≥80 | 可直接交付客户 |
| Silver ≥70 | 内部复核后交付 |
| Bronze ≥60 | 需返工 |
| <60 | 不交付 |

**入驻硬门**:`方案分 < 80 或命中 COMPLIANCE_RED → exit 1`,专家方案打回。用法:
```bash
siyu-eval score .siyu-team/04-playbook.md --threshold 80   # 低于 80 或踩合规红线 exit 1
```

### (e) 主持人(团长)收口 prompt 草案 —— `src/siyu_team/host.py` 的 `build_host_prompt()`

> 结构照搬 `heavy.py:196-245`,只改身份与五段为入驻决策版。核心句"不投票不平均、评推理质量、保留少数意见"直接对位 `heavy.py:204`。

```text
<task>
你是「私域专家团」的团长，私域操盘手画像，负责对四官的独立评审拍板。
议题：{question}
入驻/方案成功标准：{success_criteria}
硬约束：{constraints}

四官（公关官 / 产品官 / 广告官 / 合规官）已各自独立给出意见，互相不知道对方写了什么。
你的任务不是投票，也不是把四个意见平均，而是评估每位的推理质量，找出他们互相补足的地方，
保留有价值的少数意见（哪怕只有一个官反对），最后替团队给出一个能落地的判断。
如果某官的关键前提站不住，明确点出来，不要因为他职位在就采信。
合规官的红线意见拥有一票否决权：只要他标了 COMPLIANCE_RED，方案不得通过，先整改。
如果这是第 2 轮，请把上一轮主持综合(H1)也当作一个可审查的输入，而不是最终答案。
</task>

<officers>
{把四官产出按 <officer>Label/角色/Content</officer> 块依次贴入，已洗牌去位置偏差}
</officers>

<output_rules>
用中文写给团队成员看，像内部拍板会，不像报告。短段落，重点加粗独立成段。
不要用"confidence""加权""综上所述""总而言之"这类词。不确定的地方直说。
口吻：解释者，谦逊沉稳克制，不灌鸡汤金句、不炫资历（这是团长的真实声音 register）。

按这个结构输出：

## 四官吵到哪了
两三段：哪里四个人其实一致，哪个分歧最要命，为什么这个分歧决定方案能不能落地。

## 逐官点评
每位官 3-5 句：他这次最有价值的判断是什么，又漏看了什么。
（公关官扣『私域即公关』、产品官扣『内容即产品』、广告官扣『运营即广告』各自的视角是否到位。）

## 团长拍板
两到三句给最终答复：方案通过 / 整改后通过 / 不通过，可带条件，但不要躲在条件后面。
最后一句让人记得住。

## 落地前必须先解决的事
1-3 条还没解决、但不解决就别上线的硬问题（合规红线优先）。

## 如果决定执行，第一周做什么
1-3 条具体动作，落到谁、做什么、看什么指标（指标须可埋点进某 BI 平台）。否则省略本节。
</output_rules>
```

`host.py` 还需 `stable_shuffle_traces(question, traces)`(去位置偏差)和 `write_report()`(落 `deliberation.md` + 自带样式 HTML),均照搬 `heavy.py:474-530`。

### (f) 角色配置表结构 —— `src/siyu_team/roster.py`(+ `examples/roster.example.json`)

> 角色=视角:换 prompt/换绑定模型 完全不碰代码。字段复用 qiaomu `HeavyPerspectiveInput`(`schemas.py:144-152`):`name` / `description` / 可选 `provider` / 可选 `model` / 可选 `subagent_type`(指向 plugins 里的 agent)。

`examples/roster.example.json`:

```json
{
  "version": "1.0.0",
  "officers": [
    {
      "name": "公关官",
      "engine": "私域即公关",
      "description": "只盯信任资产与口碑：IP/朋友圈人设/差评危机话术/转介绍。私域里每一次触达都是一次公关。",
      "subagent_type": "private-pr-officer-private-pr-officer",
      "model": "sonnet"
    },
    {
      "name": "产品官",
      "engine": "内容即产品",
      "description": "只盯内容与承接：选题/钩子/承接话术/社群促活，把内容当产品做（有钩子有承接有复购）。",
      "subagent_type": "content-product-officer-content-product-officer",
      "model": "sonnet"
    },
    {
      "name": "广告官",
      "engine": "运营即广告",
      "description": "只盯获客与转化漏斗：每个运营动作即一次广告投放，关心 UV→加微→首单→复购 每一跳的口径与埋点。",
      "subagent_type": "ops-ad-officer-ops-ad-officer",
      "model": "sonnet"
    },
    {
      "name": "合规官",
      "engine": "Critic",
      "description": "专找企微封号风险/违禁词/过度承诺/未授权收集个人信息，团里的怀疑者，对红线有一票否决权。",
      "subagent_type": "compliance-critic-compliance-critic",
      "model": "opus"
    }
  ],
  "host": { "mode": "codex", "rounds_max": 2 }
}
```

`roster.py` 提供 `load_roster()` / `normalize_officers(supplied, k)`(用户传了用用户的、否则用默认,照 `heavy.normalize_perspectives`)。**想加财务官/客服官**:roster.json 加一条 + 在 plugins 新建对应 agent,代码零改动(K 上限 5、officers 数组上限 6,照 qiaomu schema)。`model` 按难度挂:四官多 sonnet(要推理共情),合规官挂 opus(红线判断最重),套模板的轻量活可降 haiku。

---

## 4) 落地路线

### 3 档(进场可信)—— 先做这 9 个文件,跑通一条客户链就能立项

只用 **wshobson 范式 A 编排 + qiaomu host 收口**,先不上 eval 全流水线、不上多端分发。

1. `plugins/_orchestrator/commands/siyu-onboard.md` —— 团长四 Step 编排(§3a)
2. `src/siyu_team/state.py` + 运行时 `.siyu-team/state.json` —— 续跑(§3c)
3. `src/siyu_team/roster.py` + `examples/roster.example.json` —— 四官角色表(§3f)
4. `plugins/private-pr-officer/agents/private-pr-officer.md`(+另三官 agent.md) —— 四官人设(§3b 同款 frontmatter+SOP)
5. `plugins/content-product-officer/skills/reactivation-playbook/SKILL.md` —— 至少一个 skill 跑通(§3b)
6. `src/siyu_team/host.py` —— 主持收口 prompt(§3e)
7. `knowledge/01-wechat-official/compliance/redlines.md` —— 合规底座(可公开,先有)
8. `knowledge/02-industry/catering/stages.md` —— 餐饮行业×阶段定义(基线数据标【待马甲填】)
9. `README.md` + `CLAUDE.md` —— 三句话方法论 + source-of-truth 约定

**这 9 个文件 = 一个能对一个餐饮客户跑完"调研→四官→团长拍板→出 playbook"的最小可信闭环。** 马甲的真实 SOP 此时是占位,但骨架已能演示。

### 4 档(进头部)—— 在 3 档之上加这四层

- **质量门层**(护城河核心):`src/siyu_team/eval/{static,judge,monte_carlo,engine,rubrics,cli}.py`(§3d)。这层让方案"有可复现分数 + 置信区间 + CI 自动拦截",是区别于"网上私域 prompt 合集"的全部技术差异。`make eval` 接进 orchestrator Step 3。
- **行业 RAG 层**:补齐 `knowledge/02-industry/catering/benchmarks.md`(餐饮真实基线)+ `knowledge/03-majia-sop/`(护城河 SOP,私仓/git-ignore)。四官 skill 检索这层。
- **多专家并行 + 二审**:host.py 上 `rounds=2` 团长二审;Step 2 真并行四官(多 Task 单 response)。
- **多端分发层**(可选,只在要把专家团给别人用时):`tools/generate.py` + `tools/validate_generated.py`,把四官 plugin 分发到 codex/cursor/opencode/gemini。

### 与马甲已有工具链接入(全部走 `src/siyu_team/connectors/` 薄包装)

| 工具 | connector 文件 | 接在哪个环节 | 干什么 |
|---|---|---|---|
| 某 BI 平台(bi-cli/bi-ds/bi-vis) | `bi_platform.py` | Step 0 调研 + Step 3 收口 Next Steps | 取真实漏斗数据验证转化口径(eval 转化口径维度的事实校验);方案埋点指标建成某 BI 平台卡片/看板 |
| 飞书全家桶 | `lark.py` | Completion | 04-playbook.md 落成飞书 docx 交付;进度同步到飞书;改正文走 lark-cli str_replace |
| Get笔记 | `getnote.py` | Step 0 调研 | 抓行业素材/竞品私域打法,并入 00-intake.md |
| Nowledge Mem | `nowledge_mem.py` | 四官 skill 检索 | 马甲真实 SOP 语义检索(护城河 RAG 取数,知识库第三层的检索入口) |
| Obsidian 本地库 | (复用现有同步) | 知识沉淀 | 沉淀成功案例进案例库(Platinum 方案归档) |

密钥走 keychain 指针(照 qiaomu `registry.py:107-120`),connector 只存 `keychain:siyu-team/<tool>` 引用,真 token 不入库——同时满足公开 repo 提交脱敏红线。

---

**忠实度声明**:本蓝图所有机制均来自四份 teardown 标注的真实文件,未发明标杆里没有的东西。`code_template_quality`/`robustness` 两维(teardown 标注的文档-实现缺口)未引入。马甲私域内容部分(四官 skill 的话术/分层阈值/节奏配比、行业真实基线、第三层 SOP)均给结构占位 + 示例并标 `【待马甲填真实SOP】`。

相关绝对路径(供后续建仓参照):标杆母版在 `wshobson-agents/plugins/full-stack-orchestration/commands/full-stack-feature.md`(编排)、`.../qiaomu-llm-mcp/src/qiaomu_llm_mcp/heavy.py`(主持收口)、`.../wshobson-agents/plugins/plugin-eval/`(质量门);新 repo 建议落在 `siyu-expert-team/`。
