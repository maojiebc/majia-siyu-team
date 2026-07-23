I have everything I need — the rubrics, the scoring engine, the Monte Carlo reliability math, the anti-pattern penalty, the badge thresholds, and the actual CI gate (exit code 1 when `score < threshold`). Here is the teardown.

---

# wshobson/agents · plugin-eval 质量门深拆

> 所有引用基于本地真文件，路径前缀统一省略为 `plugin-eval/`，全路径根是 `wshobson-agents/plugins/plugin-eval/`。

## 0. 一句话定性

它不是"一个 LLM 给 agent 打个分"。它是**三层流水线 + 十维加权 + 反模式惩罚 + 蒙特卡洛可靠性 + Elo 对打 + CI 退出码硬卡**的工程化质量门。LLM-as-Judge 只是中间一层(占大头但不是全部),前面有纯 Python 静态分析兜底,后面有 N 次重复采样做统计置信区间。这套"可复现 + 有置信区间 + 能在 CI 里 exit 1"的设计,正是它区别于网上 prompt 合集的护城河。

---

## 1. 怎么评一个 agent/专家好不好

### 1.1 三层叠加(后层覆盖/混合前层)

来源 `skills/evaluation-methodology/SKILL.md:16-86`:

| 层 | 速度 | 是否调 LLM | 干什么 |
|---|---|---|---|
| Layer 1 静态分析 | <2s,确定性 | 否 | 6 个子检查直接读 SKILL.md(`SKILL.md:26-35`) |
| Layer 2 LLM Judge | 30-90s,非确定 | 是(默认 Sonnet) | 4 维锚定 rubric 打分(`SKILL.md:51-64`) |
| Layer 3 蒙特卡洛 | 5-20min,统计 | 是(N=50 次真跑) | 重复采样算激活率/一致性/失败率/token(`SKILL.md:66-86`) |

### 1.2 LLM-as-Judge 的 rubric 是什么

判官评 **4 个维度**,每维 0.0–1.0,五个锚点之间插值。权威锚定文档是 `skills/evaluation-methodology/references/rubrics.md`(512 行),代码里的精简版在 `src/plugin_eval/layers/judge.py`。

**维度 1 触发准确度(权重 0.25,最高)** — `rubrics.md:13-124`
- 测的是 description 能否让路由模型在"该触发"时触发、"不该触发"时不触发,概念上是 precision/recall 的 F1(`rubrics.md:24-25`)。
- 判官实现:`judge.py:209-227` 让模型**生成 10 条合成 prompt(5 该触发 / 5 不该触发)**,逐条预测会不会触发,返回 `precision/recall/f1`,F1 即维度分。
- 锚点举例(`rubrics.md:39-107`):0.0–0.19 描述等于技能名/纯被动语态 → 几乎不会被自动调用;0.80–1.00 必须含 "Use when…" 且列 **3+ 个具体可区分场景**,5 条该触发全中、5 条不该触发全不中。

**维度 2 编排适配度(权重 0.20)** — `rubrics.md:127-246`
- 测的是技能是不是"纯 worker"(收任务→执行→返回结构化输出),**不能**自己当 supervisor 去调度别的工具/agent。
- 70% 靠判官,因为"编排意图"静态分析抓不准(`rubrics.md:142-144`)。
- 代码里的锚定 rubric `judge.py:20-26`:

```
Score 0.0 — Skill acts as standalone agent; manages its own tool calls and sub-tasks.
Score 0.75 — Skill is mostly a worker; inputs/outputs documented, minimal coordination.
Score 1.0 — Pure worker role; composable, clear contracts, no orchestration logic.
```

- 负向信号(`rubrics.md:159-164`):出现 orchestrate / coordinate / dispatch / "if X call skill Y" 即扣分。

**维度 3 输出质量(权重 0.15)** — `rubrics.md:250-354`
- 判官选 3 个由简到繁的真实任务,**心算执行**技能指令,评 Correct / Complete / Useful 三项取平均(`rubrics.md:268-275`)。代码 `judge.py:275-289`。
- 这维 static 占 0%,纯经验(`rubrics.md:260-261`):depth 深时 60% 交给蒙特卡洛真跑。

