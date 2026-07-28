---
description: "私域专家团团长：调研诊断客户私域现状 → 按行业/阶段路由 → 并行派公关/产品/广告/合规四官 → 团长主持收口出可落地 playbook"
argument-hint: "<客户名/品类> [--industry catering|retail|edu] [--stage cold|growth|mature]"
---

# 私域专家团 · 团长编排（siyu-onboard）

> 如只需单个动作（写朋友圈 / 出群发 / 给话术），直接调用 siyu-execution 对应 skill，无需全盘诊断。

> **讲人话**：这是后台编排文档，但**最终交付给用户的话**遵循讲人话铁律——别对店老板暴露"团长/四官/升舱/playbook"这些词，产物就叫「搭建清单 / 怎么做」。面对普通店老板（问得泛、没运营黑话），优先走零依赖的 [`../../siyu-core/skills/siyu/references/整盘怎么搭-老板版.md`](../../siyu-core/skills/siyu/references/整盘怎么搭-老板版.md)，讲人话 + 出图 / 网页，别硬上这套复杂编排。

> 母版 = wshobson `full-stack-feature.md` 七段式 + qiaomu HeavySkill 主持收口。
> 编排走范式 A（单 orchestrator + 文件状态机），收口走主持人模式（四官独立采样、团长不投票只评质量）。

## CRITICAL BEHAVIORAL RULES
You MUST follow these rules exactly. Violating any of them is a failure.
1. **按顺序执行**。不要跳步、不要重排、不要合并步骤。
2. **落盘传状态**。每步必须在 `.siyu-team/` 写出自己的产物文件后，下一步才开始。从上一步的文件读取——**不要靠上下文记忆传递**。
3. **卡点停**。到 PHASE CHECKPOINT 必须停下，用 `AskUserQuestion` 等用户明确批准。
4. **失败即停**。任何步骤失败（尤其合规官命中 `COMPLIANCE_RED`）立即 STOP。
5. **只用本地 agent**。所有 `subagent_type` 指向本 repo plugins 里的 agent 或 `general-purpose`。
6. **不自行进 plan mode**。这个 command 就是计划——执行它。
7. **先结构化再派发**。没有通过 `SiyuRuntime.plan()` 生成有效 Task 和 RouteDecision，不得把原始文本直接交给 Skill 或四官。

（1–6 照搬 full-stack-feature.md:8-18，仅第 4 条补了合规红线；第 7 条是 Runtime 边界。）

## Pre-flight Checks
1. **查会话**：`.siyu-team/state.json` 是否存在？
   - 存在且 `status=="in_progress"`：读出，显示 `current_step`，问用户 **1. 续跑 / 2. 重开（归档旧档）/ 3. 退出**。
   - 存在且 `status=="complete"`：问是否归档后重开。
2. **解析 `$ARGUMENTS`**：抽出 `$CLIENT`、`--industry`、`--stage`。
3. **建立结构化计划**：调 `SiyuRuntime.plan($ARGUMENTS, hints)`，把 `plan.to_dict()` 写入 `.siyu-team/task.json`。
   - `decision.skill != "siyu-onboard"`：停止本命令，按 RouteDecision 转给对应单步能力。
   - `needs_clarification=true`：只在 Step 0 补 `required_fields`，不得提前创建或派发四官上下文。
4. **初始化 state.json**（字段见 `src/siyu_team/state.py` / docs/blueprint.md §3c），调 `state.init_state(client, industry, stage)`。

---

## Step 0 · 调研诊断（Interactive，团长亲自做）
用 `AskUserQuestion` 一次问一个，收齐：
- 品类（餐饮/零售/教培/其他）
- 阶段（冷启动/扩张/成熟）
- 现有私域规模（好友数/群数/到店或客流）
- 变现模式（堂食/外卖/电商/课程…）
- 当前最核心的痛点（加不上人/不互动/群死了/不复购/不裂变…）
- 能给的真实数据（有就给，没有就估）

