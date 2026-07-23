我已读完所有要求的真文件。下面是完整的 teardown。

---

# qiaomu-llm-mcp 深拆：主持人模式 + MCP + 多角色讨论 + 模型路由

来源仓库：`qiaomu-llm-mcp`，作者向阳乔木（joeseesun）。下面所有结论都标了`文件名:行号`，抓不到的地方我会明说。

## 0. 整体架构（一句话）

一个本地 MCP 网关：把多个 LLM Provider + 密钥 + 路由规则 + 多模型讨论统一成一组 `qllm_*` 工具。`server.py` 是工具门面，`registry.py` 管 Provider/密钥，`providers.py` 管 HTTP 适配（OpenAI/Anthropic 双协议），`routing.py` 是规则路由，`heavy.py` 是 HeavySkill 多视角讨论的 prompt 工厂 + 报告渲染，`claude_code.py` 是本机 Claude Code CLI 包装。注意一个关键事实：**核心是「prompt 编排 + 调度」，没有任何真正的 multi-agent 框架**，每个"角色"就是一次独立的 `chat_completion` 调用。

---

## 1. HeavySkill / 主持人模式到底怎么跑

### 1.1 数据流（server.py 的 `qllm_heavy_discuss`，`server.py:579-754`）

整条链路：

1. **规整视角**：`normalize_perspectives(params.mode, params.perspectives, params.k)`（`server.py:591`）。取 K 个视角，缺省用 `heavy.py` 里的两套默认表。
2. **决定每个视角用谁跑**：`_heavy_provider_cycle(...)`（`server.py:594-600` 调用，定义在 `server.py:487-500`）。没指定 `providers` 时，用 `rank_providers` 排名取前 N 个 provider id 循环分配。
3. **并行拉起角色**：`call_perspective` 内嵌函数（`server.py:602-647`），用 `asyncio.gather` 同时跑所有视角（`server.py:649-651`）。每个角色：
   - 算字母标签 `letter_for(index)`（A/B/C…，`heavy.py:61-65`）。
   - provider 选择优先级：`perspective.get("provider") or provider_cycle[index % len(...)]`（`server.py:604`）——即**视角可自带 provider/model，否则走轮转**。
   - 用 `build_perspective_prompt` 造孤立 prompt（`server.py:605-612`），然后 `_run_chat` 实际调用模型。
4. **过滤失败**：只保留 `status=="ok"` 的 trace（`server.py:652`），全失败直接报错返回（`server.py:653-660`）。
5. **去位置偏差洗牌**：`stable_shuffle_traces(params.question, successful_traces)`（`server.py:662`）。
6. **造主持 prompt**：`build_host_prompt(...)`（`server.py:663-670`）。
7. **主持收口**：两种模式分叉（见 1.4）。

### 1.2 角色（视角）怎么被拉起讨论

**默认视角表是写死在 `heavy.py` 里的两套**，按 `mode` 切换：

讨论模式 `DEFAULT_DELIBERATION_PERSPECTIVES`（`heavy.py:14-35`）：实用主义者 / 怀疑者 / 用户体验视角 / 证据视角 / 教练视角。

验证模式 `DEFAULT_VERIFICATION_PERSPECTIVES`（`heavy.py:37-58`）：直接推理 / 第一性原理 / 反方质疑 / 边界条件 / 经验证据。

`normalize_perspectives`（`heavy.py:68-98`）：`source = supplied if supplied else defaults`（`heavy.py:75`），即**用户传了就用用户的，否则用默认**，再 `[:k]` 截断。每条记录可带 `provider`/`model` 覆盖（`heavy.py:84-87, 92-96`）——这是"每个角色绑不同模型"的关键。

每个角色的**孤立 prompt**由 `build_perspective_prompt`（`heavy.py:120-168`）生成，几条硬约束很关键（忠实引用）：
- `只用这个视角独立分析，不要提及其他分析者。`（`heavy.py:145`）—— 角色之间**互不可见**，是真正的独立采样，不是对话。
- `有立场，不要为了显得平衡而含糊。`（`heavy.py:146`）
- `不要输出隐藏思维链；请输出面向读者的推理摘要、判断依据和关键取舍。`（`heavy.py:147`）
- 强制输出结构（`heavy.py:155-167`）：`## {视角名}` / **切入角度** / 2-5 段 / **我的结论** / **最脆弱的前提** / **最有力的依据** / **参考来源**。

### 1.3 host（主持人）如何"不投票、不平均、评估推理质量、列共识与分歧、给判断+行动项"

