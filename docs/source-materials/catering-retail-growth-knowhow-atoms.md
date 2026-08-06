# 餐饮零售 · 用户增长 Know-how 知识原子（草案）

> **状态**：待过目 / 未写入 `atoms.jsonl` / 未进 Runtime  
> **行业专精**：连锁加盟餐饮为主，零售门店可复用；默认前提 = 企微私域 + 门店执行差异大  
> **素材来源**：大宁 Get 笔记「用增/用户运营」方法骨架 × 马甲既有餐饮私域公理/五步骨架/23 条基建原子 × Nowledge 方向（行业 Know-how 运行时注入）  
> **整理日期**：2026-08-06  
> **定位**：可检索的最小判断句（Know-how Atom），不是面试题库，不是客户专属 SOP  

**本文件路径**  
`/Users/majia/projects/majia-siyu-team/docs/source-materials/catering-retail-growth-knowhow-atoms.md`

**上游语料审阅稿**  
`/Users/majia/projects/majia-siyu-team/docs/source-materials/daning-user-growth-extract.md`

---

## 0. 为什么重写这一版

| 上一版问题 | 本版处理 |
|---|---|
| 互联网 App 用增话术（DAU/次留/投放） | 全部改写成 **进店→加微→首单→复购→沉默唤醒** |
| 面试包装/offer 话术混入 | **整段剔除** |
| 教学假数字当 benchmark | **不进 atom 正文**；指标只保留定义与观察窗 |
| 与现有 23 条基建原子重叠 | 只补 **增长层**，基建层只做交叉引用 |
| 直营强管控式隐含假设 | 显式写入 **加盟/门店执行边界**（长期记忆中的加盟执行规则） |

Nowledge 已对齐的项目方向：

1. 下一阶段优先「**真实行业 Know-how 可检索、可验证、可注入**」，而不是继续堆专家角色。  
2. 公开能力核心 + 私有知识叠加；本草案 `visibility=expert_private` 候选，过审后再决定是否降敏公开。  
3. Golden Tasks 三大主题（加微承接 / 活动增量 / 复购召回）应用本批 atom 可拉开「有知识 vs 无知识」的答题差。

---

## 1. 行业前提（写进每条 atom 的默认 scope）

```text
industry:        catering | retail_store
business_model:  franchise_chain（默认）| multi_store | single_store
channels:        wecom_friend, wecom_group, moments, instore, takeaway_pack, groupbuy
lifecycle:       cold | growth | mature   # 对齐 knowledge/02-industry/catering/stages.md
roles:           hq, branch, franchisee, store_staff
硬约束:
  - 98% 加盟场景下，不假设总部能强制门店执行
  - 标签必须能挂消费行为；纯企微手工标签价值有限（既有原子 2026Q3_020）
  - 合规前置：不诱导分享、不绝对化承诺、不未授权收集
  - 口径先于工具；会员数据问题可转 majia-huiyuan，不在本包内编 SQL
```

### 与私域五步骨架的挂接

| 五步（餐饮方法论） | 阶段 | 本包 atom 重点 |
|---|---|---|
| 造 IP → 做链接 | cold | 入口人群定义、加微漏斗、渠道 CAC |
| 促活 → 分层 | growth | 来源分群、漏斗找断点、活跃/沉默定义 |
| 复购 → 规模化 | mature | 召回、主爆品、结果物裂变（合规）、LTV |

### 与既有 23 条原子的边界

- **已有且不再重复**：企微四件套、先加好友再进群、老客迁移先引后弃、企微成本地板、认证命名、SCRM 选型阶梯、消费行为标签原则。  
- **本包新增**：增长决策与漏斗优化层（拉谁、测哪条渠、断在哪一跳、怎么分层促转化/召回）。

---

## 2. 餐饮零售指标字典（Atom 共用，禁止混用）

> 所有率类指标必须写清：**分子 / 分母 / 时间窗**。  
> 大数默认是累计量；活跃与转化是周期量。

