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
except Exception as exc:  # noqa: BLE001
    print("无法加载合规词库（需在 repo 内运行）:", exc)
    sys.exit(2)

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
