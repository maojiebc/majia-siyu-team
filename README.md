# 私域专家团 · 马甲实战版

[![Skill Version](https://img.shields.io/badge/skill-v2.0.0-0b5cad.svg)](https://github.com/maojiebc/majia-siyu-team/releases)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)
[![ClawHub](https://img.shields.io/badge/ClawHub-majia--siyu-6b4bd8.svg)](https://clawhub.ai/s/majia-siyu)
[![SkillHub](https://img.shields.io/badge/SkillHub-siyu-ef6c00.svg)](https://skillhub.cn)
[![skills.sh](https://img.shields.io/badge/skills.sh-install-24a148.svg)](https://skills.sh/maojiebc/majia-siyu-team)
[![Release](https://img.shields.io/github/v/release/maojiebc/majia-siyu-team?label=release&color=success)](https://github.com/maojiebc/majia-siyu-team/releases)

> **私域专家团 · 马甲实战版**
>
> 把马甲做私域的判断装进你的 AI。日常文案直接出活；遇到拿不准的事，按他真做过的事给判断。入口只有一个：`/siyu`。

<p align="center">
  <img src="https://raw.githubusercontent.com/maojiebc/majia-siyu-team/main/assets/icon.png" alt="私域专家团图标" width="120">
</p>

## 这个包和通用 AI 差在哪

通用 AI 也会写朋友圈、也会讲私域方法。它没有的，是一个人真踩过的坑。

马甲在一家几百家店的连锁咖啡，从短信一条条发，做到企业微信社群三个月攒下一百万好友，一年发 1500 多条推送基本没出错；后来又给餐饮老板做咨询。这个包里装的就是这些事：当时什么情况，他怎么判断，结果怎样，换到你家店该怎么改。

你问的处境对得上，AI 会先说马甲会怎么判断，再讲当年那件事；对不上，就按通用方法正常回答，不硬套。

## 马甲的判断

挑几条，完整的 20 条见[判断清单](knowledge/cases/00-判断清单.md)：

| 判断 | 当年那件事 |
|---|---|
| 做社群之前，先算清你现在找回一个老顾客要花多少钱 | [短信那笔账](knowledge/cases/01-短信那笔账.md) |
| 门店拉新先找没动起来的店，不是标杆店 | [线上铺满三个月还是涨得慢](knowledge/cases/02-门店拉新先找没动的店.md) |
| 台卡上写顾客这一单能省多少，别写“进群有福利” | [台卡上那一句话](knowledge/cases/03-台卡一句话.md) |
| 码细到每个位置，最后发现决定数据的，是收银员开不开口 | [每个位置一个码](knowledge/cases/04-每个位置一个码.md) |
| 新店让顾客直接进群，成熟老店先加好友再进群 | [社群 1.0 到 2.0](knowledge/cases/05-先进群还是先加好友.md) |
| 店多到要在一刻钟里发完几千个群，就只能总部来发 | [8:30 的早餐消息下午才发](knowledge/cases/06-总部接管发送.md) |
| 推送之前，先让管系统的、管货的、管门店的人知道 | [开工日小程序被推崩了](knowledge/cases/07-推送前先问三个人.md) |
| 私域的数再好看，没留一组人不发，就说不清多做了多少生意 | [两个数说明不了什么](knowledge/cases/08-两个数说明不了什么.md) |
| 分层先看顾客多久没来，能让你下一句话不一样才有用 | [贝果和咖啡](knowledge/cases/09-分层别搞复杂.md) |
| 企业微信先用原生功能把地基搭起来，跑通了再花钱买系统 | [一次两小时的咨询](knowledge/cases/10-餐饮连锁两小时咨询.md) |

## 装和不装比

这个包有没有用，只看一件事：同样的问题，装了比没装答得好。每次改技能或案例，都拿同一批题让装和不装的 AI 各答一遍，打乱、隐去版本名，交给没参与的评审打分。方法和历次结果见 [`evals/`](evals/README.md)。

2026-10-21 跑了四轮，14 题，每轮两个模型评审：

| 对比 | 结果（胜 / 平 / 负，两个评审） |
|---|---|
| 装了 vs 不装（第三轮） | 7 / 5 / 2，8 / 5 / 1 |
| 加了案例的版本 vs v1.8.1（第三轮） | 4 / 7 / 3，5 / 3 / 6 |
| 再加精简排版和 emoji vs v1.8.1（第四轮） | 7 / 2 / 5，11 / 1 / 2 |

马甲本人盲评了第三轮：分数打平，但每题最想发给老板的那份，加了案例的版本被选了 8 次，v1.8.1 5 次，不装技能 1 次。第四轮按他说的偏好（结论放第一行、排版好读、文案带 emoji）改了，评审标准也加了这两条，所以第四轮的赢面有一部分来自标准本身；他本人再盲评，分数还是打平，“最想要”这一版被选了 8 次，v1.8.1 4 次。

题少、只采样一次，只能说“这些题上”。真实老板的问题收到后会加进题库。

## 能力地图

一次安装拿到完整能力。你不必全记，路由会按处境挑选；下表方便人肉查找。

### 1. 统一入口

| 能力 | 什么时候用 | 产出 |
|---|---|---|
| `/siyu` | 不知道从哪开始 / 下一步怎么走 | 新手教程、任务路由、任务后导航 |
| `/siyu-update` | 升级私域专家团 | 同步官方项目；不碰本地客户档案 |

### 2. 高频执行 · 边写边合规

| 能力 | 什么时候用 | 产出 |
|---|---|---|
| `/siyu-pyq` | 写朋友圈、内容池、节日素材 | 可直接发的朋友圈文案 |
| `/siyu-qunfa` | 群发、社群栏目、秒杀通知 | 群发脚本、承接动作、机制提醒 |
| `/siyu-huashu` | 欢迎语、破冰、答疑 | 分场景话术库 + 账号 IP 模板 |

### 3. 问诊与调研

| 能力 | 什么时候用 | 产出 |
|---|---|---|
| `siyu-wenzhen` | 转化 / 留存 / 加微等具体问题 | 先判断问题成不成立，再给马甲会怎么做 |
| `siyu-market-research` | 厂商选型、竞品、报价、市场地图 | 带核验状态、日期与来源链接的证据快照 |

### 4. 全盘诊断（低频）

| 能力 | 什么时候用 | 产出 |
|---|---|---|
| `siyu-onboard` | 整盘怎么搭、战略级私域评审 | 四位专家分头看、团长拍板后的搭建清单 |
| 方法库（随诊断调用） | IP / 促活 / 漏斗 / 危机 / 合规深挖 | `trust-asset` · `content-as-product` · `reactivation` · `ops-as-ad-funnel` · `conversion-caliber` · `crisis-response` · `wechat-compliance-redlines` |

### 5. 客户档案

| 能力 | 什么时候用 | 产出 |
|---|---|---|
| `/siyu-save` | 把结论留下 | 写入本地客户档案 |
| `/siyu-restore` | 接着上次聊 | 拉出最近档案并续跑 |
| `/siyu-report` | 打包给老板或客户 | 合并多份存档 + 合规扫描报告 |

WorkBuddy / CodeBuddy 一次安装 = **17 个能力 + 4 位专家 Agent + 编排命令**。ClawHub / SkillHub 是同一份自包含入口包：子能力在包内路由，不拆成一堆商店条目。

## 30 秒上手

```text
/siyu
```

也可以直接说处境，不用先记 skill 名：

```text
我给门店群发了三轮活动，打开率还是很低，下一步该先改文案还是改群机制？
```

```text
帮我写下周朋友圈，主推周末双人套餐，受众是附近上班族。
```

```text
对比几家餐饮 SCRM，我要看清哪个还在售、大概什么价、有没有坑。
```

## 安装

### WorkBuddy / CodeBuddy（推荐）

只装一个插件，完整专家团一次到位：

```bash
/plugin marketplace add maojiebc/majia-siyu-team
/plugin install majia-siyu@majia-siyu
```

清单见 [`.codebuddy-plugin/plugin.json`](.codebuddy-plugin/plugin.json)。

### ClawHub / SkillHub（自包含单入口）

```bash
clawhub install majia-siyu
skillhub install siyu
```

两个商店都只保留一个条目：ClawHub slug 为 `majia-siyu`；SkillHub 为保留历史下载量 / 收藏 / 版本记录，继续用历史安装名 `siyu`。**对外标题一律是「私域专家团 · 马甲实战版」**（H1 / displayName），不要把 `siyu` 或 `majia-siyu` 当成卡片标题。代码入口、WorkBuddy 插件与 GitHub 真源统一为 `majia-siyu`。

### skills.sh / Claude Code

```bash
npx -y skills add maojiebc/majia-siyu-team -g --all
claude plugin marketplace add maojiebc/majia-siyu-team
```

Claude Code 安装单元见 [`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json)。发布包由 `python3 tools/build_skillhub_bundle.py` 从模块真源生成到 `skillhub/majia-siyu/`，保证 GitHub / ClawHub / SkillHub 对应同一 commit。

## 方法论引擎：三句话

- **私域即公关** —— 私域是关系 / 口碑 / 信任场，不是收割场  
- **内容即产品** —— 每条内容都要有钩子、有承接、可复用  
- **运营即广告** —— 每个运营动作本身就是广告，自带传播与转化  

## 开发与验证

```bash
make check          # 测试、技能结构、链接、分发包、版本与措辞
make compliance FILE=文案.md
python3 tools/ab_eval.py --help   # 装和不装的盲评
```

能力真源在 `plugins/`（技能）和 `knowledge/`（方法、行业册、案例）。`skillhub/majia-siyu/` 由 `tools/build_skillhub_bundle.py` 生成，不手改。`src/siyu_team/` 只剩三个文案检查脚本共用的合规扫描器：命中封号红线或广告法绝对化用词就拦下，不交付。

## 📋 版本记录

- **v2.0.0**（2026-10-22）移除未运行的 Python 运行时，保留 17 个 Markdown 技能与合规检查，加入经本人审阅的真实案例及盲评记录。旧 Python 命令行入口停止提供，改用 Markdown 技能。
- **v1.8.1**（2026-10-20）文案先交成品，补充跨场景完整示范与实用构图，检查留在后台，保留真实业务条件。
- **v1.8.0**（2026-10-20）同一活动的朋友圈、群发与私聊按需接力，保留前置条件、已完成稿件和整体核对；小幅补充文案与配图方法，完整素材分析留给独立收费项目。
- **v1.7.0**（2026-10-19）选型核验履约风险与平台覆盖；49条有条件知识；朋友圈、私聊、群发、欢迎与图文设计方法进入执行技能。原始私有素材不随包分发，H1/H2/H3未验证。
- **v1.6.0**（2026-10-12）Q4 至春节模板、模型出活自测与内容修正、只读档案复用；修复社区假更新与旧包提示。H1/H2/H3 未验证。
- **v1.5.0**（2026-09-14）门店会员执行知识与场景检索；41 条严格知识随包分发；补齐六场景安装验证，更新发布和使用说明。
- **v1.4.3** — WorkBuddy 专家团适配、自包含 ZIP 和平台契约检查。

完整历史见 [CHANGELOG](https://github.com/maojiebc/majia-siyu-team/blob/main/CHANGELOG.md)。

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

## License

MIT © 2026 马甲 (maojiebc)。方法论框架与骨架开源；真实操盘 SOP 属作者私有，不在本仓。
