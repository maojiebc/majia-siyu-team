"""Bounded skill composition. Produces plans; never calls models or publishes.

The contract exported here is also consumed by prompt-only hosts. Result records
are host attestations with artifact references, not proof of business outcomes.
"""
from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Mapping

from .errors import TaskValidationError
from .task import Task, TaskKind, kind_signal_positions


CAPABILITIES: dict[str, dict[str, Any]] = {
    "moments_copy": {
        "skill": "siyu-pyq", "kind": "moments_copy", "target_type": "bundled",
        "accepts": "已确认的读者、活动条件与真实素材；未确认条件保留待核",
        "delivers": "朋友圈正文与按需配图简报；真实检查状态留内部交接",
        "does_not_deliver": ["会员圈选", "擅定优惠", "自动发布", "把配图简报当成图"],
        "acceptance": ["正文符合本次范围", "事实与原材料一致", "按技能完成合规检查"],
    },
    "group_message": {
        "skill": "siyu-qunfa", "kind": "group_campaign", "target_type": "bundled",
        "accepts": "已确认的活动条件、目标群与触达约束",
        "delivers": "群发或群内推送正文及必要承接",
        "does_not_deliver": ["改变活动规则", "擅自群发", "假定统一发送时刻"],
        "acceptance": ["触达范围与限制明确", "事实与原材料一致", "按技能完成合规检查"],
    },
    "dm_script": {
        "skill": "siyu-huashu", "kind": "conversation_script", "target_type": "bundled",
        "accepts": "真实客户问题与服务边界；圈人任务须先有可用人群依据",
        "delivers": "欢迎、私聊或答疑话术及必要的转人工条件",
        "does_not_deliver": ["猜测目标会员", "虚构权益", "自动联系顾客"],
        "acceptance": ["回答当前问题", "沿用真实权益与人群条件", "按技能完成合规检查"],
    },
    "diagnosis": {
        "skill": "siyu-wenzhen", "kind": "diagnosis", "target_type": "bundled",
        "accepts": "原始问题、可用证据与执行约束",
        "delivers": "有依据的诊断、未证实解释及后续动作是否成立",
        "does_not_deliver": ["以群内沉默认定流失", "把假设当事实", "自动发券"],
        "acceptance": ["区分事实与假设", "明确 proceed/stop/revise 及理由"],
        "gate": True,
    },
    "membership_audience": {
        "skill": "majia-huiyuan", "kind": "membership_data", "target_type": "external",
        "accepts": "已授权的数据、消费时间窗、会员口径与排除条件",
        "delivers": "有数据依据的会员口径、人群规则或结果及其适用条件",
        "does_not_deliver": ["缺数据时编造名单", "替代触达授权", "编写渠道文案"],
        "acceptance": ["口径和时间窗明确", "保留来源与排除条件", "明确 proceed/stop/revise"],
        "gate": True,
    },
    "market_evidence": {
        "skill": "siyu-market-research", "kind": "market_research", "target_type": "bundled",
        "accepts": "需要核验的动态事实或用户给定的选型材料",
        "delivers": "标明来源、日期、冲突与未知的证据快照",
        "does_not_deliver": ["无联网时新增厂商事实", "把材料初筛当采购批准"],
        "acceptance": ["结论不超过证据", "明确 proceed/stop/revise 及适用范围"],
        "gate": True,
    },
}