| 指标 | 餐饮零售定义（默认） | 常见错用 |
|---|---|---|
| 有效加微 | 通过好友且未立即删除/拉黑（建议观察 24h） | 把扫码次数当加微 |
| 加微率 | 有效加微 ÷ 触点曝光（或进店人次）÷ 同日 | 分母用累计会员 |
| 入群率 | 入群数 ÷ 有效加微 ÷ 7 日 | 把群人数当好友数 |
| 首单转化 | 加微后 T 日内有消费人数 ÷ 有效加微 | 把领券当首单 |
| 复购率 | 观察窗内 ≥2 次消费会员 ÷ 有消费会员 | 跨天/非跨天口径未声明 |
| 活跃 | 窗口内有打开/互动 **或** 有消费（须二选一写死） | 与留存混谈 |
| 沉默/流失风险 | 超 N 日无消费且无有效互动（N 按品类复购周期） | 全国统一 30 天一刀切 |
| CAC（私域） | （礼品+券成本+可归属人力+物料）÷ 有效加微或有效首单 | 只算券面、不算店员时间 |
| LTV（观察窗） | 单客在 90/180 日内贡献毛利或实收（先定口径） | 用「转化率提升幅度」冒充 LTV |
| 触达成本 | 触达人数 × 疲劳代价（退群/屏蔽率）+ 人力 | 以为群发免费 |

**品类复购周期提示（诊断必问，不作统一阈值）**  
快餐/饮品短；正餐/火锅中；零售标品看囤货周期。沉默阈值必须随复购周期缩放，不能从互联网 App「7 日活」硬套。

---

## 3. Know-how 知识原子清单

### 读写约定

每条 atom 字段对齐仓库 V1 私有库习惯，并预留 V2 迁移：

| 字段 | 含义 |
|---|---|
| `id` | 草案号 `KH-CAT-GROW-xxx`（入库时再生成 `2026Q3_0xx` / `ka_…`） |
| `type` | principle / method / anti-pattern / insight |
| `knowledge` | **一条可独立判断的陈述**（运行时检索主句） |
| `why` | 餐饮零售场景下为什么成立 |
| `action` | 建议动作（可执行） |
| `metrics` | 验证指标 + 观察窗 |
| `failure` | 常见失败模式 |
| `boundary` | 失效边界 / 加盟约束 / 合规 |
| `stage` | cold / growth / mature |
| `topics` | 受控：用户增长、转化、留存、复购、社群运营、活动、数据、合规… |
| `skills` | 绑定真实 module |
| `confidence` | 本包默认 **medium**（第三方方法 × 行业改写，非门店亲历实测） |
| `overlaps` | 与既有原子关系 |

---

### KH-CAT-GROW-001｜拉新先锁「值得拉的人」

| | |
|---|---|
| **type** | principle |
| **knowledge** | 餐饮零售的拉新第一步不是选渠道或加大钩子，而是用现有高贡献顾客（高复购/高客单/高带新）定义「值得拉进来的人」；渠道测试与放量都建立在这个定义上。 |
| **why** | 门店流量杂，钩子一开容易灌入羊毛党或低频路过客，表观加微很好看，复购和社群质量却塌。 |
| **action** | 1）从近 90 日订单抽出高贡献客群特征（品类、时段、堂食/外卖、客单）；2）写清目标画像一句话；3）再设计加微钩子与渠道实验。 |
| **metrics** | 新加微中目标画像占比；加微后 30 日首单率；90 日复购率 |
| **failure** | 先上大额券再补人群定义 → CAC 虚低、LTV 差 |
| **boundary** | 加盟店数据口径不一的，先统一会员/订单主键再画像；数据不可得时用店长访谈 + 小样本手记代替，但要标注 low 置信 |
| **stage** | cold, growth |
| **topics** | 用户增长, 数据 |
| **skills** | ops-as-ad-funnel, conversion-caliber, siyu-wenzhen |
| **source_inspire** | 大宁「拉新五步」第 1 步 |
| **overlaps** | 承接开场摸清盘（2026Q3_001），不替代基建四件套 |

---

### KH-CAT-GROW-002｜渠道用 CAC×LTV 决策，不靠感觉放量