全部落在 `build_host_prompt`（`heavy.py:171-245`）这一个函数里。核心指令逐字引用：

`heavy.py:204`：
> `你的任务不是投票，也不是平均它们的观点，而是评估推理质量，找出互相补足处，保留有价值的少数意见，最后给出一个清晰判断。`

这一句就是题面里"不投票不平均、评估推理质量、保留少数意见"的**原文出处**。

输入侧，每个角色的产出被包成 `<agent>` 块喂给主持（`heavy.py:185-195`），带 Label / Perspective / Provider / Model / Content。

输出结构由 `<output_rules>`（`heavy.py:212-244`）强制成五段：

1. `## 讨论之后，我们发现了什么`（`heavy.py:225-227`）——"不同视角真正达成了什么共识，哪里有分歧，为什么这个分歧重要" → **共识与分歧**。
2. `## 各个角度说了什么`（`heavy.py:229-231`）——逐视角点评贡献 + 指出它忽略了什么。
3. `## 我们的判断`（`heavy.py:233-235`）——"给出最清晰的最终答案……最后用一句容易记住的话收束" → **最终判断**。
4. `## 还值得想想`（`heavy.py:237-239`）——未解决但重要的问题。
5. `## 如果你要行动`（`heavy.py:241-243`）——"如果问题天然包含行动建议，给 1-3 条具体动作。否则省略本节。" → **行动项**。

还有反 AI 味约束（`heavy.py:213, 220`）：禁止 `confidence / Pass@K / weakest assumption` 等术语，禁止"综上所述/总而言之"。

### 1.4 主持的两种模式 + 多轮

模式分叉在 `server.py:672-691`：

- **`host_mode=="codex"`**（`server.py:672-679`）：**不自己跑主持**，返回 `status="needs_host"` + `host_prompt`，让外部 Codex（当前掌握工作区的主控）来综合，再回头调 `qllm_heavy_render` 落盘（`server.py:677` 的 message 明说）。这是"让最强的主控模型当主持人"的设计。
- **`host_mode=="model"`**（`server.py:680-691`）：调 `_run_model_host_rounds`，让某个指定 provider 直接收口。

**多轮**逻辑在 `_run_model_host_rounds`（`server.py:503-566`）：
- `rounds` 默认 1、上限 2（`schemas.py:168`，注释 `Max 2 by HeavySkill rule`）。
- 第 2 轮时，把第 1 轮主持综合**当成一个新的可审查输入** trace（letter=`H1`，`server.py:548-557`），再洗牌重造 host prompt（`server.py:558-565`）。
- 对应 `build_host_prompt` 里那句：`如果这是第 2 轮，请把上一轮主持综合也当作一个可审查的输入，而不是最终答案。`（`heavy.py:205`）。

收口产物落盘走 `write_heavy_report`（`heavy.py:474-530`）：写每个 trace 的 md、`deliberation.md`、合并 md（`render_report_markdown`，`heavy.py:258-294`）、自带样式的 HTML（`render_report_html`，`heavy.py:352-471`）。

**一个诚实标注**：repo 名叫 `qiaomu-llm-mcp`，但 host prompt 自称 `qiaomu-heavyskill 的讨论主持人`（`heavy.py:197`）/ `qiaomu-heavyskill`。"HeavySkill"是它致敬/复刻的方法名（多模型独立采样 + 单主持综合，类似 Pass@K + judge），仓库内**没有**对外部 HeavySkill 原始定义的引用文件，这套 prompt 就是它对该模式的本地实现。

---

## 2. 路由：规则路由，不是模型路由

`routing.py` 是**纯规则/关键词路由，全程不调模型**。

### 2.1 两张静态表

- `TASK_KEYWORDS`（`routing.py:9-15`）：5 类任务的中英文关键词。例：`coding` 命中 `code/代码/debug/bug/typescript/python/react/mcp`；`writing` 命中 `写/文章/公众号` 等。
- `ROUTE_PREFERENCES`（`routing.py:17-24`）：每类任务的 provider 偏好顺序。例：`coding` → `zai-glm` 优先；`review/writing/research` → `aigocode-anthropic` 优先；`fast` → `deepseek` 优先；兜底 `general`。

### 2.2 推断 + 打分

`infer_task_type`（`routing.py:27-35`）：显式传了非 auto 就直接用；否则把文本 lower 后扫关键词，命中即返回，全不中返回 `general`（`routing.py:35`）。**注意**：按 `TASK_KEYWORDS` dict 插入顺序遍历（`routing.py:32`），先命中先返回，所以多关键词混合时有顺序偏向。