# These are conservative discovery rules, not a general natural-language planner.
# A host can explicitly declare deliverables/prerequisites after reading context.
DISCOVERY: dict[str, Any] = {
    "content": {
        "moments_copy": r"朋友圈|发圈",
        "group_message": r"群发|群公告|群内推送|社群推送",
        "dm_script": r"私聊|答疑|话术|欢迎语|破冰",
    },
    "action": r"写|生成|制作|补|起草|改写|重写|给.{0,6}(?:一|两|三|几|份|条)",
    "clause_split": r"[，,。！？!?；;\n]|(?=只(?:写|补|做|要))|"
                    r"(?:但|不过|只是)(?=(?:不要|不用|无需|不必|不需要|暂不|别))",
    "negative": r"(?:不要|不用|无需|不必|不需要|暂不|别)(?:再|帮我)?"
                r"(?:写(?!得|太|过于|那么|这么|很)|做(?!得|太)|生成|补|制作|"
                r"圈选|圈出|筛选|分层|诊断|调查|核验|朋友圈|群发|私聊|话术)",
    "finished": r"(?:已经|已)(?:完成|定稿|写好)|已有.{0,8}(?:定稿|成稿)",
    "past_action": r"写(?:过|了|好|完)|(?:已经|已).{0,4}写",
    "list_remainder": r"^(?:通知|文案|脚本|稿件|正文|各|每|一|两|三|份|条|都|也|以及|和|与|、|\s)*$",
    "specific_dm": r"私聊|答疑|欢迎语|破冰",
    "choice": r"还是|或者|二选一|哪个|哪种",
    "audience": r"(?:会员|消费记录|人群).{0,24}(?:圈选|圈出|筛选|分层)|"
                r"(?:圈选|圈出|筛选).{0,16}(?:会员|人群)",
    "diagnosis_gate": r"先.{0,16}(?:诊断|核实|判断)|"
                      r"(?:诊断|判断).{0,24}(?:再|然后|之后|据此)",
    "diagnosis_request": r"(?:请|帮我|先|需要).{0,5}诊断",
}
CONTENT_OUTPUTS = tuple(DISCOVERY["content"])
GATE_OUTPUTS = tuple(key for key, spec in CAPABILITIES.items() if spec.get("gate"))
COMPOSITION_KEYS = frozenset({
    "deliverables", "prerequisites", "available_skills", "results",
    "confirmed_facts", "hypotheses", "delivery_review",
})


def composition_contract() -> dict[str, Any]:
    return deepcopy({
        "version": "1.0",
        "capabilities": CAPABILITIES,
        "discovery": DISCOVERY,
        "input_path": "task.context.composition",
        "input_keys": sorted(COMPOSITION_KEYS),
        "execution": "sequential",
        "result_statuses": ["passed", "failed"],
        "gate_dispositions": ["proceed", "stop", "revise"],
        "rules": [
            "优先使用宿主按用户真实要求声明的 deliverables 与 prerequisites；未知输出报错。",
            "无内容交付且未声明接力时保持单步，优先沿用既有市场核验或会员数据路由；其余明确诊断只做诊断。",
            "显式 kind 不重新猜测其他意图；对应单项内容仍沿用已核验结果，不重复生成。",
            "自动发现只采用有创作动词或承接同一动词的渠道列表，排除否定及已完成分句；比较渠道不生成多个稿件。",
            "各前置信号独立保留，不能只看最高分意图；按用户原文顺序加入，已核验市场快照沿用原豁免。",
            "动态事实仍先核验；prerequisites 依次执行，渠道产物依赖全部前置结果。",
            "已有 passed 结果须有 artifact 引用；前置结果还须有 disposition。",
            "外部能力须由宿主确认可用；缺失时阻断该步及依赖它的后续步骤。",
            "passed 只记录宿主核验结果；程序不读取引用文件，不验证结果真实性。",
            "分支失败不阻断无依赖分支；全部结果通过且跨渠道核对通过才能标 complete。",
            "不自动创建 Agent、发送、发布或持久存档；满足当前目标即结束。",
        ],
        "handoff": {
            "original_request": "task.source_text",
            "constraints": "task.constraints",
            "confirmed_facts": "task.context.composition.confirmed_facts",
            "hypotheses": "task.context.composition.hypotheses",
            "upstream_results": "task.context.composition.results",
        },
        "delivery_checks": [
            "按原始任务交齐要求的产物，不增加用户未要求的渠道",
            "多渠道的价格、权益、适用对象、时间和限制一致，冲突未解不得标完成",
            "不把待核稿、配图简报、模型自检或检查通过写成已发布、已出图或经营见效",
        ],
    })


def _names(value: Any, allowed: set[str], label: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or item not in allowed for item in value
    ):
        raise TaskValidationError(f"{label} 必须是已登记名称的数组")
    return list(dict.fromkeys(value))