| | |
|---|---|
| **type** | method |
| **knowledge** | 私域拉新渠道（收银台口播、桌贴、外卖贴、团购回访、短视频引流、老客转介等）的去留，应由获客成本与观察窗用户价值共同判定，再集中资源打穿最优 1–2 条，而不是平均使力。 |
| **why** | 门店触点多但店员精力有限；平均分配等于没有策略，加盟场景下更要用「哪条渠店员肯做、算得过账」说话。 |
| **action** | 1）列触点清单并各跑一小周；2）统一记：曝光→扫码→通过→入群→T 日首单；3）算 CAC（含店员时间折算）与 90 日贡献；4）停掉劣渠，把物料与话术预算集中到优渠。 |
| **metrics** | 分渠 CAC；分渠 30 日首单率；分渠 90 日 LTV 或贡献；店员执行率 |
| **failure** | 只比「加了多少人」；或只算券成本不算口播耗时 |
| **boundary** | 外卖导流须先核验平台规则与隐私合规；禁止编造平台允许口径 |
| **stage** | cold, growth |
| **topics** | 用户增长, 转化, 数据 |
| **skills** | ops-as-ad-funnel, conversion-caliber, siyu-market-research |
| **source_inspire** | 大宁拉新五步 3–5；渠道实验 |

---

### KH-CAT-GROW-003｜加微漏斗必须拆成曝光 / 扫码 / 通过

| | |
|---|---|
| **type** | method |
| **knowledge** | 加微人数下降或不动时，先拆成触点曝光、扫码成功、好友通过三跳定位第一断点，再决定是改物料、改路径还是改店员动作；禁止只盯「今日新增」一个总数。 |
| **why** | 总部与加盟常互相甩锅；没有分步计数就无法判断是码坏了、位置差，还是高峰期没人引导。 |
| **action** | 门店×时段抽样：进店/排队曝光估计、扫码次数、通过数；一次只改一个主变量。 |
| **metrics** | 曝光→扫码率；扫码→通过率；通过→入群率（同日或 24h） |
| **failure** | 券领得多但通过少时直接加大券面 |
| **boundary** | 各环节都无数时，先补计数，不归因任何一方（对齐 Golden Task add_wechat） |
| **stage** | cold, growth |
| **topics** | 用户增长, 转化, 数据 |
| **skills** | conversion-caliber, siyu-wenzhen, ops-as-ad-funnel |
| **source_inspire** | 大宁「转化漏斗找流失点」+ 项目既有 Golden Tasks |
| **overlaps** | 与「先加好友再进群」（2026Q3_007）串联：漏斗末端再接欢迎语/群码 |

---

### KH-CAT-GROW-004｜转化提升遵循「漏斗→断点→小流量验证→全量」

| | |
|---|---|
| **type** | method |
| **knowledge** | 科学提升加微后首单/复购，不是堆活动或堆券，而是先画 UV/进店→加微→入群→首单→复购漏斗，对准掉得最狠的一跳设计一个动作，小范围 AB 或门店对照验证后再全量。 |
| **why** | 连锁最容易「全国同一套群发」；断点不在同一跳时，统一加码只会抬成本。 |
| **action** | 1）画出五跳并填近 4 周数；2）圈定第一断点；3）只改该跳的一个变量（话术/钩子/时机/路径）；4）选 2–3 家对照店跑 7–14 天；5）达标再复制。 |
| **metrics** | 断点跳转化率Δ；CAC 变化；退群/拉黑率；门店执行完成率 |
| **failure** | 同时改券面、话术、时段，无法归因 |
| **boundary** | 加盟店对照要控制区位与客流近似；不能把单店奇迹外推全品牌 |
| **stage** | growth, mature |
| **topics** | 转化, 数据, 活动 |
| **skills** | conversion-caliber, ops-as-ad-funnel, siyu-wenzhen |
| **source_inspire** | 大宁「漏斗→流失点→AB→全量」 |

---

### KH-CAT-GROW-005｜店内 / 店外（池内 / 池外）增长策略必须拆开

| | |
|---|---|
| **type** | method |
| **knowledge** | 增长对象应拆成池内活跃、池内沉默、池外品类存量（在别处吃同类）、池外品类增量；四类目标不同，钩子、渠道和成功标准不能共用一张群发。 |
| **why** | 把长期未消费的老客与从未加微的路人塞进同一波「全员福利」，要么钩子不够精准，要么伤害价格体系。 |
| **action** | 池内活跃：关联推荐/到店理由（下一次吃什么）；池内沉默：预警召回（见 006）；池外存量：对比迁移利益（会员价/隐藏套餐）；池外增量：内容种草+到店钩子，可联品牌/供应方资源共担。 |
| **metrics** | 分群触达率；分群转化；分群退订/退群；资源共担后的 CAC |
| **failure** | 「全员发券」当唯一增长手段 |
| **boundary** | 池外拉新若走平台私域导流，先核合规；加盟商私自破价引流禁止 |
| **stage** | growth, mature |
| **topics** | 用户增长, 留存, 复购 |
| **skills** | ops-as-ad-funnel, reactivation-playbook, siyu-qunfa |
| **source_inspire** | 大宁站内活跃/休眠 × 站外存量/增量 |

