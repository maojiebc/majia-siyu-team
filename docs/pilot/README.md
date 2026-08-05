# Knowledge Pilot Validation v1.2.1

这个目录只定义可复现的离线验证，不声称知识已经改善答案，也不声称贡献模式或审核成本已经验证。仓库中只有 30 个 Golden Tasks 和 24 条合成 fixture Atom，没有真实私有原子、模型答案或人类评分。

## 范围

- H1：与基线相比，条件性行业知识是否改善答案。
- H2：同行是否愿意用亲历案例交换案例卡和完整脱敏知识包。
- H3：人工提炼、脱敏、确认和审批是否能持续运行。

v1.2.1 不包含 Runtime 检索或注入、KnowledgeBundle、贡献网关、飞书 API、模型 API、自动批准或自动 PR。

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
  --seed 20260805

# 人工用同一模型/参数在独立新对话中生成两版答案，替换 Prompt 文件
siyu-pilot blind --run ~/.siyu-team/pilot/runs/run-001
siyu-pilot score \
  --run ~/.siyu-team/pilot/runs/run-001 \
  --ratings reviewer-a.csv reviewer-b.csv reviewer-c.csv \
  --output docs/pilot/results/knowledge-value-run-001.md

siyu-pilot editorial-report \
  --input phase0-editorial.csv \
  --output docs/pilot/results/editorial-throughput.md
```

`prepare` 禁止把含私有 Atom 的 Prompt 包写入 Git 仓库。试验目录为 `0700`，Prompt、manifest 和盲测真值文件为 `0600`。

## Dry Run 边界

5 题、1 评审的 Dry Run 只验证“准备 → 替换答案 → 盲化 → 评分 → 报告”工具链。少于 30 题或 3 名评审时，工具强制输出 `not_evaluated`，不得宣称 H1 Pass。