**维度 4 范围校准(权重 0.12)** — `rubrics.md:358-474`
- 测技能"大小是否合适":太薄是 stub,太胖浪费 token、和兄弟技能重叠。代码 `judge.py:28-34`、`judge.py:294-318`。
- 还给了**按品类的行数基线表**(`rubrics.md:455-462`),比如 Reference 类 200–500 行、Workflow 类 150–300 行。

判官 agent 的系统提示和输出契约在 `agents/eval-judge.md:60-68`,强制返回无 markdown 围栏的 JSON:
```json
{"triggering_accuracy": {"score": 0.0, "reasoning": "..."}, ...}
```

### 1.3 模型分层(省钱)

`judge.py:40-49`:触发用 **haiku**,编排/输出/范围用 **sonnet**:
```python
_MODEL_MAP = {"haiku": "...", "sonnet": "claude-sonnet-4-6", "opus": "claude-opus-4-8"}
```
触发那种"生成 10 条 prompt"的机械活给便宜模型,需要语义判断的给贵模型。

### 1.4 蒙特卡洛/可靠性怎么算

核心在 `src/plugin_eval/layers/monte_carlo.py`。它把同一批 prompt **重复跑到 N 次**(`monte_carlo.py:128-132`,默认 50,thorough 时 100,见 `engine.py:94-96`),每次记录一个 `SimResult`(激活/质量/token/是否报错,`monte_carlo.py:26-35`),然后算四组统计量(`monte_carlo.py:252-353`):

- **激活率** + Wilson 置信区间(`monte_carlo.py:266`,`stats.py:10`)
- **输出一致性** = 变异系数 CV + bootstrap CI(`monte_carlo.py:281-283`,`stats.py:34/83`)
- **失败率** = 报错占比 + Clopper-Pearson 精确 CI(`monte_carlo.py:303`,`stats.py:64`)
- **token 效率** = 中位数 + IQR + 离群点,归一化 `efficiency_norm = max(0, 1 − median/8000)`(`monte_carlo.py:329-334`)

Layer 3 合成分(`monte_carlo.py:147-153`):
```
mc_score = 0.40×激活率 + 0.30×(1−min(1,CV)) + 0.20×(1−失败率) + 0.10×token效率
```
**关键洞察**:把"好不好"拆成"稳不稳"——0.30 的权重直接给一致性(CV 越低越稳),0.20 给"不崩"。这就是"可靠性"的量化:不是单次跑得漂亮,而是跑 50 次都稳定。

判官之间也有**一致性度量**:`judges>1` 时报 Cohen's kappa(`stats.py:94`,`rubrics.md:480-494`),目标 kappa ≥ 0.70;低 kappa 指向描述有歧义。

### 1.5 十维合成 + Elo

最终分不是 4 维而是 **10 维加权**(`engine.py:22-33`,`SKILL.md:100-111`):触发 0.25 / 编排 0.20 / 输出 0.15 / 范围 0.12 / 渐进披露 0.10 / token 0.06 / 鲁棒 0.05 / 结构 0.03 / 代码模板 0.02 / 生态 0.02(和=1.0)。

每维再按**层混合权重**跨三层加权(`engine.py:36-47`),例如触发 = static 0.15 + judge 0.25 + mc 0.60;输出 = judge 0.40 + mc 0.60。缺层时**重归一化**(`engine.py:272-280`),保证跳过蒙特卡洛不会人为压低分。

合成公式(`engine.py:198-206`,`SKILL.md:95`):
```
composite = Σ(维度权重 × 该维混合分) × 100 × 反模式惩罚
```
certify 时再叠 **Elo 对打**:对 gold corpus 两两比,起始 1500、K=32、双向跑查位置偏差(`SKILL.md:266-289`)。

---

## 2. 质量门怎么卡:什么分算过,不过怎么办

### 2.1 硬门:CI exit code(这是真正的"门")