---

### KH-CAT-GROW-006｜沉默召回优先「预警触发」，而不是等盘死了再群发

| | |
|---|---|
| **type** | method |
| **knowledge** | 沉默顾客应在越过品类复购周期阈值时自动进入召回队列，按沉默深度升级触达（轻预告→利益钩子→少量 1v1），而不是等大盘活跃掉了再做一次全员轰炸。 |
| **why** | 触达是成本（公理 4）；全员轰炸抬短期核销、伤长期可触达池。加盟店员也扛不住运动式私聊。 |
| **action** | 1）按品类定沉默阈值（例：饮品 14 日 / 正餐 30–45 日，须业务确认）；2）队列按历史贡献排序；3）轻触达用群/朋友圈预告；中度用专属到店钩子；深度才 1v1；4）退群率超阈值即停。 |
| **metrics** | 召回触达率；唤醒后 7 日到店/下单率；退群率；召回 ROI |
| **failure** | 对全库无差别发大额券；或只有文案没有分层 |
| **boundary** | 无消费数据时，用最后互动/入群时间降级代理，并标注口径弱；唤醒话术过合规 |
| **stage** | growth, mature |
| **topics** | 留存, 复购, 社群运营 |
| **skills** | reactivation-playbook, conversion-caliber, siyu-huashu |
| **source_inspire** | 大宁流失预警+自动召回；对齐 reactivation 五步 |
| **overlaps** | 强化公理「沉默盘是机制问题」 |

---

### KH-CAT-GROW-007｜社群转化：来源打标 × 身份分群 × 策略实验

| | |
|---|---|
| **type** | method |
| **knowledge** | 社群转化率提升依赖三件事同时成立：入群来源可区分、按身份/生命周期分群匹配内容与商品、对价格/促销组合做小流量实验；统一群发无法稳定抬转化。 |
| **why** | 堂食加微、外卖贴码、团购回访、活动拉新的人群预期不同；混群后只能打最大公约数内容，核销变差。 |
| **action** | 1）加微/入群链路带渠道参数或人工标签；2）至少拆：新客未首单 / 已首单未复购 / 高频 / 沉默；3）内容与钩子分群配置；4）同一分群内一次只测一个促销变量。 |
| **metrics** | 分群点击/回复；分群核销；笔单价；退群率 |
| **failure** | 建了很多群但内容仍是同一条群发复制 |
| **boundary** | 群数量受店员运营带宽约束；宁可少群分清，不少而乱；「饥饿营销」话术改为真实截止条件，禁虚假倒计时 |
| **stage** | growth, mature |
| **topics** | 社群运营, 转化, 活动 |
| **skills** | siyu-qunfa, content-as-product, ops-as-ad-funnel, siyu-huashu |
| **source_inspire** | 大宁社群转化满分答（来源分流+妈妈分群+AB） |

---

### KH-CAT-GROW-008｜业绩诊断三视角：看自己 / 看平台 / 看市场

| | |
|---|---|
| **type** | method |
| **knowledge** | 帮门店或商家提 GMV/复购时，同步复盘自身历史结构（真贡献品是谁）、平台流量与竞对结构、市场趋势，再决定主推品与预算倾斜；禁止只听感觉定主爆。 |
| **why** | 餐饮零售的「爆」常被库存、厨政、平台流量机制共同塑造；只看自家昨日销冠容易选错规格/套餐。 |
| **action** | 看自己：近 2 个大促/近 90 日品类贡献；看平台：类目榜、套餐点击、评分门槛；看市场：周边竞品与趋势；输出「主爆 + 引流 + 利润款」结构建议。 |
| **metrics** | 主爆占比；套餐点击→核销；活动期 GMV；毛利额（不只看流水） |
| **failure** | 只推高流水低毛利款，活动越成功越亏 |
| **boundary** | 加盟商改价/改套餐需总部规则；私域专属价优先走「隐藏套餐/会员价」不破公开价（对齐偷着打折） |
| **stage** | growth, mature |
| **topics** | 数据, 活动, 转化 |
| **skills** | siyu-wenzhen, siyu-market-research, ops-as-ad-funnel |
| **source_inspire** | 大宁商家 GMV 三视角 |

