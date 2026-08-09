# v1.4.2 发布清单

本清单只用于人工发布复核。所有 GitHub、ClawHub、SkillHub 和远端 Git 操作都必须由发布人明确执行；自动化代理不得代为推送、打标签、创建 Release、上传或发布。

## 1. 离线发布门

- [ ] PR-01 至 PR-05 已合并，发布候选只包含 v1.4.2 稳定化范围。
- [ ] `ruff check src tests tools`、`mypy src/siyu_team`、`make check` 全部通过。
- [ ] `python tools/check_versions.py` 与 `python tools/check_consistency.py` 通过。
- [ ] `python tools/build_skillhub_bundle.py --check` 通过，SkillHub 包无坏链。
- [ ] 干净 wheel 安装后，`siyu-plan` 能运行并加载随包公开知识。
- [ ] H1、H2、H3 仍标为 **Not Evaluated**；发布说明不得声称知识飞轮或同行共建已经成立。

任一项失败就停止发布，继续保留 v1.4.1 作为可回滚版本。

## 2. 同一提交三项核对

以下含远端查询，只能由发布人在准备发布时人工运行。本仓库的开发或验证代理不得执行 `git ls-remote`。

```bash
LOCAL_COMMIT=$(git rev-parse HEAD)
WORKTREE_STATUS=$(git status --porcelain)
REMOTE_MAIN=$(git ls-remote origin main | awk '{print $1}')

test -z "$WORKTREE_STATUS"
test "$LOCAL_COMMIT" = "$REMOTE_MAIN"
```

- [ ] `git rev-parse HEAD` 得到发布候选 commit。
- [ ] `git status --porcelain` 为空，证明没有未提交或未跟踪文件混入产物。
- [ ] `git ls-remote origin main` 与本地 commit 完全相同。
- [ ] GitHub Release 的 `v1.4.2` tag 最终也指向同一 commit。

只有 rev-parse、porcelain、ls-remote 三项结果共同成立，才能进入线上步骤。

## 3. GitHub Release（人工）

- [ ] 先人工创建 GitHub Release `v1.4.2`，tag 指向上节核对过的 commit。
- [ ] Release 只描述稳定化、安装态与契约加固；H1/H2/H3 写 **Not Evaluated**。
- [ ] 发布后重新下载 Release 源码或产物，核对 VERSION、wheel 与 SkillHub bundle 都是 `1.4.2`。

GitHub Release 完成前，不发布 ClawHub 或 SkillHub。

## 4. ClawHub 入口指针包（人工、按需）

GitHub Release 完成后，人工检查现有 `majia-siyu` 条目的入口指针、版本和下载产物。只有条目仍指向旧 commit、旧 SemVer 或旧包内容时，才重发入口指针包；已经正确指向 v1.4.2 时不要为了“刷新”重复发布。

允许的发布范围只有仓内明确指定的单入口包 `./skillhub/majia-siyu`。仓内没有可证明当前 ClawHub 版本参数和 tag 参数拼法的契约，因此这里只保留不可直接执行的命令模板。发布人必须先查当时的官方 CLI 文档，填入 v1.4.2 参数和正好 10 个 tag 参数，再人工核对文件清单：

```bash
clawhub publish ./skillhub/majia-siyu \
  <按官方 CLI 填写的 v1.4.2 版本参数> \
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

- 只允许显式的 `clawhub publish <指定包>`；本次指定包只能是 `./skillhub/majia-siyu`。
- 绝不裸跑 `clawhub`，也绝不运行 `clawhub sync`、`clawhub sync --all` 或任何会扫描并批量上传本机目录的变体。
- 不发布 `plugins/`、仓库根目录、用户目录或自动发现出的其他包。
- 真正发布前由人工核对当前官方 CLI 文档并替换占位符；本清单不授权代理执行上述命令，也不把占位模板当作可运行命令。

## 5. SkillHub（人工）

- [ ] 从 GitHub Release 所用的同一 commit 运行 `python tools/build_skillhub_bundle.py --check`。
- [ ] 上传对象只取该 commit 中的 `skillhub/majia-siyu`，SemVer 必须是 `1.4.2`。
- [ ] 保留历史商店身份 `siyu`，不新建重复条目；展示名仍为“私域专家团 · 马甲实战版”。
- [ ] 上传后核对根 `SKILL.md`、所有 modules、route-contract、公开知识 manifest 和查询工具均来自同一 commit。

SkillHub 的 commit 与 SemVer 必须同时匹配 GitHub Release；任一不一致都停止发布。

## 6. 发布后验证与回滚

- [ ] 分别从 GitHub、ClawHub、SkillHub 做一次干净安装，运行入口、知识查询和一条静态合规回归。
- [ ] 核对 ClawHub 入口指针、SkillHub 历史条目和 GitHub Release 都显示 `1.4.2`。
- [ ] 保存人工发布记录：操作者、时间、commit、SemVer、产物校验值和异常。
- [ ] 任一安装态失败，立即停止继续分发；按平台人工撤回或回指 v1.4.1，并记录原因。

真实 Pilot 在发布后另行人工执行。只有 H1/H2/H3 达到预注册门槛，才讨论 v1.5.0。
