# 私域专家团 · 马甲实战版

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/maojiebc/majia-siyu-team/blob/main/LICENSE)

> 中文私域运营工具箱。日常文案直接干活，结构问题升舱四官诊断。入口只有一个：`/siyu`。

![私域专家团 v0.4.1 框架全局：客户私域诉求→结构化任务→团长按行业/阶段路由→四官独立评审→团长收口→质量门](https://raw.githubusercontent.com/maojiebc/majia-siyu-team/main/docs/framework.png)

## 这个入口做什么

`/siyu` 是私域工具箱的统一入口，三种模式：新手教程、任务前路由、任务后导航。它读取你当前的处境，选一个最该做的能力直接执行，干完再按真实结论导航下一步。

v0.4.0 起，请求会先整理成结构化 Task，再由 Runtime 只选择当前一个 Skill；信息不足时先补问，结构问题才会升舱四官。

## 全套能力（从公开仓一键装）

- `siyu-pyq` 朋友圈文案 · `siyu-qunfa` 社群群发 · `siyu-huashu` 破冰话术 —— 各自**边写边合规**
- `siyu-wenzhen` 五层问诊 · `siyu-onboard` 四官诊断团 · `siyu-save`/`restore`/`report` 客户档案

```bash
clawhub install majia-siyu-team                       # 装本入口
npx -y skills add maojiebc/majia-siyu-team -g --all    # 装全套
```

完整说明、框架图与源码：**https://github.com/maojiebc/majia-siyu-team**

## 方法论：私域即公关 · 内容即产品 · 运营即广告

—— 马甲（@maojiebc）· 超级马甲，14 年用户运营实战沉淀。
