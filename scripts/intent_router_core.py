from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MAX_MODULES = 3
DEFAULT_P12_CONFIG_PATH = Path(__file__).resolve().parents[1] / "assets" / "p12-skillopt-config.json"
DEFAULT_P13_CONFIG_PATH = Path(__file__).resolve().parents[1] / "assets" / "p13-skillopt-config.json"
DEFAULT_P14_CONFIG_PATH = Path(__file__).resolve().parents[1] / "assets" / "p14-skillopt-config.json"


def _p12_config_path() -> Path:
    override = os.environ.get("RESEARCH_GUARD_SKILLOPT_CONFIG")
    if not override:
        return DEFAULT_P12_CONFIG_PATH
    candidate = Path(override).resolve()
    evidence_root = DEFAULT_P12_CONFIG_PATH.parents[1] / "evals" / "p12-skillopt"
    expected = os.environ.get("RESEARCH_GUARD_SKILLOPT_CONFIG_SHA256", "")
    if not candidate.is_relative_to(evidence_root) or not expected:
        raise RuntimeError("SKILLOPT_CONFIG_OVERRIDE_INVALID: candidate path or hash is missing")
    actual = hashlib.sha256(candidate.read_bytes()).hexdigest()
    if actual != expected:
        raise RuntimeError("SKILLOPT_CONFIG_OVERRIDE_INVALID: candidate hash mismatch")
    return candidate


def _p12_priorities() -> dict[str, int]:
    try:
        value = json.loads(_p12_config_path().read_text(encoding="utf-8"))
        priorities = value.get("routing_priorities") or {}
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(priorities, dict):
        return {}
    result = {
        str(key): int(score) for key, score in priorities.items()
        if isinstance(score, int) and 1 <= score <= 200
    }
    for config_path in (DEFAULT_P13_CONFIG_PATH, DEFAULT_P14_CONFIG_PATH):
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            additions = config.get("routing_priorities") or {}
        except (OSError, json.JSONDecodeError):
            additions = {}
        if isinstance(additions, dict):
            result.update({
                str(key): int(score) for key, score in additions.items()
                if isinstance(score, int) and 1 <= score <= 200
            })
    return result


@dataclass(frozen=True)
class Rule:
    module: str
    priority: int
    english: tuple[re.Pattern[str], ...]
    chinese_terms: tuple[str, ...]


def _rx(*values: str) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(value, re.I) for value in values)