`rank_providers`（`routing.py:38-100`）打分逻辑：
- 过滤：跳过 disabled（`routing.py:54`）；必须有 `chat` 或 `messages` 能力（`routing.py:56-58`）；`require_secret` 时必须密钥 present（`routing.py:59-61`）。
- 基础分 10（`routing.py:63`）。
- 在偏好表里：`boost = (len(preferred) - index) * 10`（`routing.py:66`）——排越前加越多。
- 硬编码加成：`coding + zai-glm` +25（`routing.py:69-71`，理由 `Coding Plan endpoint`）；`review + protocol==anthropic` +12（`routing.py:72-74`）；带 `tools` 能力 +3（`routing.py:75-77`）；有 `verified_at` +2（`routing.py:78-80`）。
- 按 score 降序排（`routing.py:99`）。

### 2.3 路由怎么被消费

- 独立工具 `qllm_route_task`（`server.py:293-326`）：只排名不花 token。
- `qllm_chat` 里 `_select_provider`（`server.py:80-97`）：没指定 provider 就取 `ranked[0]`。
- **HeavySkill 里也复用同一套路由**做 provider 轮转（`server.py:498`）。

所以题面问"规则路由还是模型路由"——**明确是规则/关键词路由**。唯一带"模型"味道的是 `qllm_compare`（`server.py:376-422`）多模型并行对比，但那是横向比较不是路由决策。

---

## 3. registry / providers：视角配置 与 模型密钥如何解耦

### 3.1 三层解耦

1. **角色=视角层**（prompt 文本）：在 `heavy.py` 默认表 或 调用时传 `perspectives`。视角只关心"名字 + description + 可选 provider/model 覆盖"（`schemas.py:144-152` 的 `HeavyPerspectiveInput`）。
2. **Provider 注册表层**（`registry.json`）：display_name / protocol / base_url / default_model / models / capabilities / secret_ref。
3. **密钥层**：注册表里只存 `secret_ref` 指针（`keychain:...` 或 `env:...`），真实 key 在 macOS Keychain 或环境变量。

换 prompt（视角）完全不碰代码、也不碰密钥；换模型只改 registry 的 `default_model`；换 key 只改 Keychain。这就是"换 prompt 不换代码"。

### 3.2 密钥永不外泄的机制（registry.py）

- `resolve_secret`（`registry.py:107-120`）：`keychain:` 走 `read_keychain_secret`（`security find-generic-password`，`registry.py:92-104`）；`env:` 读环境变量。
- `secret_status`（`registry.py:123-132`）：只返回 `present/missing`，**从不返回明文片段**。
- `provider_summary`（`registry.py:196-216`）只暴露非敏感字段，secret 只给状态。
- `redact_sensitive`（`registry.py:34-46`）对上游报错里的 `sk-/Bearer/AIza` 等做脱敏。

### 3.3 registry.example.json 真实结构（`examples/registry.example.json`）

顶层 `version` + `providers` map。每个 provider 的真实字段（以 `zai-glm` 为例，`registry.example.json:4-23`）：

```json
{
  "version": "1.0.0",
  "providers": {
    "zai-glm": {
      "display_name": "Z.ai GLM Coding Plan",
      "protocol": "openai",
      "base_url": "https://api.z.ai/api/coding/paas/v4",
      "append_v1": false,
      "auth_header": "bearer",
      "secret_ref": "keychain:qiaomu-llm/zai-glm",
      "default_model": "glm-5.2",
      "models": ["glm-5.2"],
      "capabilities": ["chat", "models", "coding", "reasoning"],
      "source": "https://docs.z.ai/devpack/overview",
      "notes": "Use the dedicated Coding endpoint for Z.ai Coding Plan."
    }
  }
}
```

示例里还有 `deepseek`（openai 协议、append_v1:true）、`anthropic`（`protocol:"anthropic"` + `auth_header:"x-api-key"`，`registry.example.json:42-59`）、`openai-compatible`（`secret_ref:"env:OPENAI_API_KEY"` + `"disabled":true`，`registry.example.json:60-78`）。

**关键解耦点**：`providers.py` 的 `chat_completion`（`providers.py:110-146`）只看 `protocol` 字段分流——`anthropic` 走 `/messages`（`providers.py:214-275`），其余走 OpenAI 的 `/chat/completions`（`providers.py:149-211`）。换一家供应商=注册表加一条，不改代码。

