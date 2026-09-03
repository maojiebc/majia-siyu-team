# 社区语料审核说明（v1.5）

默认路径已经自动化。维护者日常不用点每条投稿。

## 自动路径（不要插手）

每日 02:00 UTC 的 GitHub Action 会：

1. 拉飞书 `案例提交` 和 `印证`。
2. 哈希公司名，扫隐私，去重，标平台规则风险。
3. 单源写 D，两家不同公司写 C，维护者 ID 写 A。
4. 直接提交到 `knowledge/05-community/`。H2/H3 看当天 `manifest.json` 的 `metrics`。

含手机号/证件/密钥/门店编号的投稿会停在飞书状态「需人工」，不进仓库。打开那一行删掉隐私后再等下一次拉取。

平台技巧和规则变化只打风险标签，并带 180 天有效期，不要因为「这是技巧」就拒收。

互相打架的判断句会写进 `lifecycle.contradicts`，不会自动判谁对。

## 唯一还要手做的事：A/B 升级

管线不会把社区稿升到 A/B。若你本人核实过、或有内部数据，可以：

1. 打开对应 JSONL（通常在 `inbox.jsonl` 或 `confirmed.jsonl`）。
2. 把 `quality.evidence_grade` 改成 `A` 或 `B`，必要时改 `reviewer`。
3. 把这一行剪到 `maintainer.jsonl`。
4. 本地跑 `python tools/community_intake.py --dry-run --from-json <当前记录>` 看回礼文案；或直接下次 Action 会按文件现状打包。

不要改 `knowledge/04-atoms/growth-layers.approved.jsonl`。那是 35 条严格正式集，和社区语料分开。

## 停止线

出现未处理的隐私投诉，先停 Action（workflow 里 disable），清数据后再开。不要「先入库以后再洗」。