---

### KH-CAT-GROW-009｜活动品按四阶段运营，成熟期目标是利润与生命周期

| | |
|---|---|
| **type** | method |
| **knowledge** | 新品/活动品打法应分筹备（卖点定价机制）、启动（流量与执行）、爆发（加码与实时调优）、成熟（利润、忠诚、防御竞品）；成熟期继续只靠补贴放量会透支品牌。 |
| **why** | 餐饮新品死亡多在「上了阵没有复盘节奏」或「永远大促价」。 |
| **action** | 筹备：小范围试吃/预售测价；启动：私域首发+门店话术；爆发：限定门店或时段加码并日更数据；成熟：收回补贴、转会员常规权益、沉淀进 3322 内容素材。 |
| **metrics** | 各阶段销量与毛利；复购带出率；活动后退群/客诉；是否回到正价可售 |
| **failure** | 筹备不足直接全连锁爆发；或爆发后无退出机制 |
| **boundary** | 厨政产能与供应链未就绪不做爆发；加盟培训未完成不开全网 |
| **stage** | growth, mature |
| **topics** | 活动, 复购, 内容运营 |
| **skills** | ops-as-ad-funnel, content-as-product, siyu-qunfa |
| **source_inspire** | 大宁爆品四阶段 |

---

### KH-CAT-GROW-010｜借节点获客要切窗口，用「可到店的结果物」承接

| | |
|---|---|
| **type** | method |
| **knowledge** | 借节日/考试/赛季/开学等热点获客时，先把热点拆成需求不同的时间窗口，每个窗口只打一个主痛点；承接物应是即时可得、可分享体验的结果（到店凭证、专属菜单、测评/搭配方案），而不是一句「快来买」。 |
| **why** | 餐饮零售的热点窗口短，错窗口等于错人群；纯广告话术在朋友圈会被当垃圾站（反 3322）。 |
| **action** | 例：开学季拆「家长备餐焦虑 / 学生到店社交」；产出「一周带饭/组队套餐方案」海报+隐藏套餐码；关键信息用合规方式引导加微解锁（禁止诱导分享）。 |
| **metrics** | 窗口期内加微 CAC；结果物到店核销；分享带来的自来加微（自然传播，不强制） |
| **failure** | 热点期间狂发打折，无窗口差异 |
| **boundary** | **合规硬门**：不要求「分享到 N 个群才可领」；不绝对化功效；收集信息需授权 |
| **stage** | growth, mature |
| **topics** | 用户增长, 内容运营, 活动, 合规 |
| **skills** | content-as-product, ops-as-ad-funnel, wechat-compliance-redlines, siyu-pyq |
| **source_inspire** | 大宁高考热点×可分享报告裂变 → 餐饮合规改写 |

---

### KH-CAT-GROW-011｜留存与活跃必须分定义、分策略

| | |
|---|---|
| **type** | principle |
| **knowledge** | 在餐饮零售私域里，「还在不在可触达池」（好友/群籍保留）与「会不会来消费/互动」（活跃）是两件事；提升手段与考核指标不可混用。 |
| **why** | 只追活跃容易过度触达导致退群，可触达池变小后一切转化率失真。 |
| **action** | 看板同时保留：可触达人数、窗口活跃率、消费率、退群率；活跃策略用内容与到店理由，留存策略控制频率与价值感。 |
| **metrics** | 净可触达变化；活跃率；消费率；退群率 |
| **failure** | 用日群发数考核「活跃」，退群飙升仍报喜 |
| **boundary** | 活跃定义必须在项目启动时写死（互动 XOR 消费） |
| **stage** | growth, mature |
| **topics** | 留存, 数据 |
| **skills** | conversion-caliber, reactivation-playbook, content-as-product |
| **source_inspire** | 第三方题库对「留存/活跃」的强约束「留存 vs 活跃」 |