**诚实标注**：`routing.py` 的偏好表里出现了 `aigocode-openai`、`aigocode-anthropic`、`qmblog-siliconflow`（`routing.py:17-24`）这些 provider id，但 `registry.example.json` 里**只有** zai-glm/deepseek/anthropic/openai-compatible。说明作者本机真实 registry 里 provider 更多，示例文件做了精简。`.env.example`（仅 2 行，`QIAOMU_LLM_REGISTRY` + `QIAOMU_LLM_TIMEOUT`）也证实真实配置在 `~/.config/qiaomu-llm/registry.json`，不在仓库里。

---

## 4. MCP server 暴露的 tool（server.py）

全部用 `@mcp.tool` 注册在 FastMCP（`server.py:58`），共 **11 个**：

| 工具名 | 行号 | 作用 | 副作用标注 |
| --- | --- | --- | --- |
| `qllm_list_providers` | `server.py:165` | 列 provider + 密钥状态 | readOnly |
| `qllm_show_provider` | `server.py:207` | 单 provider 非敏感元数据 | readOnly |
| `qllm_list_models` | `server.py:245` | 本地配置或远程 `/models` | readOnly/openWorld |
| `qllm_route_task` | `server.py:293` | **不花 token** 排名选模型 | readOnly |
| `qllm_chat` | `server.py:339` | 调单个 provider | 非 readOnly |
| `qllm_compare` | `server.py:376` | 同问题并行比多 provider | 非 readOnly |
| `qllm_pipeline` | `server.py:435` | 串联多步（上一步输出喂下一步） | 非 readOnly |
| `qllm_heavy_discuss` | `server.py:579` | **多视角多模型讨论 + 主持收口** | 非 readOnly |
| `qllm_heavy_render` | `server.py:767` | 把 Codex 主持后的综合渲染成 md/HTML | 非 readOnly |
| `qllm_claude_code_capabilities` | `server.py:815` | 探测本机 Claude Code CLI 能力 | readOnly |
| `qllm_claude_code_models` | `server.py:869` | 列 Claude Code 模型别名/目录 | readOnly |
| `qllm_claude_code_run` | `server.py:917` | 非交互跑 Claude Code CLI | 非 readOnly |
| `qllm_claude_code_sessions` | `server.py:983` | 看本机 Claude Code session | readOnly |

（表里 11 行工具 + claude_code 系列实为 4 个，合计 **13 个 tool**。入口 `main()` 在 `server.py:1010-1013`，stdio 传输，默认 `QIAOMU_LLM_TIMEOUT=120`。）

`qllm_pipeline`（`server.py:435-484`）值得单独提：把上一步 `content` 拼进下一步 prompt（`server.py:450`），每步可独立指定 provider/model/task_type，天然支持"快速模型初稿 → 强模型审查 → 写作模型润色"。

---

## 5. 照搬到"私域专家团 + 团长收口"

这套架构对"四官讨论 + 团长主持"几乎是 1:1 可移植：**四官 = 四个 perspective**（每个可绑不同模型），**团长 = host**（建议用 `host_mode=codex` 让掌握私域上下文的主控当团长，或用 `host_mode=model` 指定一个强模型）。

### 5.1 角色（四官）配置表结构

直接复用 `HeavyPerspectiveInput` 的字段（`schemas.py:144-152`），传给 `qllm_heavy_discuss` 的 `perspectives`。每条结构：`name` / `description` / 可选 `provider` / 可选 `model`。

四官示例配置（可直接作为 `perspectives` 数组）：

```json
[
  {
    "name": "选品官",
    "description": "只盯供应链与利润结构：货能不能稳定供、毛利够不够撑投流和分佣、有没有售后雷。",
    "provider": "deepseek"
  },
  {
    "name": "流量官",
    "description": "只盯获客与转化路径：私域从哪来、加粉到成交的漏斗、内容钩子和承接话术。",
    "provider": "zai-glm"
  },
  {
    "name": "合规官",
    "description": "专找过度承诺、违禁词、虚假宣传和封号风险，是团里的怀疑者。",
    "provider": "anthropic"
  },
  {
    "name": "复购官",
    "description": "只盯长期留存：社群活跃、复购钩子、会员体系和口碑裂变，关心一年后还在不在。",
    "provider": "deepseek"
  }
]
```

调用（对应 `HeavyDiscussInput`，`schemas.py:155-181`）：

```json
{
  "params": {
    "question": "这个私域项目（XX 品类）值不值得团队入驻接盘？",
    "mode": "deliberation",
    "k": 4,
    "perspectives": [ /* 上面四官 */ ],
    "host_mode": "codex",
    "success_criteria": "给出明确的入驻/不入驻判断，附最大风险与第一步动作。",
    "constraints": "不编造平台政策和带货数据；不确定就说不确定。",
    "write_report": true,
    "write_html": true
  }
}
```

