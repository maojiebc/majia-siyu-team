#!/usr/bin/env python3
"""社群群发合规前置扫描。

复用专家团合规词库（单一真源 src/siyu_team/eval/compliance_lexicon.py），并重点扫描
群发特有的社交裂变门槛——转发得赠、集赞、拉人进群都是企微封号高发动作。

用法:
    echo "群发文案" | python3 qunfa_lint.py -
    python3 qunfa_lint.py 文案.txt
退出码: 0=通过, 1=命中封号红线(必改), 2=用法/环境错误。
"""
import sys
import pathlib

# scripts -> siyu-qunfa -> skills -> siyu-execution -> plugins -> repo 根
ROOT = pathlib.Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "src"))

try:
    from siyu_team.eval.static import scan
    from siyu_team.eval.compliance_lexicon import INDUCE_PATTERN
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
    INDUCE_PATTERN = _re.compile(
        r"(转发.{0,8}(领|送|得|抽|享|免)|集(?:满|齐|够)?\s*\d*\s*个?赞|拉\s*\d+\s*人)"
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
        print("用法: qunfa_lint.py <文件|->   （- 表示从 stdin 读）")
        sys.exit(2)
    src = sys.argv[1]
    text = sys.stdin.read() if src == "-" else open(src, encoding="utf-8").read()

    hits = [d for d in scan(text)["details"] if d["flag"] in RELEVANT]
    induce = INDUCE_PATTERN.search(text)

    if not hits and not induce:
        print("✅ 群发合规前置扫描通过（无封号红线 / 裂变门槛）")
        sys.exit(0)

    hard = induce is not None or any(d["hard"] for d in hits)
    flags = [d["flag"] for d in hits] + (["QUNFA_INDUCE"] if induce else [])
    print("⚠️ 命中：", ", ".join(flags))
    for d in hits:
        tag = "  ← 封号红线，必须改写" if d["hard"] else "  ← 广告法风险，建议改写"
        print(f"  - {d['flag']}: {d['desc']}{tag}")
    if induce:
        print(f"  - QUNFA_INDUCE: 社交裂变门槛「{induce.group(0)}」  ← 企微封号高发，必须改走官方路径")
    print("改写方向见 references/合规前置扫描.md，改完再发。")
    sys.exit(1 if hard else 0)


if __name__ == "__main__":
    main()
