# Knowledge Pilot Validation

这个目录只定义可复现的离线验证。当前仓库没有真实模型答案、同行评分或审核运行数据，因此 H1/H2/H3 均为 **Not Evaluated**。合成夹具通过只代表工具可运行，不代表知识已证明有效、贡献动力或审核吞吐已成立。

## 范围

- H1：与基线相比，条件性行业知识是否改善答案。
- H2：同行是否愿意用亲历案例交换案例卡和完整脱敏知识包。
- H3：人工提炼、脱敏、确认和审批是否能持续运行。

Pilot 不包含模型 API、飞书 API、自动批准、自动提交或自动写 Pass。

## H1 分析单位

主分析以任务为独立样本：

1. 每个任务先聚合评审结果；只有超过半数评审选知识版或基线版时，才记为该任务 Win 或 Loss，否则记 Tie。
2. 任务级非平局胜率和 Wilson 95% 区间的样本量最多为 30，不是 90 条「评审×任务」记录。
3. 维度差的不确定性使用确定性 task-cluster bootstrap；同一任务内的多个评审不会被当作独立抽样单位。
4. 平局同时报告「排除平局」、「Tie=0.5」、「全算 Loss」和「全算 Win」四种敏感性口径。
5. 评分级胜率作为次要描述，不进入 H1 门槛。报告同时给出简单一致率和 Fleiss' kappa，但不伪造未预注册的通过阈值。

无依据精确数值不再用主观的 `unsupported_claim_control` 维度代替。每名评审必须分别填写：

```text
left_unsupported_precise_claims
right_unsupported_precise_claims
```

它们是左、右答案中无依据精确数值的非负计数。一个任务中，超过半数评审标记计数大于 0，才记为该版答案「出现」；H1 门槛比较任务级出现率。平均计数仍会报告，但不替代出现率。

「至少 70% 的胜出评价能指出具体改善」按 knowledge-win 评分记录计算，不用任务级代理值替代。

## 生产装配一致性

Pilot 和生产 Runtime 共用 `KnowledgeAssembler`。`task-atom-map.json` 只是预先登记的期望选择夹具，不直接决定知识版 Prompt 注入哪些 Atom。manifest 会同时记录实际选择和期望选择，便于发现生产装配偏差。

## 完整运行配置

30 题正式运行必须在 `prepare` 时填写：

- 模型名、宿主、温度、最大输出；
- 其他模型参数 `model_config`；
- 完整 Git commit；
- 生成时间和随机 seed。

工具自动记录 task hash、corpus hash、prompt template hash；`blind` 会冻结源答案与实际盲测对的逐题 SHA-256，`score` 时逐项复核并记录答案整体 hash。盲化后任一答案或盲测对变化都会拒绝评分并要求重新运行 `blind`。缺少任意必填配置、答案、精确数值计数、30 题或 3 名评审时，均不得进入 `evaluated`。

## 命令

```bash
# 只校验仓库合成 fixture
siyu-pilot validate --fixtures

# 真实 Atom 只存本机用户目录，文件必须 0600
siyu-pilot validate \
  --tasks tests/fixtures/pilot/golden-tasks.jsonl \
  --atoms ~/.siyu-team/knowledge/approved/expert.atoms.jsonl \
  --mapping ~/.siyu-team/pilot/task-atom-map.json

siyu-pilot prepare \
  --tasks tests/fixtures/pilot/golden-tasks.jsonl \
  --atoms ~/.siyu-team/knowledge/approved/expert.atoms.jsonl \
  --mapping ~/.siyu-team/pilot/task-atom-map.json \
  --output ~/.siyu-team/pilot/runs/run-001 \
  --seed 20260805 \
  --model-name model-version \
  --host host-and-version \
  --temperature 0 \
  --max-output 1600 \
  --commit-sha 0123456789abcdef0123456789abcdef01234567 \
  --model-config '{"top_p":1}'

# 人工用同一模型/参数在独立新对话中生成两版答案，替换 Prompt
siyu-pilot blind --run ~/.siyu-team/pilot/runs/run-001
siyu-pilot score \
  --run ~/.siyu-team/pilot/runs/run-001 \
  --ratings reviewer-a.csv reviewer-b.csv reviewer-c.csv \
  --output ~/.siyu-team/pilot/runs/run-001/results/h1.md

siyu-pilot editorial-report \
  --input phase0-editorial.csv \
  --output ~/.siyu-team/pilot/runs/run-001/results/editorial.md
```

`prepare` 禁止把含私有 Atom 的 Prompt 包写入 Git 仓库。试验目录为 `0700`，Prompt、manifest 和盲测真值文件为 `0600`。

## 状态边界

- 5 题 Dry Run 只能标记 `tooling_validated`；H1 结论仍是 `not_evaluated`。
- 仅 30 题、每主题 10 题、至少 3 名完整评审，且运行配置和精确数值字段齐备时，才能标记 `evaluated`。
- `evaluated` 之后才能按预注册门槛输出 `pass` 或 `fail`。
- 未填真实模型答案和人类评分时，结果文档必须继续写 **Not Evaluated**，不得用合成测试结果自动覆盖成 Pass。