def _options(task: Task) -> dict[str, Any]:
    raw = task.context.get("composition", {})
    if not isinstance(raw, Mapping) or set(raw) - COMPOSITION_KEYS:
        raise TaskValidationError("composition 必须是对象，且不能含未知字段")
    options = dict(raw)
    for key, allowed in (
        ("deliverables", set(CAPABILITIES)),
        ("prerequisites", set(GATE_OUTPUTS)),
        ("available_skills", {spec["skill"] for spec in CAPABILITIES.values()}),
    ):
        if key in options:
            options[key] = _names(options[key], allowed, f"composition.{key}")
    if "confirmed_facts" in options and not isinstance(options["confirmed_facts"], dict):
        raise TaskValidationError("composition.confirmed_facts 必须是对象")
    if "hypotheses" in options and (
        not isinstance(options["hypotheses"], list)
        or any(not isinstance(item, str) for item in options["hypotheses"])
    ):
        raise TaskValidationError("composition.hypotheses 必须是字符串数组")
    results = options.get("results", {})
    if not isinstance(results, Mapping) or set(results) - CAPABILITIES.keys():
        raise TaskValidationError("composition.results 含未知产物")
    for output, result in results.items():
        _validate_result(result, gate=output in GATE_OUTPUTS)
    if "delivery_review" in options:
        _validate_result(options["delivery_review"])
    return options


def _validate_result(result: Any, *, gate: bool = False) -> None:
    if (
        not isinstance(result, Mapping)
        or result.get("status") not in {"passed", "failed"}
        or not isinstance(result.get("artifact"), str)
        or not result["artifact"].strip()
    ):
        raise TaskValidationError("结果须包含 passed/failed 状态和非空 artifact 引用")
    if gate and result["status"] == "passed" and result.get("disposition") not in {
        "proceed", "stop", "revise",
    }:
        raise TaskValidationError("前置结果须明确 disposition: proceed/stop/revise")


def _active_clauses(text: str) -> list[str]:
    return [
        clause for clause in re.split(DISCOVERY["clause_split"], text)
        if clause.strip()
        and not re.search(DISCOVERY["negative"], clause)
        and (
            re.search(r"重写|改写", clause)
            or not re.search(
                f"{DISCOVERY['finished']}|{DISCOVERY['past_action']}", clause
            )
        )
    ]


def _discover_content(text: str) -> list[str]:
    if re.search(DISCOVERY["choice"], text):
        return []
    outputs: list[str] = []
    continuing_list = False
    for clause in _active_clauses(text):
        action = re.search(DISCOVERY["action"], clause)
        remainder = clause
        for pattern in DISCOVERY["content"].values():
            remainder = re.sub(pattern, "", remainder)
        continuation = continuing_list and re.fullmatch(DISCOVERY["list_remainder"], remainder)
        if not action and not continuation:
            continuing_list = False
            continue
        found: list[str] = []
        for output, pattern in DISCOVERY["content"].items():
            match = re.search(pattern, clause)
            if not match:
                continue
            found.append(output)
        if (
            "dm_script" in found and len(found) > 1
            and not re.search(DISCOVERY["specific_dm"], clause)
        ):
            found.remove("dm_script")
        outputs.extend(output for output in found if output not in outputs)
        continuing_list = bool(found)
    return outputs


