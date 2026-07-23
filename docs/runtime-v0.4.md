# v0.4.0 Runtime 架构说明

v0.4.0 的核心变化，是在现有 Skill 前增加一个可验证的计划层。自然语言不再直接决定要调用哪个能力，而是先转成结构化任务，再由确定性路由选择当前唯一一步。

## 请求链路

```text
用户请求
  ↓
Task Schema
  ↓
RouteDecision
  ├─ 高频执行：siyu-pyq / siyu-qunfa / siyu-huashu
  ├─ 轻问诊：siyu-wenzhen
  ├─ 全盘升舱：siyu-onboard → 四官 → 团长 → 质量门
  └─ 档案管理：siyu-save / restore / report
```

Runtime 只生成执行计划，不直接调用模型。Skill 仍负责业务产出，这样已有插件和安装方式保持兼容。

## 核心对象

### Task

定义在 `src/siyu_team/task.py`，固定以下字段：

- `kind`：朋友圈、群发、话术、问诊、全盘评审、存档等任务类型。
- `channel`：朋友圈、群聊、私聊、多渠道或未知。
- `goal`：转化、留存、获客、互动、信任、诊断或归档。
- `industry` / `stage`：行业与业务阶段。
- `risk` / `need_compliance_check`：输入风险与合规要求。
- `context`：可序列化的结构化业务字段。

非法枚举、非布尔合规字段、不可 JSON 序列化的上下文会在路由前失败。

### RouteDecision

定义在 `src/siyu_team/routing.py`，输出：

- 当前唯一 `skill`；
- 可解释的路由理由；
- 是否仍需补信息；
- 必填字段；
- 阶段重点与知识库引用。

整盘评审缺少行业或阶段时，只返回待补字段，不创建四官上下文。

### AgentContext

定义在 `src/siyu_team/context.py`。公关、产品、广告、合规四官各有独立字段白名单：

- 公关官只看品牌、口碑和客户反馈；
- 产品官只看权益、内容资产和客户需求；
- 广告官只看权益、预算、指标和漏斗；
- 合规官读取已脱敏的原始请求、授权和数据收集方式。

Prompt 负责角色表达，代码负责信息边界。未知角色直接拒绝。

## 可恢复与可追踪

`StateStore` 使用临时文件、`fsync` 和 `os.replace` 原子更新 `.siyu-team/state.json`，并把目录和文件权限收紧为 0700/0600。v0.3.x 无 schema 版本的状态会在下一次更新时自动迁移。

`TraceRecorder` 为每轮计划生成 `trace_id`，按 JSONL 记录任务、路由和上下文字段边界。写盘前会处理：

- token、secret、password、cookie 等敏感字段；
- 中国大陆手机号；
- 18 位身份证号；
- Bearer 凭据。

Trace 默认保存在 `.siyu-team/traces/`，受 `.gitignore` 保护。

## CLI

```bash
PYTHONPATH=src python3 -m siyu_team.cli \
  "群发三轮没人打开，问题出在哪？" \
  --industry catering
```

输出是 JSON 执行计划。加 `--no-trace` 可只预览、不落追踪。

## 质量门

```bash
make check
```

当前会执行：

1. 16 个 Runtime、路由、状态和脱敏回归测试；
2. SKILL frontmatter、目录名和 8KB 上限检查；
3. VERSION、marketplace、README 徽章一致性检查；
4. 全库 footer、用户措辞和护城河占位检查。

GitHub Actions 额外执行 Ruff 与 mypy。

## 当前边界

以下能力尚未在 v0.4.0 完成：

- Runtime 尚不直接执行模型或管理模型重试；
- LLM Judge 与 Monte Carlo Eval 仍是接口占位；
- BI、飞书、Get 笔记和 Nowledge Mem 连接器仍是薄包装；
- 长期客户档案还没有 tenant/workspace 级隔离。

这意味着 v0.4.0 完成的是“输入与派发边界工程化”，不是完整 SaaS Runtime。
