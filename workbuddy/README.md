# WorkBuddy 专家团发布适配层

这里仅保存 WorkBuddy 特有的市场字段、Agent 外壳与头像。17 个能力及公开知识仍以仓库 `plugins/`、`src/` 为真源，由构建器生成一个自包含的 `majia-siyu` 总入口技能。

本地生成上传包：

```bash
python3 tools/build_workbuddy_bundle.py
```

核对已生成产物是否仍与真源一致：

```bash
python3 tools/build_workbuddy_bundle.py --check
```

默认产物：`dist/workbuddy/majia-siyu.zip`。构建器同时生成 `setting.json` 与 `settings.json`，用于兼容官方页面与官方示例 ZIP 当前存在的文件名差异；上传解析确认最终口径后可收敛为平台实际采用的一个文件。