RULES = (
    Rule("venue_evidence", 100, _rx(
        r"\b(?:conference|venue|NeurIPS|ICML|ICLR|CVPR|ACL|AAAI|KDD|SIGMOD|CHI|ICSE|ICCV|IJCAI|EMNLP|ECCV)\b.{0,100}\b(?:paper|outline|section|layout|format|template|narrative|write|draft)\b",
        r"\b(?:paper|outline|section|layout|format|template|narrative|write|draft)\b.{0,100}\b(?:conference|venue|NeurIPS|ICML|ICLR|CVPR|ACL|AAAI|KDD|SIGMOD|CHI|ICSE|ICCV|IJCAI|EMNLP|ECCV)\b",
    ), ("顶会", "会议论文", "投稿模板", "章节名", "分章节", "排版", "叙事风格", "会场格式")),
    Rule("formula_verification", 95, _rx(
        r"\b(?:formulas?|equations?|theorems?|proofs?|lemmas?|lean|pint|sympy|dimensional|unit consistency|parameter constraints?|numerical limits?|overflow checks?)\b",
        r"\bz3\b.{0,80}\b(?:parameters?|constraints?|satisfiability|equations?|formulas?|paper|manuscript|research)\b",
        r"\b(?:parameters?|constraints?|satisfiability|equations?|formulas?|paper|manuscript|research)\b.{0,80}\bz3\b",
    ),
         ("公式", "方程", "定理", "证明", "引理", "形式化核验")),
    Rule("academic_figure", 90, _rx(
        r"\b(?:scientific|academic|paper|research|statistical|vector|architecture|workflow)\s+(?:figure|plot|chart|diagram|visuali[sz]ation)\b",
        r"\b(?:scientific image integrity|image forensics?|duplicate image regions?|microscopy integrity)\b",
    ), ("科研图", "科研绘图", "科研作图", "科研可视化", "学术图", "论文图", "统计图", "向量图", "架构图", "流程图")),
    Rule("structured_evidence", 93, _rx(
        r"\b(?:structured paper ingestion|parse (?:a |the |this )?(?:paper|pdf)|extract (?:a |the |this )?(?:paper|pdf)(?: with exact (?:page |line )?locators?)?|extract exact (?:page |line )?(?:paper|pdf) locators?|document ingestion|claim[- ]evidence|evidence graph|support(?:s|ing)? claim|refut(?:e|es|ing) claim)\b",
    ), ("\u8bba\u6587\u89e3\u6790", "\u7ed3\u6784\u5316\u5bfc\u5165", "\u8bc1\u636e\u56fe", "\u4e3b\u5f20\u8bc1\u636e", "\u8bba\u70b9\u8bc1\u636e")),
    Rule("research_integrity", 89, _rx(
        r"\b(?:preregister|preregistration|pre[- ]registration|analysis freeze|statistical consistency|recompute p[- ]?value|computational reproducibility|reproducibility run|rerun experiment|record health|retractions?|expression of concern|corrections? monitoring)\b",
    ), ("\u9884\u6ce8\u518c", "\u5206\u6790\u51bb\u7ed3", "\u7edf\u8ba1\u4e00\u81f4\u6027", "\u91cd\u73b0\u6027", "\u590d\u73b0\u6027", "\u64a4\u7a3f", "\u52d8\u8bef", "\u66f4\u6b63\u76d1\u6d4b")),
    Rule("research_artifact", 88, _rx(
        r"\b(?:paper card|systematic review|screening ledger|experiment log|lab notebook|reviewer response|response to reviewers|rebuttal)\b",
    ), ("论文卡片", "论文精读卡", "系统综述", "筛选账本", "实验日志", "实验记录", "审稿意见回复", "回复审稿人", "返修信", "修回信")),
    Rule("paper_audit", 85, _rx(
        r"\b(?:paper|manuscript|experiment|results?|citation|references?)\b.{0,80}\b(?:audit|review|check|verify|validate|finalize|submit|write|revise)\b",
        r"\b(?:audit|review|check|verify|validate|write|revise)\b.{0,80}\b(?:paper|manuscript|experiment|results?|citation|references?)\b",
        r"\b(?:write|writing|draft|revise)\b.{0,80}\b(?:related work|citations?|references?)\b",
        r"\b(?:openreview|reviewer calibration|review calibration)\b",
    ), ("论文审计", "论文审稿", "论文评审", "论文核验", "论文写作", "论文修改", "引用核验", "实验审计", "实验核验")),
    Rule("citation_literature", 80, _rx(
        r"\b(?:citation|bibliography|references?|literature review|related work|paper search|doi|bibtex|APA|MLA|IEEE|Harvard)\b",
        r"\b(?:search|analy[sz]e|assess|review|survey)\b.{0,50}\bliterature\b",
        r"\bliterature\b.{0,50}\b(?:search|analysis|assessment|review|survey)\b",
    ), ("引用", "参考文献", "文献综述", "相关工作", "论文检索", "查文献", "引文格式")),
    Rule("self_evolution", 78, _rx(
        r"\b(?:self[- ]evolution|evolve (?:the )?(?:skill|plugin)|meta[- ]optimi[sz]e|optimi[sz]e (?:the )?(?:skill|plugin))\b",
    ), ("自进化", "技能进化", "优化技能", "优化插件", "元优化")),
    Rule("domain_skill", 75, _rx(
        r"\b(?:deep dive|in-depth|specialized|professional domain|domain-specific)\b.{0,100}\b(?:research|discussion|analysis|method)\b",
    ), ("深入探讨", "深入讨论", "深入研究", "深入分析", "专业领域", "领域专用", "深度研究")),
    Rule("discipline_profile", 77, _rx(
        r"\b(?:research|paper|literature|method|analysis|deep dive|in-depth)\b.{0,100}\b(?:discipline|field|humanities|history|historical studies|philosophy|literature|linguistics|archaeology|sociology|anthropology|education|economics|law|religious studies)\b",
        r"\b(?:discipline|field|humanities|history|historical studies|philosophy|literature|linguistics|archaeology|sociology|anthropology|education|economics|law|religious studies)\b.{0,100}\b(?:research|paper|literature|method|analysis|deep dive|in-depth)\b",
        r"\b(?:initialize|bootstrap|build)\b.{0,60}\b(?:discipline|field)\s+knowledge\b",
    ), ("领域知识初始化", "首次构建领域", "未注册学科", "学科支持", "人文学科研究", "人文类研究", "历史学研究", "哲学研究", "文学研究", "语言学研究", "考古学研究")),
    Rule("research_strategy", 70, _rx(
        r"\b(?:research idea|research question|problem selection|research strategy|risk assessment|hypothesis|experiment design|ablation|decision tree|go/no-go|problem inversion)\b",
        r"\bdesign\b.{0,30}\b(?:an? )?experiment\b",
    ), ("研究想法", "科研想法", "选题", "开题", "研究问题", "研究策略", "风险评估", "假设", "实验设计", "消融", "决策树", "问题反转")),
    Rule("academic_language", 60, _rx(
        r"\b(?:academic writing|rewrite|revise|polish|translate|translation|wording|prose|defensive writing|conference\s+(?:paper|writing|manuscript))\b",
    ), ("学术写作", "写作协助", "改写", "润色", "翻译", "译文", "措辞", "论述", "防御性写作")),
    Rule("research_novelty", 55, _rx(
        r"\b(?:novelty|prior work|collision|plagiarism|research method|research mechanism)\b",
    ), ("创新", "查新", "撞车", "查重", "已有工作", "研究方法", "研究机制")),
)

