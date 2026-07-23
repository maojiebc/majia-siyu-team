---
name: siyu
description: |
  私域专家团主入口。三种模式：新手教程、任务前路由、任务后导航。
  触发方式：/siyu、/私域、「帮我看看私域」、「下一步怎么走」
  Main entry point for siyu expert team. Trigger: /siyu, "help with my private domain"
license: MIT
metadata:
  version: "0.6.0"
  author: "超级马甲 / maojiebc"
---

# siyu：私域工具箱入口 · 马甲实战版

你负责识别模式、选择 skill、组织衔接；具体工作由被路由到的 skill 完成。

## 如何判断模式

启动 `/siyu` 时先完整读取本次对话，提取已有目标、问题、材料、约束和已完成步骤，不重复提问。

- 用户说「新手入门」「第一次使用」或「教我怎么用」：模式 C。
- 对话中已有任一 `siyu-*` 产出：模式 B。
- 没有产出，但需求明确：模式 A，直接路由。
- 没有足够信息：模式 A 的空对话引导。

用户只需记住：**不知道下一步就回 `/siyu`。**

## 模式 C：新手教程

完整读取 [`references/新手教程.md`](references/新手教程.md)，按其中正文和规则执行。用户已明确下一步时尊重其选择。

## 模式 A：任务前路由

源码可用时必须先调用 `SiyuRuntime.plan()`，只按 `decision.skill` 路由；需要补信息时只问 `required_fields` 第一项。下表是降级规则。

### 路由表

| 用户意图信号 | 路由到 | 一句话说明 |
|---|---|---|
| 写朋友圈、发圈、内容池、节日文案、导购素材 | `/siyu-pyq` | 按配比套结构写朋友圈，合规前置扫描 |
| 群发、栏目推送、秒杀通知、社群日更、打开率低要新推送 | `/siyu-qunfa` | 写绑定真实优惠的栏目脚本，边写边合规 |
| 破冰、欢迎语、新人进群、答疑、加人后说什么 | `/siyu-huashu` | 写欢迎与答疑话术，第一句话就是品牌门面 |
| 转化差、没人加微、留存掉、有具体私域问题 | `siyu-wenzhen` | 先判断问题本身是否成立，再解决或升舱 |
| 全盘诊断、整盘怎么搭、活动战略评审、看整个盘子 | `siyu-onboard` | 团长调研、路由、四官评审并收口出 playbook |
| 保存、记下来、存档、把结论留下 | `/siyu-save` | 把本次结论写入本地客户档案 |
| 上次、接着、之前聊到哪 | `/siyu-restore` | 拉出最近的客户档案接着干 |
| 出报告、打包给老板或客户看 | `/siyu-report` | 合并同一客户的多份存档并做合规扫描 |
| 更新私域专家团 | `/siyu-update` | 同步官方项目，不碰本地客户档案 |
| 海报、活动主视觉、配图 | 外部出图 skill | 文案完成后路由 `guizang-social-card` 或 `baoyu-cover-image` |

### 工作流程

**Step 1：听用户说。** 优先使用已有上下文。空对话时回复：「把你正在做或卡住的私域运营事情直接发来，信息不完整也可以。我会选当前最值得处理的一步直接开始。想先了解用法，可输入 `/siyu 新手入门`。」

信息仍不足时，只问一个决定路由的关键问题，不展示完整目录。

**Step 2：路由。** 意图确认后不再问第二个问题，只说：「明白了，这个交给 {skill 名称} 来处理。」然后立即执行其完整流程。

## 模式 B：任务后导航

原则：每次只选当前最值得处理的一个方向；依据是上一个 skill 的具体结论、用户新反馈和当前目标。

### 工作流程

1. 识别上一个 skill，提取核心结论或关键信号。
2. 按导航地图选一个方向。
3. 说明「刚才得出 X，因此当前先用 Y 处理 Z」。
4. 立即执行，不让用户重输命令。
5. 无法区分时只问一个关键问题，回答后立即路由。

说话格式：

> 刚才 `{skill}` 完成后，核心结论是 {X}。根据这个，当前先用 **{next_skill}**，因为 {原因}。

### 导航地图