四官并行跑（`server.py:649-651`），互不可见独立出观点，再交团长。

### 5.2 可直接用的「团长收口」host prompt 草案

把它作为外部团长（Codex/主控）的指令；或如果走 `host_mode=model`，它就是 `build_host_prompt` 的"私域专家团特化版"，结构照搬 `heavy.py:196-245`、只改身份与收口结构：

```text
<task>
你是「私域专家团」的团长，负责对四官的独立评审拍板。
议题：{question}
入驻成功标准：{success_criteria}
硬约束：{constraints}

四官（选品官 / 流量官 / 合规官 / 复购官）已各自独立给出意见，互相不知道对方写了什么。
你的任务不是投票，也不是把四个意见平均，而是评估每位的推理质量，找出他们互相补足的地方，
保留有价值的少数意见（哪怕只有一个官反对），最后替团队给出一个能落地的判断。
如果某官的关键前提站不住，明确点出来，不要因为他职位在就采信。
</task>

<officers>
{把四官产出按 <officer>Label/角色/Provider/Content</officer> 块依次贴入}
</officers>

<output_rules>
用中文写给团队成员看，像内部拍板会，不像报告。短段落，重点加粗独立成段。
不要用"confidence""加权""综上所述"这类词。不确定的地方直说。

按这个结构输出：

## 四官吵到哪了
两三段：哪里四个人其实是一致的，哪个分歧最要命，为什么这个分歧决定要不要入驻。

## 逐官点评
每位官 3-5 句：他这次最有价值的判断是什么，又漏看了什么。

## 团长拍板
两到三句给最终答复：入驻 / 暂缓 / 不入驻，可以带条件，但不要躲在条件后面。最后一句让人记得住。

## 入驻前必须先解决的事
1-3 条还没解决、但不解决就别签的硬问题。

## 如果决定入驻，第一周做什么
1-3 条具体动作，落到谁、做什么、看什么指标。否则省略本节。
</output_rules>
```

这份草案与原 `build_host_prompt` 的"不投票不平均 / 评估推理质量 / 保留少数意见 / 给清晰判断 / 行动项"骨架完全对齐（`heavy.py:204` + `heavy.py:225-243`），只是把"聪明的普通读者"换成"团队成员"、把通用五段换成入驻决策五段。

### 5.3 移植时的三个落地建议（基于真实代码限制）

1. **K 与视角数上限**：`k` 范围 `2-5`（`schemas.py:163`），`perspectives` 数组 `max_length=6`（`schemas.py:162`）。四官没问题，想加"财务官/客服官"也还有余量。
2. **多轮收口**：`rounds` 最多 2（`schemas.py:168`）。要"团长二审"就设 `rounds:2`、`host_mode:model`，第一轮综合会作为 `H1` 输入二审（`server.py:548-557`）。
3. **路由表要改**：现成 `ROUTE_PREFERENCES`（`routing.py:17-24`）是为编码/写作场景调的，私域选品/流量/合规没有对应 task_type。要么给四官**显式绑 provider/model**（最稳，绕开路由，如上面配置），要么在 `routing.py` 加 `TASK_KEYWORDS`/`ROUTE_PREFERENCES` 的私域类目——这需要改代码，是唯一不能"纯配置"完成的点。

---

## 附：一句话给老板的总结

它不是什么 multi-agent 黑魔法——**本质是"独立采样 K 个带人设的 prompt + 一个不投票只评质量的主持 prompt + 一张关键词路由表 + 一个 keychain 密钥指针注册表"**，四块都是可配置文本，代码只负责并发调度和落盘。正因为这么薄，搬成"四官 + 团长"只需要换 `perspectives` 数组和 host prompt 文本，唯一要改代码的地方是想让规则路由认识"私域选品/流量/合规"这些新任务类型。

关键文件：
- `qiaomu-llm-mcp/src/qiaomu_llm_mcp/heavy.py`（视角表 + 角色/主持 prompt 工厂 + 报告渲染）
- `qiaomu-llm-mcp/src/qiaomu_llm_mcp/server.py`（13 个 MCP tool + heavy 编排）
- `qiaomu-llm-mcp/src/qiaomu_llm_mcp/routing.py`（规则路由）
- `qiaomu-llm-mcp/src/qiaomu_llm_mcp/registry.py` + `providers.py`（密钥解耦 + 双协议适配）
- `qiaomu-llm-mcp/examples/registry.example.json`（注册表真实结构）