`src/plugin_eval/cli.py:91-96` —— 唯一真正会让流水线失败的地方:
```python
if (threshold is not None and result.composite is not None
        and result.composite.score < threshold):
    return 1
```
`cli.py:108-115`:`--threshold` 参数,低于阈值 `raise typer.Exit(code=1)`。SKILL.md 给的 CI 用法(`SKILL.md:327-328`):
```bash
plugin-eval score ./skill --depth quick --output json --threshold 70
# exits with code 1 if score < 70
```
路径不存在直接 exit 2(`cli.py:41-43`)。**没传 `--threshold` 就永远 exit 0**——门是"可选启用"的,不是默认拦截。

### 2.2 软门:徽章分级(发布建议)

`src/plugin_eval/models.py:116-134`,徽章同时要 composite 和 Elo 双达标:
```python
thresholds = [(PLATINUM,90,1600),(GOLD,80,1500),(SILVER,70,1400),(BRONZE,60,1300)]
```
含义(`SKILL.md:176-182`):**Platinum≥90 可进 gold corpus / Gold≥80 生产就绪 / Silver≥70 能用待改 / Bronze≥60 最低可行(尚不推荐给用户) / <60 不达标**。Elo 没算时跳过 Elo 条件(`models.py:132`),即标准深度下可只凭 composite 拿牌。

维度字母分(`engine.py:320-347`):≥90 A、≥80 B、≥70 C、≥60 D、<60 F。

### 2.3 反模式惩罚(乘法,会复利)

`src/plugin_eval/layers/static.py:30-32`:
```python
def anti_pattern_penalty(count: int) -> float:
    return max(0.5, 1.0 - 0.05 * count)
```
每多一个反模式扣 5%,地板 50%。五个反模式(`static.py:145-248`,`SKILL.md:194-261`):
- **OVER_CONSTRAINED**:MUST/ALWAYS/NEVER > 15 次(`static.py:27/149`)
- **EMPTY_DESCRIPTION**:描述 < 20 字符(`static.py:163`)
- **MISSING_TRIGGER**:描述缺触发短语(正则 `static.py:63-70`,匹配 "Use when/after/before/whenever"、"Use proactively"、"Trigger when"、"Auto-loads when")
- **BLOATED_SKILL**:>800 行且无 references/(`static.py:51/200`)
- **ORPHAN_REFERENCE / DEAD_CROSS_REF**:死链(`static.py:214-247`)

惩罚是**乘在最后**的,所以内容再好,5 个反模式就把分压到 75%(`SKILL.md:504-508`)。"不过怎么办"官方答案:**先修反模式 flag,再按维度权重从高到低改**(`SKILL.md:421-498`)——触发准确度权重 0.25、改个描述就行、每小时收益最高,所以"先修触发"。

### 2.4 深度=置信度标签

`models.py:17-24`:quick→Estimated / standard→Assessed / deep→Certified / thorough→Certified+。`certify` 命令(`commands/certify.md`)= deep 全三层 + Elo,15-20 分钟,"发布前跑"。**注意一个诚实的坑**:plugin 级(非 skill 级)评估只跑静态层,标签恒为 Estimated(`engine.py:149-151`、`cli.py:57-65`)——深层只对单个 skill 有效。

---

## 3. 私域专家团的质量门怎么做(可直接用的 rubric 草案)

把上面这套机制原样移植:**静态层(免费、确定性,卡硬伤)→ LLM 判官层(锚定 rubric 评方案质量)→ 蒙特卡洛层(同一诉求重复生成 N 次,测稳定性)→ 加权合成 + 反模式乘法惩罚 + 阈值 exit 1**。下面是把"评 skill 好不好"翻译成"评私域方案好不好"。

### 3.1 维度权重表(替换原十维)