---

### KH-CAT-GROW-012｜RFM/分层阈值必须绑消费，且随品类复购周期校准

| | |
|---|---|
| **type** | principle |
| **knowledge** | 顾客分层（含 RFM）只有绑定真实消费行为才有运营意义；R/F/M 分档阈值必须按品类复购周期与业务确认后固化，禁止从通用互联网模板照搬，也禁止仅靠企微手工标签硬分。 |
| **why** | 既有原子已指出企微无感知消费；错分档会导致高价值客被当沉默骚扰、或沉睡客永远轮不到预算。 |
| **action** | 1）会员/订单数据出 R（最近消费）、F（频次）、M（金额）；2）与业务共创分位或业务阈值；3）每层只配 1 个主策略与 1 个主指标；4）社群/SCRM 只读标签不手工改核心分。 |
| **metrics** | 各层人数稳定性；层内策略 ROI；误伤率（高价值被召回券骚扰等） |
| **failure** | 标签体系很炫，但和下单数据对不上 |
| **boundary** | 口径/SQL/看板细节转 **majia-huiyuan**；本 atom 只约束「必须绑消费 + 周期校准」 |
| **stage** | growth, mature |
| **topics** | 数据, 留存, 复购 |
| **skills** | siyu-wenzhen, conversion-caliber |
| **source_inspire** | 大宁 RFM 追问 + 既有 2026Q3_020 |
| **overlaps** | 扩展 2026Q3_020，不替代会员公式库 |

---

### KH-CAT-GROW-013｜店员动作是增长函数的一部分，必须最小化高峰额外负担

| | |
|---|---|
| **type** | principle |
| **knowledge** | 在加盟餐饮场景，任何拉新/促活动作若显著增加收银高峰的额外步骤且门店无感知收益，执行率必然塌陷；设计增长策略时要把店员动作成本当作一等约束。 |
| **why** | Golden Tasks 与门店现实反复证明：码在收银台但没人引导 = 零；总部觉得「就多说一句话」，高峰期是生死线。 |
| **action** | 设计「一句话 + 一指码」级最小动作；收益可归属到店（核销/奖励）；培训考核看执行抽样而非只看结果数。 |
| **metrics** | 引导执行率（神秘顾客/抽检）；高峰 vs 低峰加微差；门店投诉「太麻烦」次数 |
| **failure** | 复杂多步：先下载小程序再注册再加信再填表 |
| **boundary** | 不默认总部能罚款驱动的强管控；奖励不得诱导虚假添加 |
| **stage** | cold, growth |
| **topics** | 用户增长, 转化 |
| **skills** | siyu-wenzhen, ops-as-ad-funnel, siyu-huashu |
| **source_inspire** | 项目 Golden Tasks + 加盟执行差（长期记忆中的加盟执行规则） |
| **overlaps** | 与口播欢迎语原子协同 |

---

### KH-CAT-GROW-014｜反模式：用累计会员数代替增长质量

| | |
|---|---|
| **type** | anti-pattern |
| **knowledge** | 把「累计加微/累计会员」当核心增长KPI，而不看周期新增质量、首单、复购与可触达健康度，会系统性地奖励灌水和伤盘式触达。 |
| **why** | 公理与会员成熟度误区一致：做了会员 ≠ 做好会员；有私域 ≠ 玩好私域。 |
| **action** | KPI 改成：周期有效新增、目标画像占比、T 日首单、窗口复购、净可触达、退群率；累计数仅作盘面附录。 |
| **metrics** | 见 action |
| **failure** | 年底冲刺「破 10 万会员」运动 |
| **boundary** | 对外 PR 可用累计，对内经营绝不用累计替代效率指标 |
| **stage** | cold, growth, mature |
| **topics** | 数据, 用户增长 |
| **skills** | conversion-caliber, siyu-wenzhen |
| **source_inspire** | 餐饮方法论「会员成熟度误区」+ 大宁对 CAC/LTV 的强调 |

---

### KH-CAT-GROW-015｜反模式：把社群运营停在「会群发」，不挂用增口径