RESEARCH_ENGLISH = re.compile(
    r"\b(?:research|method|mechanism|architecture|loss|objective|experiment|paper|manuscript|dataset|evaluation|contribution)\b",
    re.I,
)
RESEARCH_CHINESE = ("研究", "科研", "方法", "机制", "架构", "损失", "目标函数", "实验", "论文", "数据集", "评测", "贡献")
ACTION_ENGLISH = re.compile(r"\b(?:help|explore|analy[sz]e|design|plan|assess|find|search|create|develop|discuss|investigate)\b", re.I)
ACTION_CHINESE = ("探讨", "分析", "设计", "规划", "评估", "寻找", "搜索", "开发", "讨论", "研究一下")
METHOD_CHANGE_ENGLISH = re.compile(
    r"\b(?:change|adjust|revise|replace|switch|redesign|add|remove|modify|extend|drop)\b", re.I,
)
METHOD_CHANGE_CHINESE = ("改动", "调整", "修改", "替换", "增加", "新增", "引入", "删除", "移除", "换成", "改为")

CONFLICTS = {
    frozenset(("formula_verification", "paper_audit")): "formula_verification",
    frozenset(("citation_literature", "research_novelty")): "citation_literature",
    frozenset(("structured_evidence", "paper_audit")): "structured_evidence",
    frozenset(("discipline_profile", "domain_skill")): "discipline_profile",
}

INSTRUCTIONS = {
    "venue_evidence": "Resolve exact venue/year/track/stage through language_assist. CCF class routes discovery only; missing exact policy/template and exemplars returns ONLINE_ACQUISITION_REQUIRED.",
    "formula_verification": "Use paper_audit lean_check plus cross_verify: report Lean, Pint, SymPy, Z3, and protocol-admitted numerical results separately; use one manuscript-wide Lean file and verify every parameter is legal and used.",
    "academic_figure": "Use paper_audit.figure_action for evidence-bound SVG/PDF/PNG planning, rendering, programmatic audit, and final-size visual review.",
    "research_artifact": "Use research_design.artifact_action to hash-bind and validate a paper card, systematic-review ledger, experiment log, or reviewer-response issue board.",
    "structured_evidence": "Use paper_audit ingestion and claim-evidence subroutes. Preserve source/parser hashes and exact locators; metadata alone cannot support or refute a claim.",
    "research_integrity": "Use paper_audit for statistical/record-health checks and research_design for preregistration or resource-bounded reproducibility. Human decisions stay explicit and method changes invalidate derived receipts.",
    "paper_audit": "Use paper_audit with only its returned 2-3 roles and effort no higher than high; current online facts and every literature item need clickable HTTPS evidence.",
    "citation_literature": "Search current primary scholarly sources and return a clickable HTTPS DOI or primary-record link per item; use verified DOI metadata before citation_action formatting.",
    "self_evolution": "Use research_design.evolution_action to record evidence and generate a human-reviewed proposal only; this route cannot apply changes.",
    "domain_skill": "Search GitHub and SkillsHub, quarantine one narrow professional Skill, scan it, run exactly 2-3 optimization rounds, then admit it only after overlap review.",
    "discipline_profile": "Analyze discipline coverage before deep work. If the field is unregistered, automatically initialize a hash-bound live profile from official public catalogs; warn that the first build may take minutes and rebuild the collision plan afterward.",
    "research_strategy": "Use research_design with only 2-3 returned modules; preserve user-owned choices and route committed methods through the novelty gate.",
    "academic_language": "Use language_assist; preserve uncertainty and let only the user resolve material limitation and potential ethics choices.",
    "research_novelty": "Register the complete method and run domain-aware collision search before novelty claims.",
}


