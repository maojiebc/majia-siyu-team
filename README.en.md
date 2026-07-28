# Majia Siyu Expert Team · Majia Field Edition

[![Skill Version](https://img.shields.io/badge/skill-v1.0.1-0b5cad.svg)](https://github.com/maojiebc/majia-siyu-team/releases)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)

> **Siyu Expert Team · 马甲实战版**
>
> A Chinese private-domain (WeCom / 私域) operations toolbox. Install one plugin, enter through `/siyu`, and let the router select the right specialist.

<p align="center">
  <img src="assets/icon.png" alt="Siyu Expert Team icon" width="160">
</p>

![majia-siyu v1.0.1 architecture](https://raw.githubusercontent.com/maojiebc/majia-siyu-team/main/docs/framework.png)

## What it does

`/siyu` picks the single most useful capability for your current situation, runs it, then re-routes based on the real outcome — no fixed long chain.

- **Planning layer**: natural language becomes a validated `Task`, then a deterministic `RouteDecision`.
- **Execution layer**: `siyu-pyq` (Moments copy), `siyu-qunfa` (group broadcast), `siyu-huashu` (welcome & FAQ scripts) — each with **write-time compliance scanning** (blocks WeCom-ban triggers / absolute-claim ad-law words / share-bait).
- **Diagnostic layer**: structural issues escalate to four isolated officer contexts (PR / product / ads / compliance), host synthesis, and a quality gate.
- **Runtime foundation**: atomic state storage, redacted JSONL traces, layered knowledge, and connector boundaries.

Technical architecture: [`docs/runtime-v0.4.md`](docs/runtime-v0.4.md).

## Install

### WorkBuddy / CodeBuddy — one plugin

```bash
/plugin marketplace add maojiebc/majia-siyu-team
/plugin install majia-siyu@majia-siyu
```

The repository's `.codebuddy-plugin/` manifest exposes the full team as one plugin: 16 skills, four specialist agents, and one `/siyu` entry point.

### ClawHub / SkillHub — one bundled skill

The release bundle embeds the router and all internal modules, so users do not need to install specialists separately:

```bash
clawhub install majia-siyu
skillhub install siyu
```

SkillHub keeps the historical `siyu` entry so downloads, stars, and version history remain attached to the same store identity. The code, GitHub source, WorkBuddy plugin, and ClawHub slug use `majia-siyu`.

### Generic Skills CLI

```bash
npx -y skills add maojiebc/majia-siyu-team -g --all
```

## Version History

- **v1.0.1** — Corrected registry identity: ClawHub uses `majia-siyu`, while SkillHub updates the historical `siyu` entry and preserves its stats and version history.
- **v1.0.0** — Renamed the top-level Skill, WorkBuddy plugin, and ClawHub slug to `majia-siyu`; kept `/siyu` as the user command, corrected the canonical source, and added an explicit routing boundary with `majia-huiyuan`.
- **v0.8.0** — One-install distribution: WorkBuddy / CodeBuddy now sees the entire expert team as one plugin, while ClawHub and SkillHub receive a self-contained single-entry bundle. Added a unified minimalist icon and reproducible bundle builder.

Full history: [CHANGELOG.md](./CHANGELOG.md) or [GitHub Releases](https://github.com/maojiebc/majia-siyu-team/releases).

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

> Built from 14 years of user-operations work and hands-on data platform &amp; BI engineering in production.

## License

MIT © 2026 Majia (maojiebc). The public repository contains the framework and methodology; private operating SOPs are excluded.
