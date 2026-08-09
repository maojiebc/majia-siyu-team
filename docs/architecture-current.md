# 当前执行架构

本文记录仓库当前可由代码和分发产物验证的事实。创建期设计保留在
[`blueprint.md`](blueprint.md)，v0.4.0 的历史 Runtime 说明保留在
[`runtime-v0.4.md`](runtime-v0.4.md)。

## 三条现有执行链

| 执行面 | 当前真实入口 | 已自动验证 | 尚未闭环 |
|---|---|---|---|
| 插件与 SkillHub | Markdown Skill 由宿主解释执行 | 文件结构、发布版本、生成路由契约、84 条人工对照 | Prompt-only 不具备代码强制隔离/追踪 |
| Python Runtime | `siyu-plan` / `SiyuRuntime.plan()` | ExecutionPlan v1、Task、路由、上下文隔离、状态与追踪单测 | 干净 wheel 与各宿主安装态 |
| Knowledge Pilot | `siyu-pilot` 与离线夹具 | 盲化、数据契约、Dry Run 工具 | H1/H2/H3 真实人工评估与生产装配一致性 |

这三条链目前并非同一条生产执行链。源码态 Python 测试通过，不能推导出
Markdown 宿主一定经过 Runtime；Pilot 工具可运行，也不能推导出知识已经改善真实回答。

## 当前可验证链路

```text
用户请求
  ├─ CLI 可用且契约哈希匹配：siyu-plan → ExecutionPlan(runtime_mode=python)
  └─ 否则：生成 route-contract.json → Prompt-only 计划(runtime_mode=prompt_only)

ExecutionPlan
  ├─ 单能力路由
  └─ 信息齐备的全盘任务 → 四官白名单上下文

离线质量工具
  ├─ 静态合规/反模式扫描
  └─ 宿主另行回填 Judge 分数后才有质量分
```

`plugins/.../references/route-contract.json` 与
`skillhub/.../modules/_runtime/route-contract.json` 均由 Python 常量生成，字节和
`content_sha256` 必须一致。SkillHub 包不含 Python Runtime，因此不能因为携带该契约
就宣称执行过 Runtime；Python 模式必须先用 `siyu-plan --contract-info` 完成哈希握手。

## 行业能力状态

- `catering`：`supported_with_industry_pack`，可引用真实存在的餐饮行业目录。
- `retail`：`generic_only`，可复用公开的餐饮零售 L1 方法层，但不声称有独立零售行业目录。
- `edu`：`generic_only`，只使用通用 L0，不声称有教培行业包。

路由不得为 `generic_only` 生成不存在的 `knowledge/02-industry/<industry>/` 路径。

## 自动事实检查

```bash
python tools/check_links.py
python tools/render_route_contract.py --check
python tools/build_skillhub_bundle.py --check
python tools/check_route_contracts.py
make check
```

检查覆盖仓库及已提交 SkillHub 包的 Markdown 本地链接、Python 路由目标、知识引用、
行业能力声明和公开知识原子绑定。干净构建的 SkillHub 包也会在单测中重新执行同一检查。

## 安全与产品边界

- `knowledge/03-majia-sop/` 只允许公开占位 README；真实 SOP 不进入仓库或分发包。
- 连接器是明确抛出未实现错误的骨架，不代表已接通外部系统。
- H1、H2、H3 均仍为 `Not Evaluated`；不得把工具 Dry Run 写成业务验证通过。
- 当前版本不新增 Skill、角色或行业包；先完成 Runtime、分发、知识和质量语义对齐。
