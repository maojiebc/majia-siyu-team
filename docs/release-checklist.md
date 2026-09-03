# 发布清单

本清单只用于人工发布复核。所有 GitHub、ClawHub、SkillHub、WorkBuddy 和远端 Git 操作都必须由发布人明确执行；自动化代理不得代为推送、打标签、创建 Release、上传或发布。

版本号以仓库根目录 [`VERSION`](../VERSION) 为准。发布前用 `make bump VERSION=x.y.z`（或 `python tools/bump_version.py x.y.z --dry-run` 预览）统一 bump 所有声明面，再跑 `make check`。

## 1. 离线发布门

- [ ] 发布候选范围已合并，无意外 diff。
- [ ] `ruff check src tests tools`、`mypy src/siyu_team`、`make check` 全部通过。
- [ ] `python tools/check_versions.py` 与 `python tools/check_consistency.py` 通过。
- [ ] `python tools/build_skillhub_bundle.py --check` 与 `python tools/build_workbuddy_bundle.py --check` 通过。
- [ ] 干净 wheel 安装后，`siyu-plan` 能运行并加载随包公开知识。
- [ ] H1、H2、H3 指标从社区共建流水线日志读取，发布说明仍标 **Not Evaluated**（或当前流水线状态）；不得声称离线 Pilot 已给出 Pass/Fail。

任一项失败就停止发布，继续保留上一可回滚版本。

### 冻结组件（非发布门）

以下目录/模块自 v1.5 起**冻结**，保留供参考，**不进入** `make check` 发布门：

- Python Runtime：`src/siyu_team/pilot`、`src/siyu_team/eval`（及关联 CLI）
- Pilot 文档与协议：`docs/pilot/`

日常仍可 `make pilot` opt-in 校验合成夹具；Release 不依赖其通过。

## 2. 同一提交三项核对

以下含远端查询，只能由发布人在准备发布时人工运行。本仓库的开发或验证代理不得执行 `git ls-remote`。

```bash
LOCAL_COMMIT=$(git rev-parse HEAD)
WORKTREE_STATUS=$(git status --porcelain)
REMOTE_MAIN=$(git ls-remote origin main | awk '{print $1}')
RELEASE_VERSION=$(cat VERSION)

test -z "$WORKTREE_STATUS"
test "$LOCAL_COMMIT" = "$REMOTE_MAIN"
```

- [ ] `git rev-parse HEAD` 得到发布候选 commit。
- [ ] `git status --porcelain` 为空，证明没有未提交或未跟踪文件混入产物。
- [ ] `git ls-remote origin main` 与本地 commit 完全相同。
- [ ] GitHub Release 的 `v${RELEASE_VERSION}` tag 最终也指向同一 commit。

只有 rev-parse、porcelain、ls-remote 三项结果共同成立，才能进入线上步骤。

## 3. 发布渠道（按顺序）

### 3.1 GitHub Release / tag（main）

- [ ] 先人工创建 GitHub Release `v$(cat VERSION)`，tag 指向上节核对过的 **main** commit。
- [ ] Release 说明聚焦能力、安装态与契约；H1/H2/H3 写当前社区流水线状态，不引用离线 Pilot 为发布依据。
- [ ] 发布后重新下载 Release 源码或产物，核对 VERSION、wheel 与 bundle 均与 `VERSION` 一致。

GitHub Release 完成前，不发布下游渠道。

### 3.2 ClawHub 与 SkillHub

**ClawHub** — slug `majia-siyu`，发布对象只能是 `./skillhub/majia-siyu`：

```bash
clawhub publish ./skillhub/majia-siyu \
  <按官方 CLI 填写的 v$(cat VERSION) 版本参数> \
  <按官方 CLI 填写的 10 个 tag 参数>
```

10 个 tags 必须正好是：

1. `private-domain`
2. `wechat`
3. `operations`
4. `marketing`
5. `customer-retention`
6. `copywriting`
7. `compliance`
8. `business-diagnostics`
9. `knowledge-management`
10. `chinese`

安全硬门：

- 只允许显式 `clawhub publish ./skillhub/majia-siyu`；绝不裸跑 `clawhub`，也绝不运行 `clawhub sync`、`clawhub sync --all` 或任何会扫描并批量上传本机目录的变体。

**SkillHub** — 历史 slug `siyu`（skillId **127952**），**原地更新**，不新建重复条目；展示名仍为「私域专家团 · 马甲实战版」。

- [ ] 从 GitHub Release 同一 commit 运行 `python tools/build_skillhub_bundle.py --check`。
- [ ] 上传 `skillhub/majia-siyu`，SemVer 与 `VERSION` 一致。
- [ ] [`.codebuddy-plugin/*.json`](../.codebuddy-plugin/) 中的 `version` 字段已随 bump 更新（SkillHub / 安装器读取）。
- [ ] 上传后核对根 `SKILL.md`、modules、route-contract、公开知识 manifest 均来自同一 commit。

ClawHub 与 SkillHub 的 commit 与 SemVer 必须同时匹配 GitHub Release；任一不一致都停止发布。

### 3.3 WorkBuddy 开放平台

- [ ] 运行 `make workbuddy`，产物为 `dist/workbuddy/majia-siyu.zip`（目录已 gitignore，仅本地生成）。
- [ ] ZIP 内版本与 `VERSION` 一致；按 WorkBuddy 控制台人工上传与审核（仓库无自动发布 API）。

## 4. 仓内 manifest 说明

[`.claude-plugin/`](./../.claude-plugin/) 与 [`.codebuddy-plugin/`](./../.codebuddy-plugin/) 的 marketplace / plugin manifest **仍保留在仓库**（SkillHub、Claude Code、CodeBuddy 安装器读取），但 **Claude marketplace 与 CodeBuddy marketplace 已不再是独立发布步骤**；对外三渠道见 §3。

## 5. 发布后验证与回滚

- [ ] 分别从 GitHub、ClawHub、SkillHub、WorkBuddy（如已上架）做一次干净安装，运行入口、知识查询和一条静态合规回归。
- [ ] 核对各渠道显示版本与 `VERSION` 一致。
- [ ] 保存人工发布记录：操作者、时间、commit、SemVer、产物校验值和异常。
- [ ] 任一安装态失败，立即停止继续分发；按平台人工撤回或回指上一版本，并记录原因。
