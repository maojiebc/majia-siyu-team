.PHONY: compliance judge eval validate pilot atoms links contracts workbuddy test check report bump

# 静态合规门：只报告规则命中，不产生质量分或徽章。
compliance:
	PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m siyu_team.eval.cli compliance $(FILE) --mode $(or $(MODE),customer_copy)

# 独立 Judge：无 SCORES 时生成 prompts；有 SCORES 时生成机器可读 JudgeReport。
judge:
	PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m siyu_team.eval.cli judge $(FILE) \
		$(if $(SCORES),--scores $(SCORES),--emit-prompts) \
		$(if $(REPORT),--output $(REPORT),) \
		--threshold $(or $(THRESHOLD),80) --mode $(or $(MODE),customer_copy)

# v1.4.1 兼容别名：deprecated，只执行静态合规检查，不再声称打质量分。
eval:
	@echo "⚠️ make eval 已 deprecated；本次仅执行静态合规检查，请改用 make compliance。"
	PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m siyu_team.eval.cli score $(FILE) --threshold $(or $(THRESHOLD),80)

# 校验 plugins 下 SKILL.md / agent.md 结构（name==目录名、frontmatter、≤8KB）
validate:
	PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m siyu_team.eval.cli validate plugins/

# 校验 v1.2.8 Knowledge Pilot 的 30 题与合成 fixture（不读取私有 Atom）
pilot:
	PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m siyu_team.pilot.cli validate --fixtures
	PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m siyu_team.pilot.cli validate \
		--tasks tests/fixtures/pilot/golden-tasks.jsonl \
		--atoms tests/fixtures/pilot/growth-approved-atoms.jsonl \
		--mapping tests/fixtures/pilot/growth-task-atom-map.json \
		--allow-public-atoms

# 校验知识原子：v1 示例、v2 正式集本体，以及本体与 Pilot 夹具零漂移
atoms:
	PYTHONDONTWRITEBYTECODE=1 python3 tools/atoms_validate.py knowledge/04-atoms/atoms.example.jsonl
	PYTHONDONTWRITEBYTECODE=1 python3 tools/atoms_validate.py knowledge/04-atoms/growth-layers.approved.jsonl
	PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m siyu_team.eval.cli compliance knowledge/04-atoms/growth-layers.approved.jsonl --mode knowledge
	@cmp -s knowledge/04-atoms/growth-layers.approved.jsonl tests/fixtures/pilot/growth-approved-atoms.jsonl \
		|| { echo "❌ approved 本体与 Pilot 夹具漂移：重跑 PYTHONPATH=src python3 tools/build_growth_atoms.py"; exit 1; }
	PYTHONDONTWRITEBYTECODE=1 python3 tools/sync_public_knowledge.py --check
	@echo "原子闸门通过：本体与夹具零漂移"

# 仓库与已提交 SkillHub 包的 Markdown 本地链接。
links:
	PYTHONDONTWRITEBYTECODE=1 python3 tools/check_links.py

# Python 路由目标、行业能力、知识引用与分发包路径对账。
contracts:
	PYTHONDONTWRITEBYTECODE=1 python3 tools/render_route_contract.py --check
	PYTHONDONTWRITEBYTECODE=1 python3 tools/build_skillhub_bundle.py --check
	PYTHONDONTWRITEBYTECODE=1 python3 tools/build_workbuddy_bundle.py --check
	PYTHONDONTWRITEBYTECODE=1 python3 tools/check_route_contracts.py

# 生成 WorkBuddy 专家团上传目录与 ZIP（只写入已忽略的 dist/）。
workbuddy:
	PYTHONDONTWRITEBYTECODE=1 python3 tools/build_workbuddy_bundle.py

# Runtime 与状态层回归测试（stdlib unittest，零额外依赖）
test:
	PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v

# 总质量门：测试、结构、原子、发布版本、全库 footer/措辞/体积（pilot 为 opt-in，见 make pilot）
check: test validate atoms links contracts
	PYTHONDONTWRITEBYTECODE=1 python3 tools/check_versions.py
	PYTHONDONTWRITEBYTECODE=1 python3 tools/check_consistency.py

# 统一 bump 所有声明 VERSION 的 tracked 文件
bump:
	@test -n "$(VERSION)" || (echo "用法: make bump VERSION=x.y.z"; exit 1)
	PYTHONDONTWRITEBYTECODE=1 python3 tools/bump_version.py $(VERSION)

# 渲染最近一次主持收口报告
report:
	@echo "见 .siyu-team/reports/"