（若用户授权，可调 `connectors/getnote.py` 抓行业素材、`connectors/bi_platform.py` 拉真实漏斗验证口径，结果并入。）
→ 写 `.siyu-team/00-intake.md` → `state.update(step=1, add_file="00-intake.md", add_completed=0)`

## Step 1 · 按行业×阶段路由（规则路由，不花 token）
读 `00-intake.md`，把调研字段映射进 `Task.context`，重新调 `SiyuRuntime.plan()`。只有 RouteDecision 不再缺字段时才更新 `.siyu-team/task.json`，并加载 `knowledge/02-industry/<industry>/` 行业册。
产出：选定行业册 + 阶段重点 + **四官各自要重点回答的子问题**。
→ 写 `.siyu-team/01-routing.md` → `state.update(step="checkpoint-1")`

### == PHASE CHECKPOINT 1 — User Approval Required ==
展示 `00-intake` 与 `01-routing` 摘要，`AskUserQuestion` 三选项：
1. **Approve** — 派四官评审
2. **Request changes** — 调整诊断/路由后重审（**不前进**）
3. **Pause** — 落盘退出（`state.json` 记 `current_step="checkpoint-1"`，靠 Pre-flight 续跑兜底）

**未选 1 不得进 Step 2。**

## Step 2 · 并行派四官（多 Task 单 response）
**Launch four agents in parallel using multiple Task tool calls in a single response.**
每个 Task 必须先用 `context.build_agent_context()` 做字段白名单投影，再由 `perspectives.build_isolated_officer_prompt()` 生成；禁止调用接受未过滤 intake 的旧接口：

- **Task 2a 公关官** `subagent_type: "private-pr-officer-private-pr-officer"` → `.siyu-team/02a-pr.md`
- **Task 2b 产品官** `subagent_type: "content-product-officer-content-product-officer"` → `.siyu-team/02b-product.md`
- **Task 2c 广告官** `subagent_type: "ops-ad-officer-ops-ad-officer"` → `.siyu-team/02c-ad.md`
- **Task 2d 合规官** `subagent_type: "compliance-critic-compliance-critic"` → `.siyu-team/02d-critic.md`

四官互不读对方输出，也不直接读取 `00-intake.md`；公关/产品/广告官看不到原始请求，只有合规官可读取已脱敏的 `source_text` 与风险字段，故可真并行。
→ `state.update(add_completed="2a/2b/2c/2d")`

## Step 3 · 主持收口（团长综合）
1. 跑 `make eval FILE=.siyu-team/02*.md`（`src/siyu_team/eval/cli.py`）对四份产物打质量门分。**命中 `COMPLIANCE_RED` → 打回对应官重做，不进收口。**
2. `host.stable_shuffle_traces()` 洗牌去位置偏差。
3. 用 `host.build_host_prompt()`（docs/blueprint.md §3e）综合四官 → 写 `.siyu-team/04-playbook.md` + `reports/deliberation.md`。
   - 默认 `host_mode=codex`：你（掌握全程上下文的主控）直接当团长综合。
   - 需二审时 `rounds=2`，把第一轮综合当 H1 输入再审一遍。
→ `state.update(status="complete")`

## == Completion ==
`state.json: status="complete"`。打印 final summary：
- 列出 `00~04` 全部产物路径
- 质量门得分 + 徽章
- **Next Steps**：① 方案落飞书 docx（`connectors/lark.py`）② 埋点指标进某 BI 平台（`connectors/bi_platform.py`）③ 复盘周期
- 如本轮已有可跨对话追踪的结论或假设，收尾提示一次：「有结论想留下，输入 `/siyu-save`。」一次对话最多提示一次。

---

## 不知道下一步用哪个 skill？

输入 `/siyu`。

这是私域工具箱的导航入口。它会读取刚才的具体结论，选择当前最值得处理的一个方向，
并直接路由到对应 skill。迷路了就回 `/siyu`。