def build_workflow(task: Task, *, infer: bool = True) -> dict[str, Any] | None:
    """Build a finite dependency plan from declared or confidently found outputs."""
    options = _options(task)
    declared = options.get("deliverables")
    if declared is not None:
        outputs = list(declared)
    elif infer:
        outputs = _discover_content(task.source_text)
    else:
        outputs = [
            key for key, spec in CAPABILITIES.items()
            if spec["kind"] == task.kind.value and key not in GATE_OUTPUTS
        ]

    active_text = "，".join(_active_clauses(task.source_text))
    if not outputs and declared is None and not options.get("prerequisites"):
        if task.kind in {TaskKind.MARKET_RESEARCH, TaskKind.MEMBERSHIP_DATA}:
            return None
        if infer and re.search(DISCOVERY["diagnosis_request"], active_text):
            # An explicit diagnostic request stays one diagnostic step even when
            # its source material names several channels.
            outputs = ["diagnosis"]
        else:
            return None

    discover_gates = infer and any(output in CONTENT_OUTPUTS for output in outputs)
    signals = kind_signal_positions(active_text) if discover_gates else {}
    inferred_gates: dict[str, int] = {}
    if (
        TaskKind.MARKET_RESEARCH in signals
        and task.context.get("verified_market_snapshot") is not True
    ):
        inferred_gates["market_evidence"] = signals[TaskKind.MARKET_RESEARCH]
    if TaskKind.MEMBERSHIP_DATA in signals:
        inferred_gates["membership_audience"] = signals[TaskKind.MEMBERSHIP_DATA]
    if discover_gates:
        audience = re.search(DISCOVERY["audience"], active_text)
        diagnosis = re.search(
            f"{DISCOVERY['diagnosis_gate']}|{DISCOVERY['diagnosis_request']}",
            active_text,
        )
        if audience:
            inferred_gates.setdefault("membership_audience", audience.start())
        if diagnosis:
            inferred_gates["diagnosis"] = diagnosis.start()
    if task.kind is TaskKind.DIAGNOSIS and TaskKind.DIAGNOSIS in signals:
        inferred_gates.setdefault("diagnosis", signals[TaskKind.DIAGNOSIS])
    if not infer and task.kind in {TaskKind.MARKET_RESEARCH, TaskKind.MEMBERSHIP_DATA}:
        key = "market_evidence" if task.kind is TaskKind.MARKET_RESEARCH else "membership_audience"
        inferred_gates.setdefault(key, 0)
    gates = [
        *options.get("prerequisites", []),
        *sorted(inferred_gates, key=lambda key: inferred_gates[key]),
    ]
    gates = list(dict.fromkeys([*gates, *(o for o in outputs if o in GATE_OUTPUTS)]))
    outputs = [output for output in outputs if output not in gates]
    requested = [*gates, *outputs]
    if not requested:
        return None

    results = options.get("results", {})
    available = options.get("available_skills", [])
    steps: list[dict[str, Any]] = []
    gate_steps: list[dict[str, Any]] = []
    for output in requested:
        spec = CAPABILITIES[output]
        dependencies = list(gate_steps)
        result = results.get(output)
        status, reason = "ready", ""
        if any(
            step["status"] == "blocked"
            or results.get(step["output"], {}).get("disposition") in {"stop", "revise"}
            for step in dependencies
        ):
            status, reason = "blocked", "前置步骤未放行；保留证据缺口或停止理由"
        elif any(step["status"] != "complete" for step in dependencies):
            status, reason = "waiting", "等待前置步骤的实际结果，不能以假设代替"
        elif result:
            status = "complete" if result["status"] == "passed" else "blocked"
            reason = str(result.get("reason", "宿主已核验产物" if status == "complete" else "产物检查未通过"))
        elif spec["target_type"] == "external" and spec["skill"] not in available:
            status, reason = "blocked", f"需先确认外部能力 {spec['skill']} 可用"
        step = {
            "id": output,
            "output": output,
            "skill": spec["skill"],
            "kind": spec["kind"],
            "target_type": spec["target_type"],
            "depends_on": [parent["id"] for parent in dependencies],
            "status": status,
            "reason": reason,
            "acceptance": list(spec["acceptance"]),
            "handoff": {
                **composition_contract()["handoff"],
                "upstream_outputs": [parent["output"] for parent in dependencies],
                "deliverable": spec["delivers"],
            },
        }
        steps.append(step)
        if output in GATE_OUTPUTS:
            gate_steps.append(step)

    statuses = {step["status"] for step in steps}
    review = options.get("delivery_review", {})
    if "blocked" in statuses or review.get("status") == "failed":
        status = "blocked"
    elif statuses == {"complete"}:
        if len(outputs) > 1 and review.get("status") != "passed":
            status = "awaiting_review"
        else:
            status = "complete"
    else:
        status = "planned"
    return {
        "version": "1.0",
        "execution": "sequential",
        "status": status,
        "steps": steps,
        "delivery_checks": composition_contract()["delivery_checks"],
    }


def next_step(workflow: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Prefer runnable independent work; never return a dependent waiting step."""
    steps = workflow["steps"]
    return next(
        (step for step in steps if step["status"] == "ready"),
        next((step for step in steps if step["status"] == "blocked"), None),
    )
