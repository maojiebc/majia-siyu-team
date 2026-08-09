# CLAUDE.md — 私域专家团 · 给 AI 协作者的不变量

**唯一真源（source of truth）**：能力定义只在 `plugins/`（角色人设+方法论）和 `src/siyu_team/`（编排/收口/质量门/连接器）。多端派生分发（`tools/generate.py` → codex/cursor/opencode）目前**尚未启用**（脚本为禁用桩）；一旦启用，其产物即派生物、绝不手改。

**编排范式**：走 wshobson「单 orchestrator + 文件状态机」（范式 A），不碰需要实验开关的 agent-teams（范式 B）。团长链是顺序依赖 + 要人审，范式 A 更稳。

**收口范式**：走 qiaomu HeavySkill 主持人模式——四官各自独立采样、互不可见，团长（host）不投票不平均，只评推理质量、保留少数意见。合规官红线一票否决。

**质量门**：静态合规与质量评分分开。`siyu-eval compliance` 只报告按语境解释的合规命中；`siyu-eval judge` 仅在独立宿主逐维评分并回填完整来源后计算质量分。缺少 `JudgeReport` 时不得显示分数或徽章，分数也不自动批准案例或知识。`siyu-eval score` / `make eval` 只保留一个版本的 deprecated 合规别名。当前事实见 `docs/architecture-current.md`。

**护城河边界**：`knowledge/03-majia-sop/` 是马甲真实 SOP，私有，git-ignore，**绝不进公开库**。所有 `【待马甲填真实SOP】` 标记处由马甲本人注入。

**知识分层不变量**：高频案例内联 `SKILL.md`（≤8KB）→ 深度方法论进 skill 的 `references/` 或 `knowledge/00-methodology/` → 全量语料原子化进私有 `knowledge/03-majia-sop/atoms.jsonl`。公开层只保留 schema 与脱敏示例；各层之间用路径指针引用，不复制正文，防止漂移。

**脱敏红线**：commit message 与任何对外内容都脱敏，不写真实品牌/雇主/他人姓名。密钥走 keychain 指针（`keychain:siyu-team/<tool>`），真 token 不入库。

> 这个 repo 是怎么来的：看透两个 4-5 档标杆（wshobson/agents、qiaomu-llm-mcp）后把编排范式翻译成私域专家团骨架。完整拆解见 `docs/`。
