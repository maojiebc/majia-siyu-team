.PHONY: compliance validate links bundles workbuddy test check bump

# 静态合规门：只报告规则命中，不产生质量分或徽章。
compliance:
	PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m siyu_team.eval.cli compliance $(FILE) --mode $(or $(MODE),customer_copy)

# 校验 plugins 下 SKILL.md 结构（name==目录名、frontmatter、≤8KB）
validate:
	PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m siyu_team.eval.cli validate plugins/

# 仓库与已提交 SkillHub 包的 Markdown 本地链接。
links:
	PYTHONDONTWRITEBYTECODE=1 python3 tools/check_links.py

# 已提交的 SkillHub 包、WorkBuddy 包与源文件一致。
bundles:
	PYTHONDONTWRITEBYTECODE=1 python3 tools/build_skillhub_bundle.py --check
	PYTHONDONTWRITEBYTECODE=1 python3 tools/build_workbuddy_bundle.py --check

# 生成 WorkBuddy 专家团上传目录与 ZIP（只写入已忽略的 dist/）。
workbuddy:
	PYTHONDONTWRITEBYTECODE=1 python3 tools/build_workbuddy_bundle.py

# 回归测试（stdlib unittest，零额外依赖）
test:
	PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v

# 总质量门：测试、结构、链接、分发包、发布版本、全库 footer/措辞/体积
check: test validate links bundles
	PYTHONDONTWRITEBYTECODE=1 python3 tools/check_versions.py
	PYTHONDONTWRITEBYTECODE=1 python3 tools/check_consistency.py

# 统一 bump 所有声明 VERSION 的 tracked 文件
bump:
	@test -n "$(VERSION)" || (echo "用法: make bump VERSION=x.y.z"; exit 1)
	PYTHONDONTWRITEBYTECODE=1 python3 tools/bump_version.py $(VERSION)
