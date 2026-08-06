# 私域专家团 · 马甲实战版

[![Skill Version](https://img.shields.io/badge/skill-v1.2.8-0b5cad.svg)](https://github.com/maojiebc/majia-siyu-team/releases)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/maojiebc/majia-siyu-team/blob/main/LICENSE)
[![GitHub](https://img.shields.io/badge/GitHub-majia--siyu--team-171515.svg)](https://github.com/maojiebc/majia-siyu-team)

> **私域专家团 · 马甲实战版**
>
> 中文私域经营工具箱。日常文案直接出活，结构问题再升级做全套诊断。入口只有一个：`/siyu`。

私域经营动作全景图（统一入口 → 当前一步 → 执行 / 问诊 / 升级全盘诊断；动态事实先检索留证；知识 Pilot 仅离线验证）：

![majia-siyu v1.2.8 框架全局](https://raw.githubusercontent.com/maojiebc/majia-siyu-team/main/docs/framework.png)

完整框架 SVG 与源码说明见 [GitHub docs/framework.svg](https://github.com/maojiebc/majia-siyu-team/blob/main/docs/framework.svg)。

## 这个入口做什么

`/siyu` 是私域工具箱的统一入口，三种模式：

1. **新手教程** —— 第一次用，先讲清楚能干什么  
2. **任务前路由** —— 读你的真实处境，只选当前最该做的一个能力并直接执行  
3. **任务后导航** —— 干完按真实结论告诉你下一步  

经营动作归本入口；会员指标、SQL、数仓请用 `majia-huiyuan`。

## 一次安装拿到的能力

- **高频执行（边写边合规）**：`siyu-pyq` 朋友圈 · `siyu-qunfa` 群发 · `siyu-huashu` 破冰话术  
- **问诊与调研**：`siyu-wenzhen` 五层问诊 · `siyu-market-research` 厂商/竞品/报价实时留证  
- **全盘诊断**：`siyu-onboard` 四位专家分头看 + 方法库（信任资产 / 促活 / 从进店到再买 / 危机 / 合规）  
- **客户档案**：`siyu-save` / `siyu-restore` / `siyu-report`  
- **升级**：`siyu-update`（只同步官方项目，不碰本地客户档案）  

子能力在包内 `modules/` 路由，**不需要、也不应该**拆成多个商店条目分别安装。

## 安装

```bash
# ClawHub（slug = majia-siyu，展示名 = 私域专家团 · 马甲实战版）
clawhub install majia-siyu

# SkillHub（历史条目 slug = siyu，展示名必须是 私域专家团 · 马甲实战版）
skillhub install siyu

# WorkBuddy / CodeBuddy：一个插件 = 完整专家团
/plugin marketplace add maojiebc/majia-siyu-team
/plugin install majia-siyu@majia-siyu
```

> **身份对照（防标题漂成 slug）**  
> - 安装 / 目录 / frontmatter `name:` → `majia-siyu`（代码身份）  
> - SkillHub 历史商店条目 → slug `siyu`（保留下载量与版本历史）  
> - 对外卡片标题 / H1 / `displayName` → **私域专家团 · 马甲实战版**  
> 三者不要混用：`siyu` 只是历史安装名，不是标题。

完整说明、角色导航、开发验证与源码：**https://github.com/maojiebc/majia-siyu-team**

## 同行知识共建（邀请制）

[填写真实案例采集卡](https://supermjbc.feishu.cn/share/base/form/shrcnLsRQgaQJilUGNg6BjBXflg)（约 3–5 分钟）。提交只进人工审核队列，不会直接注入 Skill；只有脱敏、批准并进入版本化发布批次的知识才可用于正式检索。

## 📋 版本记录

- **v1.2.8** — 增长 L0/L1 接入路由（无业态只 L0）。
- **v1.2.5** — 与 1.2.4 相同的用增方法映射；SkillHub 渠道对齐（1.2.4 槽位异常）。  
- **v1.2.4** — 公开「用增方法映射·餐饮零售」16 条增长 Know-how；问诊/漏斗/促活可挂口径；不自动灌进后台。  
- **v1.2.3** — 修复 SkillHub 详情页标题：发布临时包对齐 name=slug，主标题显示「私域专家团 · 马甲实战版」。功能不变。  
- **v1.2.2** — 公开首页与包页全面重梳；H1 / displayName 固定为「私域专家团 · 马甲实战版」，避免被商店短名盖住标题。  
- **v1.2.1** — 离线 Knowledge Pilot 盲测、30 Golden Tasks、审核吞吐报表。  
- **v1.2.0** — `KnowledgeAtomV2` 与贡献安全层；飞书 Phase 0。  
- **v1.1.0** — 动态外部事实硬门 + `siyu-market-research`。  

完整变更见 [GitHub Releases](https://github.com/maojiebc/majia-siyu-team/releases)。

## 方法论：私域即公关 · 内容即产品 · 运营即广告

## 👤 作者 / 联系

**马甲（@maojiebc）** · 超级马甲

| 渠道 | 链接 |
|---|---|
| 📧 Email | [m9224@163.com](mailto:m9224@163.com) |
| 🐙 GitHub | [github.com/maojiebc](https://github.com/maojiebc) |
| 🪝 ClawHub | [clawhub.ai/p/maojiebc](https://clawhub.ai/p/maojiebc) |
| 🐦 X | [@maojiebc](https://x.com/maojiebc) |
| 📕 小红书 | [超级马甲](https://xhslink.com/m/4fQMJeHHWKC) |
| 📰 微信公众号 | [超级马甲](https://mp.weixin.qq.com/mp/profile_ext?action=home&__biz=MzY5NzIzODk2NA==#wechat_redirect) |

> 这份 skill 是 14 年用户运营 + 数据中台 + BI 工程实战沉淀出来的，问题/合作随时聊。