| | |
|---|---|
| **type** | anti-pattern |
| **knowledge** | 只交付群发文案与活动排期、不挂载加微 CAC、漏斗断点、分群转化与召回 ROI，私域会停在执行岗能力，无法升级为可诊断的用户增长系统。 |
| **why** | 大宁岗位地图亦指出社群≈私域入口岗、难直接当终局；siyu-team 的产品化路径要求执行技能反向绑定增长口径。 |
| **action** | 每次群发/活动方案强制附：目标分群、漏斗假设、主指标、失败止损（退群阈值）；复盘用同一张表。 |
| **metrics** | 方案附口径完整率；复盘可归因率 |
| **failure** | 「本周文案 7 条」当唯一交付 |
| **boundary** | 不否定文案能力，只否定无口径的文案堆砌 |
| **stage** | growth, mature |
| **topics** | 社群运营, 数据, 用户增长 |
| **skills** | siyu-qunfa, ops-as-ad-funnel, conversion-caliber, content-as-product |
| **source_inspire** | 大宁岗位认知 + 项目「运营即广告」公理 |

---

### KH-CAT-GROW-016｜增长体检清单（问诊用）

| | |
|---|---|
| **type** | method |
| **knowledge** | 餐饮零售私域增长体检至少覆盖九项：目标人群定义、分渠 CAC、加微三跳漏斗、入群与欢迎承接、首单转化、分群策略、沉默预警召回、主爆/活动四阶段、可触达健康度；缺项先补定义再给方案。 |
| **why** | 防止客户一句「帮我做增长」就跳进发券；对齐 siyu-wenzhen 消解与升舱。 |
| **action** | 按九项逐条要证据（有数读数，无数先定性）；输出「断点排序 + 本周只打一个断点」。 |
| **metrics** | 九项填完率；首个断点实验是否上线 |
| **failure** | 体检变成功能清单推销（上 SCRM、上全套自动化） |
| **boundary** | 厂商/报价问题另走 siyu-market-research 证据门 |
| **stage** | cold, growth, mature |
| **topics** | 用户增长, 数据 |
| **skills** | siyu-wenzhen, conversion-caliber, ops-as-ad-funnel |
| **source_inspire** | 大宁用户运营题库地图 × 餐饮五步 |

**九项展开（检查表）**

1. 高价值/目标画像是否写清？  
2. 各触点是否有分步计数与 CAC？  
3. 曝光→扫码→通过哪一跳最差？  
4. 加好友→欢迎语→入群是否闭环？（既有基建原子）  
5. 加微后 T 日首单率？断在领券还是到店？  
6. 来源/身份是否分群运营？  
7. 沉默阈值是否按品类设定并有升级路径？  
8. 当前主推活动处于四阶段的哪一段？  
9. 净可触达与退群率是否在看？  

---

## 4. 与 skills / Golden Tasks 的挂载图

| Atom | 主 skill | 次 skill | Golden 主题 |
|---|---|---|---|
| 001 画像先行 | ops-as-ad-funnel | siyu-wenzhen | add_wechat / activity |
| 002 渠道 CAC×LTV | conversion-caliber | ops-as-ad-funnel | add_wechat |
| 003 加微三跳 | conversion-caliber | siyu-wenzhen | **add_wechat** |
| 004 漏斗实验 | ops-as-ad-funnel | conversion-caliber | activity |
| 005 四池拆分 | ops-as-ad-funnel | reactivation-playbook | repurchase |
| 006 预警召回 | reactivation-playbook | siyu-huashu | **repurchase** |
| 007 社群分群转化 | siyu-qunfa | content-as-product | **activity** |
| 008 三视角业绩 | siyu-wenzhen | siyu-market-research | activity |
| 009 活动四阶段 | ops-as-ad-funnel | siyu-qunfa | **activity** |
| 010 节点结果物 | content-as-product | wechat-compliance-redlines | activity |
| 011 留存≠活跃 | conversion-caliber | reactivation-playbook | repurchase |
| 012 RFM 绑消费 | siyu-wenzhen | （数据细节→huiyuan） | repurchase |
| 013 店员动作成本 | siyu-wenzhen | siyu-huashu | **add_wechat** |
| 014 反模式累计KPI | conversion-caliber | siyu-wenzhen | all |
| 015 反模式只群发 | siyu-qunfa | ops-as-ad-funnel | activity |
| 016 九项体检 | siyu-wenzhen | conversion-caliber | all |

---

