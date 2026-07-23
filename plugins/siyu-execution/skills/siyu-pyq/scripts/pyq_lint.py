#!/usr/bin/env python3
"""朋友圈文案合规前置扫描。

复用专家团合规词库（单一真源 src/siyu_team/eval/compliance_lexicon.py）——这就是把"合规官"
从事后评审节点，变成生成前的内嵌函数（边写边合规）。

只查朋友圈相关的合规项（COMPLIANCE_RED / ABSOLUTE_CLAIM），过滤掉给"方案质量门"
用的 NO_METRIC / NO_CALIBRATION 等不适用项。

用法:
    echo "文案" | python3 pyq_lint.py -
    python3 pyq_lint.py 文案.txt
退出码: 0=通过, 1=命中封号红线(必改), 2=用法/环境错误。
"""
import sys
import pathlib

# 找到 repo 根，把 src 加入 import 路径（scripts -> siyu-pyq -> skills -> siyu-execution -> plugins -> repo）
ROOT = pathlib.Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "src"))

try:
    from siyu_team.eval.static import scan
except Exception:  # 脱离 repo（如装成独立插件）时降级兜底
    import re as _re

    print(
        "⚠️ 脱离 repo，启用降级合规词表（只拦最关键封号红线；完整词库单一真源见 "
        "src/siyu_team/eval/compliance_lexicon.py）",
        file=sys.stderr,
    )
    _RED = _re.compile(
        r"(诱导分享|外挂|群发软件|虚拟定位|改定位|第一|最便宜|最好|最佳|最优|最强"
        r"|最高级|国家级|世界级|100%|稳赚|包赚)"
    )

    def scan(text):
        hit = _RED.search(text)
        details = (
            [{"flag": "COMPLIANCE_RED", "desc": "封号/绝对化（降级词表）",
              "severity": 0.2, "hard": True}]
            if hit else []
        )
        return {
            "flags": [d["flag"] for d in details],
            "details": details,
            "penalty": 1.0,
            "hard_fail": bool(hit),
        }

RELEVANT = {"COMPLIANCE_RED", "ABSOLUTE_CLAIM"}


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: pyq_lint.py <文件|->   （- 表示从 stdin 读）")
        sys.exit(2)
    src = sys.argv[1]
    text = sys.stdin.read() if src == "-" else open(src, encoding="utf-8").read()

    result = scan(text)
    hits = [d for d in result["details"] if d["flag"] in RELEVANT]
    if not hits:
        print("✅ 合规前置扫描通过（无封号红线 / 绝对化用词）")
        sys.exit(0)

    hard = any(d["hard"] for d in hits)
    print("⚠️ 命中：", ", ".join(d["flag"] for d in hits))
    for d in hits:
        tag = "  ← 封号红线，必须就地改写" if d["hard"] else "  ← 广告法风险，建议改写"
        print(f"  - {d['flag']}: {d['desc']}{tag}")
    print("改写方向见 references/合规前置扫描.md，改完再发。")
    sys.exit(1 if hard else 0)


if __name__ == "__main__":
    main()
