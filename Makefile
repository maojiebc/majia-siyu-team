.PHONY: eval validate check report

# 对一份产物方案打质量门分（低于阈值或踩合规红线 exit 1）
eval:
	PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m siyu_team.eval.cli score $(FILE) --threshold $(or $(THRESHOLD),80)

# 校验 plugins 下 SKILL.md / agent.md 结构（name==目录名、frontmatter、≤8KB）
validate:
	PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m siyu_team.eval.cli validate plugins/

# 总质量门：结构、发布版本、全库 footer/措辞/体积
check: validate
	PYTHONDONTWRITEBYTECODE=1 python3 tools/check_versions.py
	PYTHONDONTWRITEBYTECODE=1 python3 tools/check_consistency.py

# 渲染最近一次主持收口报告
report:
	@echo "见 .siyu-team/reports/"
