# 社区语料管线

每日把飞书投稿写进仓库。fork 没配 `LARK_APP_ID` 或 `SIYU_HASH_SALT`（至少 16 字符）会跳过，不会半配置跑。

## 需要的 GitHub Secrets

| Secret | 用途 |
|---|---|
| `LARK_APP_ID` | 飞书应用 ID |
| `LARK_APP_SECRET` | 飞书应用密钥 |
| `LARK_BASE_APP_TOKEN` | 多维表格 app_token |
| `LARK_TABLE_SUBMISSIONS` | 表 `案例提交` 的 table_id |
| `LARK_TABLE_CONFIRMATIONS` | 表 `印证` 的 table_id |
| `LARK_PUBLIC_BASE_TOKEN` | 公开看板 Base 的 app_token（独立 Base；未设则跳过镜像） |
| `LARK_PUBLIC_TABLE` | 公开表 `公开判断` 的 table_id |
| `SIYU_HASH_SALT` | 公司名哈希盐，至少 16 字符，不要和代码一起存 |
| `SIYU_MAINTAINER_IDS` | 维护者联系方式或 ID，逗号分隔；命中则机器建议 A（仍要人审才发布） |
| `SIYU_LLM_API_KEY` | 可选。不设则整条管线不用模型 |
| `SIYU_INTAKE_MODE` | 可选。仓库变量或 Secret。`lenient`（默认，内测照单全收）/ `strict`（旧行为：未知类别、坏日期、PII 走需人工） |

本地也可设同名环境变量。没有 `LARK_APP_ID` 时 `tools/community_intake.py` 以 0 退出。盐缺失或过短则非 0 退出，不调飞书、不写文件。夹具试跑用 `--dry-run --from-json … --salt-for-tests <盐>`。

真实 Base 已建好：`LARK_BASE_APP_TOKEN=KUE9bdTm6aHAgWsWRcVcevF0nlg`，`LARK_TABLE_SUBMISSIONS=tblxZxGBtGhvos0b`，`LARK_TABLE_CONFIRMATIONS=tblclv6LhLPIKQP4`（GitHub Secrets 已写）。**你还要补 `LARK_APP_SECRET` 和 `SIYU_MAINTAINER_IDS`。** 表单字段以 `feishu-base-schema.md` 为准（15 个投稿字段 + 评审列）。对不上的印证计入 `manifest.json` 的 `confirmations_unresolved`。每次 intake 会重渲 `knowledge/05-community/contributors.md`（公开署名墙：通过 N + 待审 M + 印证，不含公司/哈希）。按 `来源记录` 把待审/已通过行镜像到独立公开 Base（`LARK_PUBLIC_BASE_TOKEN` / `LARK_PUBLIC_TABLE`）；跨 Base 不能靠关联，只能每日同步。镜像判断句/证据用脱敏后文本、对外显示名或「匿名同行」、等级和印证数；不镜像公司/品牌、联系方式、回礼。`撤销`/`已驳回`/`已拒`/`需人工` 删公开行。未设公开 token 的 fork 会跳过并打 notice。`--dry-run` 只打印计划、不写公开表。评审员就是该 Base 的协作者，在飞书里填「评审结论 / 评审等级」，不用改仓库。

## Action 做什么

`.github/workflows/community-intake.yml`：每天 02:00 UTC + 手动触发。拉表 → 写 `knowledge/05-community/` → 同步 package data 和 SkillHub → `make check`（提交前必跑）。若 diff 只在社区语料、社区基线、package data、SkillHub 知识目录，就 rebase 后推 main（最多 3 次）；失败或 diff 越界则开 PR。

## 三档语料

| 文件 | 谁写 | 进 skill / 装配 |
|---|---|---|
| `pending.jsonl` | 所有过校验、尚未人审的投稿 | 否（仓库保留，不同步到 package / SkillHub） |
| `approved.jsonl` | 「评审结论=通过」 | 是 |
| `rejected.jsonl` | 「评审结论=驳回」 | 否（排除表，类似撤销） |
| `revoked.jsonl` | 「状态=撤销」或 `--revoke` | 否（排除表） |
| `seeds.retail.jsonl` | 种子 | 是 |

评审员 = 飞书 Base 协作者。机器写「建议等级 / 印证数 / 状态 / 回礼」，不改「评审结论 / 评审等级」。

- `seeds.retail.jsonl` 进入去重池。社区投稿 Jaccard ≥ 0.8 命中种子时，记为该种子的印证（同 id 原地更新）。建议升 C 仍要 ≥2 家不同公司；发布仍等人审。
- 零新增时不改已入库文件，也不刷新 `manifest.json` 的 `last_run`。

不要改 `knowledge/04-atoms/growth-layers.approved.jsonl`。H2/H3 读 `knowledge/05-community/manifest.json` 的 `metrics`：`pending_total` / `approved_total` / `rejected_total`；H3 是 `median_hours_submit_to_approve`（提交到评审通过的时延）。

## 内测宽松与撤销

内测期默认 `lenient`：未知「这条属于」记成方法并打备注；发现时间解析不了就用创建时间；判断句/证据里的手机号邮箱等就地脱敏后收录。空判断句仍 `已拒`。原始 PII 永不进 `knowledge/`。宽松只影响能不能进 `pending.jsonl`，不代替人审。

要收紧：把仓库变量或 Secret `SIYU_INTAKE_MODE` 设为 `strict`，下次 Action 即按旧行为拦需人工。

想撤回一条：

1. 飞书「案例提交」把「状态」改成 `撤销`，下次管线会从 pending/approved/seeds 删掉该原子，写入 `knowledge/05-community/revoked.jsonl`，回礼改成「已撤销」，之后即使改投稿也不会再入库。
2. 飞书不可用时：`python tools/community_intake.py --revoke ka_xxxx [--reason "…"]`。