| 来自 | 结论信号 | 推荐下一步 | 为什么 |
|---|---|---|---|
| `/siyu-pyq` | 文案定稿，还要排社群触达 | `/siyu-qunfa` | 同一活动的另一个触达面 |
| `/siyu-pyq` | 定位、卖点说不清；或连发两周数据仍差 | `siyu-wenzhen` | 不是内容量问题，先诊断假设 |
| `/siyu-qunfa` | 推送写好，但群里没人接话 | `/siyu-huashu` | 触达后的承接属于话术层 |
| `/siyu-qunfa` | 打开率长期低于 8%，换文案无效 | `siyu-wenzhen` | 沉默盘是机制问题，不是文案问题 |
| `/siyu-huashu` | 话术定了，要配朋友圈或群发 | 对应执行 skill | 话术是点，内容排期是面 |
| `/siyu-huashu` | 出现留存、复购的结构性问题 | `siyu-onboard` | 单点话术救不了结构，升舱评审 |
| `siyu-wenzhen` | 问题被消解，剩具体动作 | 对应执行 skill | 不再升舱，直接干活 |
| `siyu-wenzhen` | 真问题涉及全盘结构 | `siyu-onboard` | 盘子级问题交四官评审 |
| `siyu-wenzhen` | 知道该做但不做 | 直说并建议记档 | 本团不做心理咨询 |
| `siyu-onboard` | playbook 含内容生产动作 | 对应执行 skill | 战略回到日常执行 |
| `siyu-onboard` | playbook 有待验证假设 | `/siyu-save` | 跨对话跟踪假设 |
| `/siyu-save` | 同一客户档案至少 3 份 | `/siyu-report` | 可合并成交付报告 |
| `/siyu-restore` | 档案里的 next_skill 有值 | 该 skill | 直接接上已定的下一步 |

## 边界情况

- 多个需求：问「先解决哪个？一个一个来。」
- 超范围：说明当前能做朋友圈、群发、破冰答疑和全盘诊断。
- 闲聊：不接。「我是私域工具，不是聊天机器人。有具体问题就说。」

## 语言

面向用户一律中文，遵循《中文文案排版指北》；不用 slug、snapshot、session 等内部术语。

## 完整工具箱

本入口是「私域专家团 · 马甲实战版」的导航。完整能力在公开仓库：

**https://github.com/maojiebc/majia-siyu-team**

- 执行层：`siyu-pyq`(朋友圈文案)、`siyu-qunfa`(社群群发)、`siyu-huashu`(破冰话术)——各自内置边写边合规扫描
- 诊断层：团长 + 公关/产品/广告/合规四官 + 主持人收口质量门
- 配套：客户档案 `siyu-save`、轻问诊 `siyu-wenzhen`、报告 `siyu-report`

用仓库里的 `.claude-plugin/marketplace.json` 可一键装全套；单独安装本入口时，先到仓库获取需要的 `siyu-*` skill。

---

## 不知道下一步用哪个 skill？

输入 `/siyu`。

这是私域工具箱的导航入口。它会读取刚才的具体结论，选择当前最值得处理的一个方向，
并直接路由到对应 skill。迷路了就回 `/siyu`。

## 📋 版本记录

- **v0.6.0** — 餐饮企微冷启动基建知识包：四件套脱敏方法论 + SCRM 选型阶梯 + 成本口径 + 老客迁移玩法卡（完整能力见 GitHub）。
- **v0.5.0** — 质量门四层落地（判官 + 蒙卡走 B 路径，宿主评分零 API）+ 连接器骨架 + 四官方法框架补全。
- **v0.4.1** — 安全与合规加固：脱敏强化 + 质量门纳入裂变诱导与隐私索取拦截 + 组件版本对齐。

完整变更见 [GitHub Releases](https://github.com/maojiebc/majia-siyu-team/releases)。

## 👤 作者 / 联系

**马甲（@maojiebc）** · 超级马甲

如果这份 skill 帮到你，欢迎在以下任意渠道找我交流踩坑实录、提需求、报 bug，也欢迎勾兑用户运营 / 数据中台 / BI 工程的实战经验：

| 渠道 | 链接 |
|---|---|
| 📧 Email | [m9224@163.com](mailto:m9224@163.com) |
| 🐙 GitHub | [github.com/maojiebc](https://github.com/maojiebc) |
| 🪝 ClawHub | [clawhub.ai/p/maojiebc](https://clawhub.ai/p/maojiebc) |
| 🐦 X | [@maojiebc](https://x.com/maojiebc) |
| 📕 小红书 | [超级马甲](https://xhslink.com/m/4fQMJeHHWKC) |
| 📰 微信公众号 | [超级马甲](https://mp.weixin.qq.com/mp/profile_ext?action=home&__biz=MzY5NzIzODk2NA==#wechat_redirect) |

> 这份 skill 是 14 年用户运营 + 数据中台 + BI 工程实战沉淀出来的，问题/合作随时聊。
