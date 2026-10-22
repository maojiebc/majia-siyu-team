# Siyu Expert Team · Majia Field Edition

[![Skill Version](https://img.shields.io/badge/skill-v2.1.0-0b5cad.svg)](https://github.com/maojiebc/majia-siyu-team/releases)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)
[![ClawHub](https://img.shields.io/badge/ClawHub-majia--siyu-6b4bd8.svg)](https://clawhub.ai/s/majia-siyu)
[![SkillHub](https://img.shields.io/badge/SkillHub-siyu-ef6c00.svg)](https://skillhub.cn)
[![skills.sh](https://img.shields.io/badge/skills.sh-install-24a148.svg)](https://skills.sh/maojiebc/majia-siyu-team)
[![Release](https://img.shields.io/github/v/release/maojiebc/majia-siyu-team?label=release&color=success)](https://github.com/maojiebc/majia-siyu-team/releases)

> **Siyu Expert Team · 马甲实战版**
>
> Majia's private-domain judgment, packaged for your AI. Daily copy ships directly; when a call is hard, the answer draws on things Majia actually did. One entry point: `/siyu`.

<p align="center">
  <img src="https://raw.githubusercontent.com/maojiebc/majia-siyu-team/main/assets/icon.png" alt="Siyu Expert Team icon" width="120">
</p>

---

**Where to go:**

| I want to… | Go to |
|---|---|
| Start for the first time | [Quick start](#quick-start) → type `/siyu` |
| Write Moments / broadcasts / welcome copy | [Capability map · execution](#2-high-frequency-execution) |
| Diagnose conversion or quiet groups | [Capability map · diagnosis](#3-diagnosis--research) |
| Read Majia's calls and the stories behind them | [Judgment list](knowledge/cases/00-判断清单.md) (Chinese) |
| Compare SCRM vendors or verify pricing | `siyu-market-research` |
| Design the whole private-domain system | owner guide or `siyu-onboard` |
| Resume last client thread / ship a report | `/siyu-save` · `/siyu-restore` · `/siyu-report` |
| Install for an AI agent | [Install](#install) |

Full Chinese manual: [README.md](./README.md).

## What it is

A generic AI can already write Moments posts and recite private-domain methods. What it lacks is someone who has actually been burned.

Majia built WeCom community operations for a coffee chain with several hundred stores: from paying per SMS to one million WeCom friends in three months, and 1,500+ pushes a year with almost no errors. He later consulted for restaurant owners. This package holds those stories in Chinese under [`knowledge/cases/`](knowledge/cases/00-判断清单.md): the situation, the call he made, what happened, and how to adapt it to your store. When your situation matches, the AI gives Majia's call first, then the story; when it does not, it answers normally.

Whether the package helps is measured one way only: the same questions answered with and without it, shuffled, anonymised and scored by a reviewer who did not take part. See [`evals/`](evals/README.md).

## Capability map

### 1. Entry

| Skill | When | Output |
|---|---|---|
| `/siyu` | Unknown next step | Tutorial, routing, post-task navigation |
| `/siyu-update` | Upgrade the toolbox | Sync official project; never touch local client files |

### 2. High-frequency execution

| Skill | When | Output |
|---|---|---|
| `/siyu-pyq` | Moments / content pool | Ready-to-post Moments copy |
| `/siyu-qunfa` | Group broadcast / campaigns | Scripts, CTA, mechanism notes |
| `/siyu-huashu` | Welcome / FAQ / ice-break | Scenario scripts + account IP templates |

### 3. Diagnosis & research

| Skill | When | Output |
|---|---|---|
| `siyu-wenzhen` | Concrete ops problems | 5-layer diagnosis or clear prescription |
| `siyu-market-research` | Vendor / competitor / pricing | Evidence snapshot with links and dates |
| `siyu-onboard` | Whole-system design | Four-officer playbook |
| Client archive trio | Save / resume / deliver | `/siyu-save` · `/siyu-restore` · `/siyu-report` |

One WorkBuddy / CodeBuddy install = **17 skills + 4 specialist agents + orchestrator**. ClawHub / SkillHub ship the same self-contained entry package; modules route internally and are not separate store listings.

## Quick start

```text
/siyu
```

Or just describe the situation:

```text
We pushed three campaign rounds to store groups and open rates are still low. Fix the copy first, or fix the group mechanism?
```

## Install

### WorkBuddy / CodeBuddy (recommended)

```bash
/plugin marketplace add maojiebc/majia-siyu-team
/plugin install majia-siyu@majia-siyu
```

### ClawHub / SkillHub

```bash
clawhub install majia-siyu
skillhub install siyu
```

ClawHub uses `majia-siyu`. SkillHub keeps the historical store identity `siyu` so downloads, stars, and version history stay attached. Code, GitHub source, and WorkBuddy plugin all use `majia-siyu`.

### skills.sh / Claude Code

```bash
npx -y skills add maojiebc/majia-siyu-team -g --all
claude plugin marketplace add maojiebc/majia-siyu-team
```

## Methodology

- **Private domain = PR** — relationship, reputation, trust; not a harvest field  
- **Content = product** — every piece needs a hook, a handoff, and reuse value  
- **Ops = ads** — every operating action should carry its own distribution and conversion  

## Version history

- **v2.1.0** (2026-10-22): Ask who is deciding and what the assigned task is before writing a plan. Decision-makers get the full trade-off; people handed a task get a plan inside that task, with Majia's own trade-off in a separate note for their eyes only, and plans going to a manager do not critique the campaign already run. Round-5 blind evaluation ties v2.0.0; both judges preferred the new version on the new question.
- **v2.0.0** (2026-10-22): Removed the unused Python runtime; retained 17 Markdown skills and compliance checks; added reviewed cases and blind evaluations. Python CLI users must migrate to the Markdown skills.
- **v1.8.1** (2026-10-20): Finished copy first, task-specific voices and layouts, original synthetic examples, and practical image briefs. Fact and risk checks stay in the background.
- **v1.8.0** (2026-10-20): Bounded handoffs for related campaign copy, prerequisite checks, completed drafts and final consistency review. Focused copy and image guidance; the complete material library stays in the separate paid project.
- **v1.7.0** (2026-10-19): Evidence-based vendor selection, platform coverage, 49 conditional knowledge atoms, and channel-specific copy and visual briefs. H1/H2/H3 remain Not Evaluated.
- **v1.6.0** (2026-10-12): Seasonal catering templates, prompt-only self-tests and content fixes, optional read-only client context; community date stability and clearer stale-bundle checks. H1/H2/H3 remain Not Evaluated.
- **v1.5.0** (2026-09-14): Store membership execution and scenario retrieval; 41 curated rules, with six scenarios checked in source, wheel and SkillHub packages.
- **v1.4.3**: WorkBuddy expert-team packaging and archive checks.

Full history: [CHANGELOG](https://github.com/maojiebc/majia-siyu-team/blob/main/CHANGELOG.md).

## 👤 Author / Contact

**Majia (@maojiebc)** · 超级马甲 (Super Majia)

If this skill helps you, find me on any of these channels — happy to chat about field experience, take feature requests, hear bug reports, or trade notes on user operations / data platforms / BI engineering work:

| Channel | Link |
|---|---|
| 📧 Email | [m9224@163.com](mailto:m9224@163.com) |
| 🐙 GitHub | [github.com/maojiebc](https://github.com/maojiebc) |
| 🪝 ClawHub | [clawhub.ai/p/maojiebc](https://clawhub.ai/p/maojiebc) |
| 🐦 X | [@maojiebc](https://x.com/maojiebc) |
| 📕 Xiaohongshu | [Super Majia](https://xhslink.com/m/4fQMJeHHWKC) |
| 📰 WeChat Official Account | [超级马甲](https://mp.weixin.qq.com/mp/profile_ext?action=home&__biz=MzY5NzIzODk2NA==#wechat_redirect) |

> Built from 14 years of user-operations work and hands-on data platform & BI engineering in production.

## License

MIT © 2026 Majia (maojiebc). The public repository contains the framework and methodology; private operating SOPs are excluded.
