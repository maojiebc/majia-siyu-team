# Changelog

本项目遵循 [keep-a-changelog](https://keepachangelog.com/) 与 SemVer。

## [1.2.5] - 2026-08-06
### 修复
- SkillHub 发布链路：1.2.4 版本号在商店侧出现「已存在但列表不可见」的槽位异常，无法原位写入；本版以 1.2.5 完成 SkillHub 与全渠道 SemVer 对齐。
- 功能内容与 v1.2.4 相同：公开餐饮零售用增方法映射（16 主句 / 九项体检），不自动注入 Runtime。

## [1.2.4] - 2026-08-06
### 新增
- 公开方法层新增 `knowledge/00-methodology/用增方法映射-餐饮零售.md`：连锁加盟餐饮/门店零售用户增长 16 条 Know-how 主句、指标字典、九项体检与 skill 绑定。
- 餐饮行业册增加用增层指针；维护者侧 source-materials 收录 atom 草案与大宁语料清洗过程稿。
- `docs/THIRD_PARTY_INSPIRATIONS.md` 登记用增方法骨架的第三方灵感来源与改写边界。

### 文档
- README / ClawHub 包页同步 v1.2.4 版本说明与框架图芯片。
- `knowledge/manifest.json` 注明公开用增映射已就绪，仍不启用正式 Runtime 检索。

### 说明
- 本版补齐**可公开引用的增长方法真源**，便于问诊/漏斗/促活技能挂口径；不改变 API、安装命令、skill slug。
- 不自动批准知识、不把私有 SOP 或未审核 Atom 注入 Runtime。
- 真实客户阈值与门店 SOP 仍在私有护城河层。

## [1.2.3] - 2026-08-06
### 修复
- SkillHub 详情页主标题显示 `siyu` 而非「私域专家团 · 马甲实战版」。
- 根因：历史改名后商店 slug=`siyu`、frontmatter name=`majia-siyu`（name≠slug），SkillHub UI 回退用 slug 当标题。
- 修复：`publish_skillhub.py` 仅在临时发布包内把 `name` 对齐为商店 slug，并刷新 `displayName`；GitHub 真源 `name: majia-siyu` 不变。
- 功能、API、安装命令、ClawHub slug、SkillHub 历史条目均不变。

## [1.2.2] - 2026-08-06
### 文档
- 按 majia-ota 品牌面规范重梳公开首页：角色导航表、完整能力地图（入口 / 执行 / 问诊 / 诊断 / 档案）、安装分渠道、中英文 README 对齐。
- ClawHub 包页（`skillhub/majia-siyu/README.md`）同步装修：完整框架图 + 一行功能说明 + 能力清单 + 作者块。
- 用户向文案去黑话：首页少用 Task Schema / RouteDecision 等内部术语，技术细节下沉到 `docs/`。
- SKILL.md H1 改为「私域专家团 · 马甲实战版」（对齐 majia-huiyuan）；frontmatter `name:` 仍为 `majia-siyu`，SkillHub 历史 slug 仍为 `siyu`。发布时 `displayName` 必须走品牌标题，禁止把 `siyu` / `majia-siyu` 当卡片标题。
- 框架图版本芯片与 PNG 预览同步到 v1.2.2。

### 说明
- 本次为 docs / 品牌面 patch，**功能、API、安装命令、skill slug 完全不变**。
- 老版本用户无需为功能升级；若要看新首页与 ClawHub 包页，更新到本版即可。

## [1.2.1] - 2026-08-06
### 新增
- 新增维护者侧离线知识价值盲测工具：校验试验输入、生成基线/知识双版 Prompt 包、稳定盲化、聚合 7 维评分并计算 Wilson 95% 区间。工具不调用模型或飞书 API。
- 新增 30 个连锁加盟餐饮私域 Golden Tasks，均衡覆盖加微承接、活动增量和复购召回；仓库另含 24 条明确标识的合成测试 Atom。
- 新增同行案例审核吞吐报表，区分 Qualified / Rejected，缺失工时不补零，P75 采用最近秩算法。

### 调整
- 将同行共建明确收敛为邀请制 Pilot；Phase 0 从六张日常治理表和 21 题问卷收敛为两类活跃工作面、7 个核心问题和语音优先入口。
- 飞书公开表单已在原分享链接上切换为 v1.2.1，共 13 题（7 个核心问题、5 项轻量元数据、1 个语音/附件入口）；确认同步表无真实投稿后，清除 v1.2.0 的 21 题旧字段，六张治理表仍保留。
- 明确有效贡献者获得个人结构化案例卡和本期完整脱敏知识包，并保留署名与授权选择。

### 边界
- 真实 H1/H2/H3 试验尚未执行；结果文件仅为 `Not Evaluated` 模板，不包含伪造数字。
- 本版仍不启用自动提交、自动批准、正式知识检索或 Runtime 注入；`public_corpora` 继续为空。

## [1.2.0] - 2026-08-05
### 新增
- 新增 `KnowledgeAtomV2` 数据契约、稳定 `source_id` / `atom_id`、V1 安全迁移和五级知识路径发现；公共、专家私有与客户私有知识具备明确隔离边界。
- 新增同行贡献安全原语：四类高价值信号、prompt-once 状态、结构化贡献预览、显式授权、隐私扫描和幂等提交键；本版仅提供本地基础能力，不会自动上传完整对话或自动批准知识。
- 完成飞书同行知识共建 Phase 0：六张治理表、一张原生问卷同步表、21 题案例采集表单、贡献者说明与人工审核 SOP。

### 文档
- 新增 Knowledge Runtime 契约说明、飞书 Base Schema、首期共建活动方案和第三方设计参考登记。
- README 增加同行共建入口，并明确飞书只负责协作审核，正式知识仍以版本化 JSONL 和 GitHub 发布批次为准。

### 安全
- `client_private` 原子强制要求 `client_id` 且禁止导出；V1 迁移结果固定为 `draft + exportable=false + evidence_grade=D`。
- 贡献流程默认预览后授权、拒绝即停止、重复提交复用幂等键；AI 只能辅助提炼和风险提示，不能自动审批。

## [1.1.0] - 2026-07-28
### 新增
- 新增 `siyu-market-research`：厂商选型、竞品、报价和市场地图先生成带核验日期、状态与来源链接的证据快照。
- Runtime 新增 `market_research` 任务类型，厂商、产品、报价、案例、政策和平台规则优先进入实时调研，不再由模型自由发挥。

### 安全
- 主入口加入检索门、证据门和输出门：候选对象必须来自本次公开网络检索，公司存续与产品仍售分别验证，证据不足不得正式推荐。
- 深度诊断新增公开网络证据关卡；内部知识、Get 笔记和 BI 数据不得替代外部动态事实核验。

## [1.0.1] - 2026-07-28
### 修复
- SkillHub 沿用历史 `siyu` 条目原位升级，保留下载量、收藏与版本历史；删除误建的零数据重复条目。
- 修正渠道安装命令：ClawHub 使用 `majia-siyu`，SkillHub 使用历史 slug `siyu`。代码入口、WorkBuddy 插件与 GitHub 真源仍统一为 `majia-siyu`。

## [1.0.0] - 2026-07-28
### BREAKING
- 顶层 Skill、WorkBuddy / CodeBuddy 插件与 ClawHub slug 从 `siyu` 统一改为 `majia-siyu`；用户命令 `/siyu` 保持兼容。SkillHub 为保留历史条目身份继续使用 `siyu`。

### 修复
- 重写主入口触发描述，与 `majia-huiyuan` 按“经营动作 / 会员数据”互斥分工，避免私域会员问题同时触发。
- `siyu-update` 的官方真源从历史地址修正为 `maojiebc/majia-siyu-team`。
- 自包含发布包改为仓库内可追踪的 `skillhub/majia-siyu/`，确保三渠道对应同一 Git commit。

## [0.8.0] - 2026-07-28
### 新增
- 新增 WorkBuddy / CodeBuddy 原生 `.codebuddy-plugin` 清单与市场入口。用户只需安装一个 `siyu` 插件，即可一次获得统一入口、16 个能力、4 个专家 Agent 和编排命令。
- 新增 `tools/build_skillhub_bundle.py`：从模块真源生成自包含的单一 `siyu` SkillHub 包，子能力仅作为内部路由模块，不再独立占用商店条目。

### 变更
- README 将 WorkBuddy 单插件安装设为推荐路径；Claude Code、ClawHub 与通用 Skills 安装方式继续保留。

## [0.7.0] - 2026-07-23
### 新增
- siyu 入口内置零依赖「整盘怎么搭·餐饮老板版」向导（现位于 `plugins/siyu-core/skills/majia-siyu/references/整盘怎么搭-老板版.md`）：黑话→大白话对照表、五步全貌讲法、起步四件套大白话版、可转发地图（SVG→PNG）与交互自测网页（单文件 HTML）的生成指令。只装入口、没有 runtime 的宿主环境不再降级成术语版，直接产出店老板看得懂、能落地的向导。
- 「整盘怎么搭」路由按环境与人群分档：店老板 / 纯入口环境 → 老板版向导；完整仓库 + 专业运营 → `siyu-onboard` 深度评审。`siyu-onboard` 头部新增讲人话与优先走老板版的提示。

### 变更
- 讲人话铁律：入口 SKILL.md 正文清除 playbook / 团长 / 四官 / 升舱 等黑话，语言规则从「禁英文内部术语」扩展为「中文运营黑话也禁」；正文精简回 8KB 限内并恢复统一 footer。

## [0.6.0] - 2026-07-23
### 新增
- 餐饮册企业微信冷启动基建知识包：新增 `knowledge/01-wechat-official/features/企业微信基建四件套.md`（好友码 / 对外资料页 / 好友欢迎语 / 群活码四模块脱敏 SOP + 认证要点 + SCRM 选型阶梯 + 成本口径 + 老客迁移方法论）。
- `catering/stages.md` 冷启动加微钩子库与「第一周基建 SOP」从占位升级为可执行指针；`餐饮私域方法论.md` 增补「企微地基与搭台唱戏」「老客迁移玩法卡」两节；`benchmarks.md` 补企业微信产品口径（单群 200 上限 / 2000 免费线 / 超额每客约一毛 / 认证时效）。
- 私有护城河层首建知识原子库（`knowledge/03-majia-sop/atoms.jsonl`，23 条）与实操 playbook，从一次真实付费咨询拆解沉淀，git-ignore 不入公开库。

### 说明
- 本次为知识内容增补，四官 skill 与 Runtime 代码不变；语料来源已脱敏，公开层无真实品牌 / 人名 / 报价。

## [0.5.0] - 2026-07-23
### 新增
- 质量门判官层与蒙卡层落地（B 路径）：宿主 Agent 按 8 维 rubric 逐维打分，脚本加权合成出总分 + 徽章，蒙卡层统计 N 份一致性与 Wilson 置信区间——不调外部 API，复用宿主额度。新增 `siyu-eval judge` 子命令（`--emit-prompts` / `--scores` / `--samples`）。
- 连接器 keychain 指针解析骨架：环境变量 → macOS keychain，区分「未配置」与「密钥已解析、API 待接」，绝不硬编码 token。
- 四官执行 skill 补行业通用方法框架（内容即产品 / 转化口径 / 运营即广告 / 差评应对 / 信任资产），保留 `【待马甲填真实SOP】` 私有注入点。
- 合规 lint 脚本 self-contained 降级：脱离 repo（如装成独立插件）时启用内嵌核心红线词表并告警，不再直接失效；完整词库仍以 `compliance_lexicon.py` 为单一真源。

### 变更
- 判官 / 蒙卡 / 连接器的文档口径从「未实装」更新为「B 路径已实装」。
- 回归测试从 28 增至 41 项（新增判官、蒙卡、连接器覆盖）。

## [0.4.1] - 2026-07-23
### 安全
- 脱敏加固：手机号兼容 `+86`/`86`/`0086` 国家码前缀；补 `api_key`/`access_key`/`credential`/`session` 等凭据字段名与中文别名（密码/密钥/手机号/身份证）；新增值内裸 token（GitHub/AWS/OpenAI 前缀）、邮箱、15 位老身份证、整数型号码脱敏。配 8 条回归测试覆盖历史泄漏向量并验证不误伤正常内容。
- 移除拆解文档示例 `plugin.json` 中的真实第三方名，改中性占位。

### 修复
- 合规质量门此前放行裂变诱导与隐私索取：`static.scan()` 纳入 `INDUCE_PATTERN`（诱导分享/集赞/拉人裂变，硬卡 exit 1）与 `PRIVACY_PATTERN`（未授权索取敏感信息，软提示）。
- 广告法绝对化词库扩充（补 最佳/最优/最强/最高级/绝对/唯一 等），修复「集满 N 个赞」正则断裂与隐私索取反向语序漏检；新增 eval 静态门回归测试。
- 7 个组件 `plugin.json` 版本从 `0.1.0` 对齐到发布版；`check_versions.py` 纳入组件 `plugin.json` 校验，堵住版本漂移的 CI 盲区。
- `roster.load_roster` 文件句柄泄漏（改 `with` + 异常回落内置默认）。
- 三个官 agent 的 skill 绑定字面量 `\n` 恢复换行；合规官 SOP 第 6 步「合规自查（合规官会复核）」自指矛盾改为「红线定级」。

### 文档
- 诚实化 judge/蒙卡/连接器实装状态：`score` 命令不再对静态检查结果贴「Platinum」质量徽章，并明确「不产出质量分、不代表已过质量门」；CLAUDE.md / README / 标杆移植说明标注判官·蒙卡为 4 档规划、连接器为未接入预留接口、`generate.py` 派生分发未启用；state 去掉名不副实的「防重入」表述。

## [0.4.0] - 2026-07-23
### 新增
- 结构化 `Task` Schema：任务类型、渠道、目标、风险、行业、阶段和合规要求可验证、可序列化。
- `SiyuRuntime` 执行计划层：自然语言先解析和路由，再交给现有 Skill。
- 四官 `AgentContext` 字段白名单，代码级隔离输入；合规官单独读取原始请求与风险。
- 本地 JSONL 追踪：记录任务、路由和上下文边界，落盘前脱敏凭据与个人信息。
- Runtime、状态存储、路由和脱敏共 16 个回归测试，纳入 `make check`。
- GitHub Actions 新增 Ruff 与 mypy，和原有结构/版本/一致性检查一起阻断回归。
- 按 OTA 发布面规则重画首页架构 SVG/PNG，并新增 v0.4.0 Runtime 说明、隐私与路由文档。

### 修复
- 状态文件改为原子写入、0600 权限、字段校验和幂等追加。
- 修复 v0.3.1 发布后 `VERSION` 未同步、README 徽章校验规则不匹配导致的 CI 阻断。

## [0.3.1] - 2026-07-23
### 装修
- 公开首页装修：新增框架全局图（SVG + PNG），能力一览与安装通道整理。
- README 图片走绝对 URL + PNG，确保 ClawHub / npm 页也能渲染。
- 补全品牌后缀「· 马甲实战版」、作者联系块、版本记录段。

## [0.3.0] - 2026-07-23
### 新增
- 首个公开版本（私有版脱敏镜像）。
- 统一入口 `/siyu`（新手教程 + 任务前路由 + 任务后导航）。
- 执行三件套：`siyu-pyq` 朋友圈文案 / `siyu-qunfa` 社群群发 / `siyu-huashu` 破冰话术，均内置边写边合规扫描。
- 诊断层四官专家团（团长 + 公关/产品/广告/合规 + 主持人收口 + 质量门）。
- 跨对话客户档案 `siyu-save` / `siyu-restore` / `siyu-report`。
- 餐饮行业方法论（3322 配比、造 IP 公式、偷着打折玩法）。