## 5. 明确不入库（从大宁原材料剔除）

- 一切面试包装、自我介绍 AIDA、学历/offer 叙事  
- App 的 DAU/次留/灰度发布作为餐饮主指标  
- 未核验的「+126% 转化」「75% 首购」等教学数字当行业基线  
- 诱导式裂变、虚假饥饿营销话术  
- 职场权谋 / be like 段子  

---

## 6. 与现有公理的对齐自检

| 公理 | 本包体现 |
|---|---|
| 私域即公关 | 011 可触达健康；006 反轰炸 |
| 内容即产品 | 007 分群内容；010 结果物 |
| 运营即广告 | 002/004 每条动作有 CAC 与实验 |
| 触达是成本 | 006/011/014 |
| 沉默盘是机制问题 | 006/012 |
| 合规前置 | 010 boundary；全包 skills 含红线处 |

---

## 7. 建议入库形态（你点头后再做）

### 7.1 私有 V1 JSONL（与现 23 条同形）

```json
{
  "id": "2026Q3_024",
  "knowledge": "……同 knowledge 字段……",
  "original": "第三方用增方法经餐饮零售改写，非单店实测原文。",
  "source": "docs/source-materials/catering-retail-growth-knowhow-atoms.md#KH-CAT-GROW-001",
  "date": "2026-08-06",
  "topics": ["用户增长", "数据"],
  "skills": ["ops-as-ad-funnel", "conversion-caliber"],
  "type": "principle",
  "confidence": "medium"
}
```

- 写入：`knowledge/03-majia-sop/atoms.jsonl`（git-ignore）或 `~/.siyu-team/knowledge/`  
- `confidence=medium` 直至门店试点后升 high  

### 7.2 预留 V2 字段（Runtime 注入时）

- `scope.industry=catering`，`business_model=franchise`  
- `evidence_grade=C`（公开方法转译）或试点后 `B`  
- `review_status=draft` → 人工 approved 才进检索  

### 7.3 文档层（可选公开）

- 将 §2 指标字典 + §3 knowledge 句 压缩进  
  `knowledge/00-methodology/用增方法映射-餐饮零售.md`  
- `docs/THIRD_PARTY_INSPIRATIONS.md` 增加大宁一行来源说明  

---

## 8. 过目清单（请直接批注）

- [ ] 行业默认 **加盟餐饮** 是否正确？是否要并列「单店零售」单独 stage？  
- [ ] 16 条是否过多？是否先入 **001–007 + 013–016** 核心 11 条？  
- [ ] `confidence=medium` 是否统一，或标 `low` 等试点？  
- [ ] 沉默阈值是否保持「业务确认」、不写死数字？  
- [ ] 是否立即导出 JSONL 草案到私有 atoms 文件？  
- [ ] 是否需要补商超、美妆集合店等业态的差异附录？  

---

## 9. 一页纸：运行时可检索主句（复制用）

1. 拉新先锁高贡献顾客画像，再选渠道。  
2. 渠道用 CAC×观察窗价值决策，集中打穿优渠。  
3. 加微必看曝光/扫码/通过三跳，不看单个总数。  
4. 转化：漏斗找断点 → 单变量小流量验证 → 全量。  
5. 池内活跃/沉默与池外存量/增量策略拆开。  
6. 沉默按复购周期预警触发，深度升级，禁全员轰炸。  
7. 社群：来源打标 × 身份分群 × 促销实验。  
8. 提业绩：看自己、看平台、看市场后定主爆。  
9. 活动品走筹备/启动/爆发/成熟，成熟期收回补贴。  
10. 热点切窗口，用可到店结果物承接；裂变必须合规。  
11. 留存（还在池里）≠ 活跃（还会来）；指标分开。  
12. 分层/RFM 必须绑消费，阈值随品类校准。  
13. 店员高峰动作成本是一等约束。  
14. 禁止用累计会员数当核心增长 KPI。  
15. 禁止只交群发、不挂用增口径。  
16. 增长体检九项缺一则先补定义再给方案。  

---

## 10. 修订记录

| 日期 | 说明 |
|---|---|
| 2026-08-06 | 首版：自大宁用增素材 + 餐饮册 + 既有 23 原子 + Nowledge「Know-how 运行时注入」方向，收成 16 条餐饮零售专精草案 |