| 维度 | 权重 | 测什么 | 主要靠哪层 |
|---|---|---|---|
| 转化口径严谨度 | 0.22 | 是否给了明确口径(GMV/件单价/复购率/UV→加微→成交漏斗每一跳),分母/时间窗是否写清,有没有把"累计注册"伪装成"月活" | judge 0.6 / static 0.4 |
| 合规安全 | 0.20 | 是否触碰微信封号红线(诱导分享/外挂/批量加好友)、广告法绝对化用词、个人信息收集是否有授权口径 | static 0.5 / judge 0.5 |
| 可落地性 | 0.18 | 一线运营/店长能否照着做,有没有依赖买不到的工具或不存在的人力 | judge 0.5 / mc 0.5 |
| SOP 完整度 | 0.15 | 是否覆盖 引流→承接→转化→复购→裂变 全链路,每环节有动作/话术/责任人/时间 | static 0.6 / judge 0.4 |
| ROI 可验证 | 0.10 | 有没有给可埋点的指标 + 验证周期 + 失败回滚条件 | judge 0.4 / mc 0.6 |
| 触发精准度 | 0.08 | 方案是否真对上了客户的行业/客单/阶段,不是通用模板套壳 | judge 0.7 / static 0.3 |
| 资源校准 | 0.04 | 篇幅和颗粒度匹配客户体量,小店别给 30 人中台方案 | judge 0.55 / static 0.3 / mc 0.15 |
| 风格一致 | 0.03 | 解释者口吻、不灌鸡汤金句、不炫资历(对应你 MEMORY 里的 register) | static 0.7 / judge 0.3 |

权重和 = 1.0。合成公式照搬 `engine.py:198-206`:`方案分 = Σ(权重×维度分) × 100 × 反模式惩罚`。

### 3.2 锚定 rubric 草案(给 LLM 判官,照 `rubrics.md` 五锚点格式)

**维度「转化口径严谨度」**(权重 0.22)
```
0.0–0.19 — 通篇"提升转化""做大私域",零口径、零分母、零时间窗。
0.20–0.39 — 提了转化率但口径含糊:不说分母是 UV 还是加微数,不说统计周期。
0.40–0.59 — 给了核心漏斗某一跳的口径,但 加微率/成交率/复购率 至少缺一个的定义。
0.60–0.79 — 漏斗每一跳都有明确口径(分子/分母/时间窗),仅个别指标边界模糊。
0.80–1.00 — 全漏斗口径闭环:UV→加微→首单→复购→裂变每跳都有定义、分母、周期,
            且区分了"累计"与"活跃/周期"口径,大数给了约束条件(对应 MEMORY 某连锁品牌口径教训)。
```

**维度「合规安全」**(权重 0.20)
```
0.0–0.19 — 包含明确封号动作(诱导分享话术/外挂群发/虚拟定位加人)或广告法绝对化用词。
0.20–0.39 — 无显性违规,但大量游走灰色地带(诱导性裂变、未授权收集手机号)且无风险提示。
0.40–0.59 — 主体合规,个别环节有风险但已标注"需法务确认"。
0.60–0.79 — 全程合规,裂变机制走官方允许路径,信息收集有授权口径,仅缺少应急话术。
0.80–1.00 — 合规闭环:每个拉新/裂变动作都标注微信规则依据,含封号应急预案 + 授权同意模板。
```

**维度「SOP 完整度」**(权重 0.15)
```
0.0–0.19 — 只有理念/方向,没有任何可执行步骤。
0.20–0.39 — 覆盖链路 1–2 环,其余环节缺失(如只讲引流不讲承接转化)。
0.40–0.59 — 五环全提及,但 动作/话术/责任人/时间 四要素普遍缺 2 项以上。
0.60–0.79 — 全链路覆盖,每环至少有动作+话术,责任人或时间偶有缺失。
0.80–1.00 — 引流→承接→转化→复购→裂变 五环闭环,每环动作/话术/责任人/触发时机/SLA 齐全,
            附首日 checklist,可直接交一线执行。
```

(可落地性、ROI 可验证、触发精准度、资源校准 同样按五锚点写,此处略——结构完全照搬 `rubrics.md` 的 0.0/0.2/0.4/0.6/0.8 五档。)

### 3.3 静态层反模式(免费、确定性,先卡硬伤)

照 `static.py:145-248` 的写法,纯关键词/正则,不调 LLM:

