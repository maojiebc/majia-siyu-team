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
| `SIYU_MAINTAINER_IDS` | 维护者联系方式或 ID，逗号分隔；命中则记为 A 级 |
| `SIYU_LLM_API_KEY` | 可选。不设则整条管线不用模型 |
| `SIYU_INTAKE_MODE` | 可选。仓库变量或 Secret。`lenient`（默认，内测照单全收）/ `strict`（旧行为：未知类别、坏日期、PII 走需人工） |

本地也可设同名环境变量。没有 `LARK_APP_ID` 时 `tools/community_intake.py` 以 0 退出。盐缺失或过短则非 0 退出，不调飞书、不写文件。夹具试跑用 `--dry-run --from-json … --salt-for-tests <盐>`。

真实 Base 已建好：`LARK_BASE_APP_TOKEN=KUE9bdTm6aHAgWsWRcVcevF0nlg`，`LARK_TABLE_SUBMISSIONS=tblxZxGBtGhvos0b`，`LARK_TABLE_CONFIRMATIONS=tblclv6LhLPIKQP4`（GitHub Secrets 已写）。**你还要补 `LARK_APP_SECRET` 和 `SIYU_MAINTAINER_IDS`。** 表单字段以 `feishu-base-schema.md` v1.5.1 为准（15 个投稿字段，含对外显示名）。对不上的印证计入 `manifest.json` 的 `confirmations_unresolved`。每次 intake 会重渲 `knowledge/05-community/contributors.md`（公开署名墙，不含公司/哈希）。定级后按 `来源记录` 把已收录行镜像到独立公开 Base（`LARK_PUBLIC_BASE_TOKEN` / `LARK_PUBLIC_TABLE`）；跨 Base 不能靠关联，只能每日同步。镜像判断句/证据用脱敏后文本、对外显示名或「匿名同行」、等级和印证数；不镜像公司/品牌、联系方式、回礼。`撤销` 删公开行；`已拒`/`需人工` 不公开，若曾镜像则删除。未设公开 token 的 fork 会跳过并打 notice。`--dry-run` 只打印计划、不写公开表。

## Action 做什么

`.github/workflows/community-intake.yml`：每天 02:00 UTC + 手动触发。拉表 → 写 `knowledge/05-community/` → 同步 package data 和 SkillHub → `make check`（提交前必跑）。若 diff 只在社区语料、社区基线、package data、SkillHub 知识目录，就 rebase 后推 main（最多 3 次）；失败或 diff 越界则开 PR。

## 等级与种子

- 管线只重算 D↔C。手改的 A/B 下次运行保持原等级，并写入 `maintainer.jsonl`（B 和 A 同一文件）。飞书「状态」没有 B 档，回写仍用「A级」。
- `seeds.retail.jsonl` 进入去重池。社区投稿 Jaccard ≥ 0.8 命中种子时，记为该种子的印证（同 id 原地更新）。升 C 仍要 ≥2 家不同公司且 ≥2 个不同贡献者；升 C 后按等级进 `confirmed.jsonl`，种子文件不再保留该条。
- 零新增时不改已入库文件，也不刷新 `manifest.json` 的 `last_run`。

## 维护者升级 A/B

1. 编辑 JSONL 里的 `quality.evidence_grade` 为 `A` 或 `B`。
2. 把该行放到 `knowledge/05-community/maintainer.jsonl`（下次 intake 也会按等级归到这里）。
3. 跑 `python tools/community_intake.py --dry-run --from-json <记录> --salt-for-tests <盐>` 查看回礼，不写飞书。
4. 或等下一次 Action 打包。

不要改 `knowledge/04-atoms/growth-layers.approved.jsonl`。H2/H3 读 `knowledge/05-community/manifest.json` 的 `metrics`。

## 内测宽松与撤销

内测期默认 `lenient`：未知「这条属于」记成方法并打备注；发现时间解析不了就用创建时间；判断句/证据里的手机号邮箱等就地脱敏后收录。空判断句仍 `已拒`。原始 PII 永不进 `knowledge/`。等级规则（D/C/A、两家印证、A/B 粘性）两档一样。

要收紧：把仓库变量或 Secret `SIYU_INTAKE_MODE` 设为 `strict`，下次 Action 即按旧行为拦需人工。

想撤回一条：

1. 飞书「案例提交」把「状态」改成 `撤销`，下次管线会从 inbox/confirmed/maintainer/seeds 删掉该原子，写入 `knowledge/05-community/revoked.jsonl`，回礼改成「已撤销」，之后即使改投稿也不会再入库。
2. 飞书不可用时：`python tools/community_intake.py --revoke ka_xxxx [--reason "…"]`。
