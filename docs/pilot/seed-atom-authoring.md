# 24 条真实 Pilot Atom 编制协议

真实 Atom 不进 Git，统一存在 `~/.siyu-team/knowledge/approved/expert.atoms.jsonl`，文件权限 `0600`，父目录 `0700`。仓库的 `tests/fixtures/pilot/synthetic-approved-atoms.jsonl` 只用于开发和回归，不是业务证据。

每个主题至少 8 条，一条 Atom 只属于一个试验主题。必须是 KnowledgeAtomV2，`quality.review_status=approved`，有审阅人和日期，不过期，不得为 `client_private`。写清：

- 一条可独立判断的 statement；
- 成立前提和建议动作；
- 可核验指标与观察窗口；
- 常见失败模式和至少一条失效边界；
- 证据等级、置信度、来源定位和使用范围。

禁止写入客户名、门店编号、手机号、会员或订单明细、密钥、可反推客户的精确数字。评审不允许因贡献者回传确认而自动提升证据等级。