def _contains_any(text: str, values: tuple[str, ...]) -> bool:
    return any(value in text for value in values)


def _research_context(text: str) -> bool:
    return bool(RESEARCH_ENGLISH.search(text) or _contains_any(text, RESEARCH_CHINESE))


def route_prompt(prompt: str, *, priority_overrides: dict[str, int] | None = None) -> dict[str, Any]:
    text = str(prompt or "")
    priorities = _p12_priorities()
    if priority_overrides:
        priorities.update(priority_overrides)
    matches: list[dict[str, Any]] = []
    for rule in RULES:
        english_hits = sum(1 for pattern in rule.english if pattern.search(text))
        chinese_hits = sum(1 for term in rule.chinese_terms if term in text)
        hit_count = english_hits + chinese_hits
        if hit_count:
            priority = priorities.get(rule.module, rule.priority)
            matches.append({"module": rule.module, "score": priority + 5 * hit_count, "reason": f"{hit_count} intent signal(s)"})
    if ("优化" in text or "进化" in text) and ("技能" in text or "插件" in text):
        if not any(item["module"] == "self_evolution" for item in matches):
            matches.append({"module": "self_evolution", "score": 88, "reason": "compound evolution intent"})
    if not matches and _research_context(text) and (ACTION_ENGLISH.search(text) or _contains_any(text, ACTION_CHINESE)):
        matches.append({"module": "research_strategy", "score": 1, "reason": "research-context fallback owner"})
    matches.sort(key=lambda item: (-item["score"], item["module"]))
    selected: list[dict[str, Any]] = []
    suppressed: list[dict[str, Any]] = []
    for candidate in matches:
        conflict = next((
            owner
            for item in selected
            if (owner := CONFLICTS.get(frozenset((candidate["module"], item["module"]))))
        ), None)
        if conflict and conflict != candidate["module"]:
            suppressed.append({**candidate, "suppressed_by": conflict, "reason": "overlap owner precedence"})
            continue
        if len(selected) < MAX_MODULES:
            selected.append(candidate)
        else:
            suppressed.append({**candidate, "suppressed_by": "module_budget", "reason": "maximum three modules"})
    method_change = bool(
        _research_context(text)
        and (METHOD_CHANGE_ENGLISH.search(text) or _contains_any(text, METHOD_CHANGE_CHINESE))
    )
    return {
        "status": "ROUTED" if selected else "NO_RESEARCH_MODULE",
        "selected_modules": [item["module"] for item in selected],
        "primary_module": selected[0]["module"] if selected else None,
        "secondary_modules": [item["module"] for item in selected[1:]],
        "suppressed": suppressed,
        "method_change_overlay": method_change,
        "module_budget": MAX_MODULES,
        "instructions": [INSTRUCTIONS[item["module"]] for item in selected],
        "hard_overlay_instruction": (
            "A research method adjustment was detected. Invalidate any prior novelty receipt, register the complete adjusted method, and rerun the full collision search."
            if method_change else None
        ),
    }


if __name__ == "__main__":
    import sys

    print(json.dumps(route_prompt(" ".join(sys.argv[1:])), ensure_ascii=False, indent=2))
