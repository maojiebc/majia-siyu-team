#!/usr/bin/env python3
"""破冰欢迎/答疑话术合规前置扫描。

复用专家团合规词库（单一真源 src/siyu_team/eval/compliance_lexicon.py），并在其上额外检测：
- 社交裂变门槛（欢迎语里也不能有）
- 首句索取敏感信息（手机号/身份证/定位 未经授权口径直接索取）

用法:
    echo "话术" | python3 huashu_lint.py -
    python3 huashu_lint.py 话术.txt
退出码: 0=通过(可能带软提示), 1=命中封号红线(必改), 2=用法/环境错误。
"""
import sys
import pathlib

# scripts -> siyu-huashu -> skills -> siyu-execution -> plugins -> repo 根
ROOT = pathlib.Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "src"))

try:
    from siyu_team.eval.static import scan
    from siyu_team.eval.compliance_lexicon import INDUCE_PATTERN, PRIVACY_PATTERN
except Exception as exc:  # noqa: BLE001
    print("无法加载合规词库（需在 repo 内运行）:", exc)
    sys.exit(2)

RELEVANT = {"COMPLIANCE_RED", "ABSOLUTE_CLAIM"}
def main() -> None:
    if len(sys.argv) < 2:
        print("用法: huashu_lint.py <文件|->   （- 表示从 stdin 读）")
        sys.exit(2)
    src = sys.argv[1]
    text = sys.stdin.read() if src == "-" else open(src, encoding="utf-8").read()

    hits = [d for d in scan(text)["details"] if d["flag"] in RELEVANT]
    induce = INDUCE_PATTERN.search(text)
    privacy = PRIVACY_PATTERN.search(text)

    if not hits and not induce and not privacy:
        print("✅ 话术合规前置扫描通过（无红线 / 诱导 / 首句索取敏感信息）")
        sys.exit(0)

    hard = induce is not None or any(d["hard"] for d in hits)
    flags = [d["flag"] for d in hits]
    if induce:
        flags.append("QUNFA_INDUCE")
    if privacy:
        flags.append("HUASHU_PRIVACY")
    print("⚠️ 命中：", ", ".join(flags))
    for d in hits:
        tag = "  ← 封号红线，必须改写" if d["hard"] else "  ← 广告法风险，建议改写"
        print(f"  - {d['flag']}: {d['desc']}{tag}")
    if induce:
        print(f"  - QUNFA_INDUCE: 社交裂变门槛「{induce.group(0)}」  ← 企微封号高发，必须改")
    if privacy:
        print(f"  - HUASHU_PRIVACY: 首句索取敏感信息「{privacy.group(0)}」  ← 收集信息要授权口径，建议改")
    print("改写方向见 references/合规前置扫描.md，改完再发。")
    sys.exit(1 if hard else 0)


if __name__ == "__main__":
    main()
