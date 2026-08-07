.PHONY: eval validate pilot atoms test check report

# 对一份产物方案打质量门分（低于阈值或踩合规红线 exit 1）
eval:
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
	@cmp -s knowledge/04-atoms/growth-layers.approved.jsonl tests/fixtures/pilot/growth-approved-atoms.jsonl \
		|| { echo "❌ approved 本体与 Pilot 夹具漂移：重跑 PYTHONPATH=src python3 tools/build_growth_atoms.py"; exit 1; }
	@echo "原子闸门通过：本体与夹具零漂移"

# Runtime 与状态层回归测试（stdlib unittest，零额外依赖）
test:
	PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v

# 总质量门：测试、结构、原子、发布版本、全库 footer/措辞/体积
check: test validate pilot atoms
	PYTHONDONTWRITEBYTECODE=1 python3 tools/check_versions.py
	PYTHONDONTWRITEBYTECODE=1 python3 tools/check_consistency.py

# 渲染最近一次主持收口报告
report:
	@echo "见 .siyu-team/reports/"