| Flag | 触发条件 | severity |
|---|---|---|
| `NO_CALIBRATION` | 全文出现"转化率/复购率"但无数字口径/分母 | 0.15 |
| `COMPLIANCE_RED` | 命中违禁词库(诱导分享/外挂/最/第一/100%/永久) | 0.20(最高) |
| `ABSOLUTE_CLAIM` | 广告法绝对化用词 | 0.10 |
| `NO_RESPONSIBLE_PARTY` | SOP 段落无"责任人/谁来做"字样 | 0.10 |
| `TEMPLATE_STUB` | 方案<某行数阈值且无客户行业专有名词(疑似通用模板套壳) | 0.10 |
| `NO_METRIC` | 全文无任何可埋点指标名 | 0.10 |

惩罚乘法照搬 `penalty = max(0.5, 1.0 − 0.05×count)`。`COMPLIANCE_RED` 建议**单独硬卡**(命中即 exit 1,不只扣分),因为合规是私域生死线。

### 3.4 蒙特卡洛(可靠性)怎么落到私域

原版是"同一 prompt 跑 50 次看稳不稳"。私域版:**同一客户诉求,让生成器产 N 份方案,测一致性**。照 `monte_carlo.py:147-153`:
```
可靠性分 = 0.40×命中率(N份里多少份真给了可执行SOP而非空话)
         + 0.30×(1−CV)(N份方案在"建议加微路径/复购周期"等关键决策上的一致性,越一致越可信)
         + 0.20×(1−崩溃率)(多少份漏掉合规/口径)
         + 0.10×篇幅效率(别动辄两万字)
```
配上 Wilson / Clopper-Pearson 置信区间(`stats.py`),就能对外说"这套方案在 50 次生成里 92% 命中可执行 SOP,95% CI [0.85, 0.96]"——这正是护城河:**有置信区间的承诺**,而不是一句"我们很专业"。

### 3.5 徽章 + CI 门(对外可交付的关键)

照 `models.py:116-134` + `cli.py:91-96`:

| 徽章 | 方案分 | 含义 |
|---|---|---|
| Platinum ≥90 | 标杆案例,可进案例库 | |
| Gold ≥80 | 可直接交付客户 | |
| Silver ≥70 | 内部复核后交付 | |
| Bronze ≥60 | 需返工 | |
| <60 | 不交付 | |

**入驻硬门**:`方案分 < 80 或命中 COMPLIANCE_RED → exit 1`,专家方案打回。这一条 exit-code 硬卡 + 反模式乘法惩罚 + 有置信区间的可靠性分,就是"对外可交付专家团"区别于"网上找的私域 prompt 合集"的全部技术差异——**合集只有一段文字,这套有可复现的分数、能在流程里自动拦截、能对客户给统计承诺**。

---

## 附:抓不到/诚实标注

- **`code_template_quality`(代码模板质量)和 `robustness`(鲁棒)这两个维度**:有权重(`engine.py:32-33`)和层混合配比(`engine.py:43/45`),但我在 `static.py` 里**没找到对应的 static 子检查实现**(`STATIC_TO_DIMENSION` 映射 `engine.py:50-57` 里没有这两个),judge.py 也**没有单独的 `robustness`/`code_template` 评估函数**——judge 只产 4 维(触发/编排/输出/范围,`judge.py:160-172`)。即 `robustness` 实际只能靠蒙特卡洛的 `1−p_fail` 喂(`engine.py:309-310`),`code_template_quality` 在标准/快速深度下大概率落入"unmeasured"分支(`engine.py:191-195`,负哨兵 −1.0 后被权重重归一化剔除)。**这是文档(SKILL.md 列了 10 维全套)与代码实现之间的一处缺口**,诚实标注。
- **Elo 模块**:`src/plugin_eval/elo.py` 存在但我未逐行读;`certify.md` 和 SKILL.md 描述了 Elo 流程(起始 1500/K=32/双向查位置偏差),我引用的是文档层(`SKILL.md:266-289`)而非 elo.py 源码行号。
- **`corpus.py`(gold corpus 加载)**、`reporter.py`(报告渲染)、`cli.py` 的 `compare`/`certify`/`init` 子命令完整实现:存在但本次未逐行读,不影响质量门主逻辑结论。