# 私域专家团 · 马甲实战版

[![Skill Version](https://img.shields.io/badge/skill-v1.0.1-0b5cad.svg)](https://github.com/maojiebc/majia-siyu-team/releases)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/maojiebc/majia-siyu-team/blob/main/LICENSE)

> 中文私域运营工具箱。日常文案直接干活，结构问题升舱四官诊断。入口只有一个：`/siyu`。

<img src="https://raw.githubusercontent.com/maojiebc/majia-siyu-team/main/assets/icon.png" alt="私域专家团高级极简图标" width="160">

![majia-siyu v1.0.1 框架全局：客户私域诉求→结构化任务→经营动作路由或四官评审→主持收口→质量门](https://raw.githubusercontent.com/maojiebc/majia-siyu-team/main/docs/framework.png)

## 这个入口做什么

`/siyu` 是私域工具箱的统一入口，三种模式：新手教程、任务前路由、任务后导航。它读取你当前的处境，选一个最该做的能力直接执行，干完再按真实结论导航下一步。

v0.4.0 起，请求会先整理成结构化 Task，再由 Runtime 只选择当前一个 Skill；信息不足时先补问，结构问题才会升舱四官。

## 全套能力（一个入口一次安装）

- `siyu-pyq` 朋友圈文案 · `siyu-qunfa` 社群群发 · `siyu-huashu` 破冰话术 —— 各自**边写边合规**
- `siyu-wenzhen` 五层问诊 · `siyu-onboard` 四官诊断团 · `siyu-save`/`restore`/`report` 客户档案

```bash
# WorkBuddy / CodeBuddy：安装一个插件，获得完整专家团
/plugin marketplace add maojiebc/majia-siyu-team
/plugin install majia-siyu@majia-siyu

# ClawHub / SkillHub：各自安装同一个自包含入口包
clawhub install majia-siyu
skillhub install siyu
```

完整说明、框架图与源码：**https://github.com/maojiebc/majia-siyu-team**

## 📋 版本记录

- **v1.0.1** — ClawHub 使用 `majia-siyu`；SkillHub 沿用原 `siyu` 条目并保留历史统计，修正安装命令。
- **v1.0.0** — 顶层 Skill、WorkBuddy 插件与 ClawHub slug 统一为 `majia-siyu`，保留 `/siyu` 命令，并与 majia-huiyuan 建立互斥触发边界。
- **v0.8.0** — WorkBuddy / CodeBuddy 单插件安装；ClawHub / SkillHub 单入口包内置全部模块。

完整变更见 [GitHub Releases](https://github.com/maojiebc/majia-siyu-team/releases)。

## 方法论：私域即公关 · 内容即产品 · 运营即广告

—— 马甲（@maojiebc）· 超级马甲，14 年用户运营实战沉淀。
