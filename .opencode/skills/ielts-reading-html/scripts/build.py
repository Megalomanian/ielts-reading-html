#!/usr/bin/env python3
"""Build a self-contained interactive HTML study page from an IELTS reading case JSON.

Usage:
    python build.py case.json --check
    python build.py case.json -o index.html
"""

from __future__ import annotations

import argparse
import copy
import difflib
import html
import json
import re
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = SKILL_DIR / "assets" / "template.html"
BUILD_VERSION = "1.0.0"

MARKER_RE = re.compile(r"\{\{([^{}]+)\}\}")
WS_RE = re.compile(r"\s+")

TYPE_LABELS = {
    "true_false_not_given": "判断题 · TRUE / FALSE / NOT GIVEN",
    "yes_no_not_given": "判断题 · YES / NO / NOT GIVEN",
    "multiple_choice": "选择题",
    "matching_headings": "段落标题匹配",
    "matching_information": "信息匹配",
    "matching_features": "特征匹配",
    "matching_sentence_endings": "句子结尾匹配",
    "summary_completion": "摘要填空",
    "sentence_completion": "句子填空",
    "note_completion": "笔记填空",
    "table_completion": "表格填空",
    "flowchart_completion": "流程图填空",
    "short_answer": "简答题",
    "diagram_labeling": "图示标注",
}

TYPE_ALIASES = {
    "tfng": "true_false_not_given",
    "true_false": "true_false_not_given",
    "true_false_notgiven": "true_false_not_given",
    "ynng": "yes_no_not_given",
    "yes_no": "yes_no_not_given",
    "yes_no_notgiven": "yes_no_not_given",
    "mcq": "multiple_choice",
    "multiple_choices": "multiple_choice",
    "headings": "matching_headings",
    "matching_heading": "matching_headings",
    "matching_informations": "matching_information",
    "matching_feature": "matching_features",
    "matching_sentence": "matching_sentence_endings",
    "summary": "summary_completion",
    "sentence": "sentence_completion",
    "notes_completion": "note_completion",
    "table": "table_completion",
    "flow_chart_completion": "flowchart_completion",
    "short_answers": "short_answer",
    "diagram": "diagram_labeling",
}

TFNG = {"TRUE", "FALSE", "NOT GIVEN"}
YNNG = {"YES", "NO", "NOT GIVEN"}
ANSWER_SOURCES = {"official", "derived", "mixed"}


class Issues:
    def __init__(self) -> None:
        self.items: list[tuple[str, str, str]] = []

    def error(self, where: str, message: str) -> None:
        self.items.append(("ERROR", where, message))

    def warn(self, where: str, message: str) -> None:
        self.items.append(("WARN", where, message))

    @property
    def errors(self) -> list[tuple[str, str, str]]:
        return [i for i in self.items if i[0] == "ERROR"]

    @property
    def warnings(self) -> list[tuple[str, str, str]]:
        return [i for i in self.items if i[0] == "WARN"]


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def norm(value: Any) -> str:
    return WS_RE.sub(" ", "" if value is None else str(value)).strip()


def norm_lines(value: Any) -> str:
    if value is None:
        return ""
    lines = [norm(line) for line in str(value).splitlines()]
    return "\n".join(line for line in lines if line)


def as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def normalize_type(value: Any) -> str:
    raw = norm(value).lower().replace("/", "_").replace("-", "_").replace(" ", "_")
    raw = re.sub(r"_+", "_", raw).strip("_")
    if not raw:
        return "short_answer"
    return TYPE_ALIASES.get(raw, raw)


def type_label(qtype: str) -> str:
    return TYPE_LABELS.get(qtype, qtype.replace("_", " ").title())


def para_dom_id(passage_index: int, para_index: int) -> str:
    return f"para-p{passage_index + 1}-{para_index + 1}"


def load_case(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def normalize_case(case: Any) -> Any:
    if not isinstance(case, dict):
        return case
    case = copy.deepcopy(case)

    meta = case.get("meta")
    if isinstance(meta, dict):
        for key in ("title", "subtitle", "exam", "source", "answerSource", "createdAt", "note", "slug"):
            if isinstance(meta.get(key), str):
                meta[key] = norm(meta[key])

    passages = case.get("passages")
    if isinstance(passages, list):
        for passage in passages:
            if not isinstance(passage, dict):
                continue
            for key in ("id", "title", "intro"):
                if isinstance(passage.get(key), str):
                    passage[key] = norm(passage[key])
            paragraphs = passage.get("paragraphs")
            if isinstance(paragraphs, list):
                for para in paragraphs:
                    if not isinstance(para, dict):
                        continue
                    for key in ("id", "label", "text"):
                        if isinstance(para.get(key), str):
                            para[key] = norm(para[key])

    groups = case.get("questionGroups")
    if isinstance(groups, list):
        for group in groups:
            if not isinstance(group, dict):
                continue
            for key in ("id", "range", "passageId", "type"):
                if isinstance(group.get(key), str):
                    group[key] = norm(group[key])
            if isinstance(group.get("instructions"), str):
                group["instructions"] = norm_lines(group["instructions"])
            group["options"] = normalize_options(group.get("options"))
            questions = group.get("questions")
            if isinstance(questions, list):
                for question in questions:
                    if not isinstance(question, dict):
                        continue
                    number = as_int(question.get("number"))
                    if number is not None:
                        question["number"] = number
                    for key in ("type", "stem", "analysis", "trap", "answerText", "confidence"):
                        if isinstance(question.get(key), str):
                            question[key] = norm(question[key])
                    answer = question.get("answer")
                    if isinstance(answer, list):
                        answer = " / ".join(norm(x) for x in answer if norm(x))
                    if isinstance(answer, str):
                        question["answer"] = norm(answer)
                    question["options"] = normalize_options(question.get("options"))
                    vocab = question.get("vocab")
                    if isinstance(vocab, list):
                        cleaned = []
                        for item in vocab:
                            if not isinstance(item, dict):
                                continue
                            cleaned.append({
                                "word": norm(item.get("word")),
                                "meaning": norm(item.get("meaning")),
                            })
                        question["vocab"] = cleaned
                    keywords = question.get("keywords")
                    if isinstance(keywords, list):
                        for keyword in keywords:
                            if not isinstance(keyword, dict):
                                continue
                            if isinstance(keyword.get("term"), str):
                                keyword["term"] = norm(keyword["term"])
                            occurrence = as_int(keyword.get("occurrence"))
                            if occurrence is not None:
                                keyword["occurrence"] = occurrence
                            anchor = keyword.get("anchor")
                            if isinstance(anchor, dict):
                                for key in ("paraId", "quote"):
                                    if isinstance(anchor.get(key), str):
                                        anchor[key] = norm(anchor[key])
    return case


def normalize_options(raw: Any) -> list[dict[str, str]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    for index, item in enumerate(raw):
        if isinstance(item, str):
            out.append({"label": chr(65 + index), "text": norm(item)})
        elif isinstance(item, dict):
            out.append({"label": norm(item.get("label")), "text": norm(item.get("text"))})
    return out


def validate_options(
    raw: Any,
    where: str,
    issues: Issues,
    *,
    auto_labels: bool,
    allow_markers: bool,
) -> list[dict[str, str]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        issues.error(where, "必须是数组。")
        return []
    out: list[dict[str, str]] = []
    labels: set[str] = set()
    for index, item in enumerate(raw):
        item_where = f"{where}[{index}]"
        if isinstance(item, str):
            label, text = chr(65 + index), norm(item)
            issues.warn(item_where, "选项被写成字符串，已自动补标签。建议使用 {label, text}。")
        elif isinstance(item, dict):
            label = norm(item.get("label"))
            text = norm(item.get("text"))
        else:
            issues.error(item_where, "必须是 {label, text} 对象。")
            continue
        if not label:
            if auto_labels:
                label = chr(65 + index)
                issues.warn(item_where, f"缺少 label，已自动使用 {label}。")
            else:
                issues.error(item_where, "缺少 label（如 A、B、i、ii）。")
                continue
        if not text:
            issues.error(item_where, "选项 text 不能为空。")
            continue
        if label in labels:
            issues.error(item_where, f"选项标签重复：{label}")
        labels.add(label)
        if not allow_markers and ("{{" in text or "}}" in text):
            issues.error(item_where, "共享选项/说明文字不支持 {{关键词}} 标记；关键词请写在题干或解析里。")
        out.append({"label": label, "text": text})
    return out


def marker_terms(text: Any) -> list[str]:
    if not isinstance(text, str):
        return []
    return [norm(m.group(1)) for m in MARKER_RE.finditer(text)]


def check_markers(
    text: Any,
    where: str,
    keyword_map: dict[str, dict[str, Any]],
    used: set[str],
    issues: Issues,
) -> None:
    if not isinstance(text, str) or not text:
        return
    for match in MARKER_RE.finditer(text):
        term = norm(match.group(1))
        if not term:
            issues.error(where, "关键词标记 {{}} 不能为空。")
            continue
        if term not in keyword_map:
            issues.error(
                where,
                f"{{{{{term}}}}} 没有对应的 keyword。请在 keywords 中定义 term=\"{term}\"，"
                "或检查是否拼写不一致。",
            )
        else:
            used.add(term)
    stripped = MARKER_RE.sub("", text)
    if "{{" in stripped or "}}" in stripped:
        issues.error(where, "关键词标记括号不完整，应使用 {{关键词}}。")


def best_match_hint(paragraph: str, quote: str) -> str:
    if not paragraph or not quote:
        return ""
    matcher = difflib.SequenceMatcher(None, paragraph, quote, autojunk=False)
    blocks = [b for b in matcher.get_matching_blocks() if b.size >= 6]
    if not blocks:
        return ""
    block = max(blocks, key=lambda b: b.size)
    start = max(0, block.a - 45)
    end = min(len(paragraph), block.a + block.size + 45)
    snippet = paragraph[start:end]
    if start > 0:
        snippet = "…" + snippet
    if end < len(paragraph):
        snippet = snippet + "…"
    return f"原文相近位置：{snippet}"


def validate_answer(
    question: dict[str, Any],
    question_type: str,
    options: list[dict[str, str]],
    where: str,
    issues: Issues,
) -> None:
    raw = question.get("answer")
    if isinstance(raw, list):
        answer = " / ".join(norm(x) for x in raw if norm(x))
        question["answer"] = answer
    elif isinstance(raw, str):
        answer = norm(raw)
        question["answer"] = answer
    else:
        issues.error(f"{where}.answer", "缺少答案（字符串，或字符串数组）。")
        return

    if not answer:
        issues.error(f"{where}.answer", "答案不能为空。")
        return

    if question_type == "true_false_not_given":
        mapped = {
            "T": "TRUE", "TRUE": "TRUE",
            "F": "FALSE", "FALSE": "FALSE",
            "NG": "NOT GIVEN", "NOTGIVEN": "NOT GIVEN", "NOT GIVEN": "NOT GIVEN",
        }
        upper = answer.upper()
        if upper in mapped:
            answer = mapped[upper]
            question["answer"] = answer
        else:
            issues.error(f"{where}.answer", f"判断题答案必须是 TRUE / FALSE / NOT GIVEN，当前为 {answer!r}。")
    elif question_type == "yes_no_not_given":
        mapped = {
            "Y": "YES", "YES": "YES",
            "N": "NO", "NO": "NO",
            "NG": "NOT GIVEN", "NOTGIVEN": "NOT GIVEN", "NOT GIVEN": "NOT GIVEN",
        }
        upper = answer.upper()
        if upper in mapped:
            answer = mapped[upper]
            question["answer"] = answer
        else:
            issues.error(f"{where}.answer", f"判断题答案必须是 YES / NO / NOT GIVEN，当前为 {answer!r}。")

    answer_text = MARKER_RE.sub(lambda m: m.group(1), norm(question.get("answerText")))
    if not answer_text and len(answer) <= 3:
        for option in options:
            if norm(option.get("label")).lower() == answer.lower():
                answer_text = MARKER_RE.sub(lambda m: m.group(1), norm(option.get("text")))
                break
    if answer_text:
        question["answerText"] = answer_text


def validate_case(case: Any, issues: Issues) -> dict[str, int]:
    stats = {"passages": 0, "paragraphs": 0, "groups": 0, "questions": 0, "keywords": 0}
    if not isinstance(case, dict):
        issues.error("$", "JSON 根节点必须是对象。")
        return stats

    if case.get("schemaVersion") != 1:
        issues.error("schemaVersion", "必须为 1。")

    meta = case.get("meta")
    if not isinstance(meta, dict):
        issues.error("meta", "必须是对象。")
        meta = {}
    title = norm(meta.get("title"))
    if not title:
        issues.error("meta.title", "不能为空。")

    answer_source = norm(meta.get("answerSource")) or "derived"
    if answer_source not in ANSWER_SOURCES:
        issues.warn("meta.answerSource", f"未知取值 {answer_source!r}，将按 derived 处理。")
        answer_source = "derived"
    meta["answerSource"] = answer_source

    passages = case.get("passages")
    if not isinstance(passages, list) or not passages:
        issues.error("passages", "至少需要一篇 Reading Passage。")
        passages = []

    passage_ids: set[str] = set()
    para_lookup: dict[tuple[str, str], dict[str, Any]] = {}
    first_passage_id: str | None = None

    for p_index, passage in enumerate(passages):
        where = f"passages[{p_index}]"
        if not isinstance(passage, dict):
            issues.error(where, "必须是对象。")
            continue
        passage_id = norm(passage.get("id"))
        if not passage_id:
            issues.error(f"{where}.id", "不能为空。")
            passage_id = f"passage-{p_index + 1}"
            passage["id"] = passage_id
        if passage_id in passage_ids:
            issues.error(f"{where}.id", f"passage id 重复：{passage_id}")
        passage_ids.add(passage_id)
        if first_passage_id is None:
            first_passage_id = passage_id

        number = as_int(passage.get("number"))
        if number is None:
            issues.warn(f"{where}.number", f"缺少 passage number，将显示为 {p_index + 1}。")
        if not norm(passage.get("title")):
            issues.warn(f"{where}.title", "文章标题为空。")

        paragraphs = passage.get("paragraphs")
        if not isinstance(paragraphs, list) or not paragraphs:
            issues.error(f"{where}.paragraphs", "至少需要一个段落。")
            continue

        para_ids: set[str] = set()
        labels: set[str] = set()
        for para_index, para in enumerate(paragraphs):
            para_where = f"{where}.paragraphs[{para_index}]"
            if not isinstance(para, dict):
                issues.error(para_where, "必须是对象。")
                continue
            para_id = norm(para.get("id"))
            if not para_id:
                issues.error(f"{para_where}.id", "不能为空，建议使用 A、B、C 或 p1、p2。")
                continue
            if para_id in para_ids:
                issues.error(f"{para_where}.id", f"段落 id 重复：{para_id}")
            para_ids.add(para_id)
            text = norm(para.get("text"))
            if not text:
                issues.error(f"{para_where}.text", "段落正文不能为空。")
            label = norm(para.get("label"))
            if label and label in labels:
                issues.warn(f"{para_where}.label", f"段落标签重复：{label}")
            if label:
                labels.add(label)
            para_lookup[(passage_id, para_id)] = para
            stats["paragraphs"] += 1
        stats["passages"] += 1

    groups = case.get("questionGroups")
    if not isinstance(groups, list) or not groups:
        issues.error("questionGroups", "至少需要一组题目。")
        groups = []

    group_ids: set[str] = set()
    question_numbers: list[int] = []
    number_set: set[int] = set()
    low_confidence = 0

    for g_index, group in enumerate(groups):
        where = f"questionGroups[{g_index}]"
        if not isinstance(group, dict):
            issues.error(where, "必须是对象。")
            continue
        group_id = norm(group.get("id"))
        if not group_id:
            issues.error(f"{where}.id", "不能为空。")
            group_id = f"group-{g_index + 1}"
            group["id"] = group_id
        if group_id in group_ids:
            issues.error(f"{where}.id", f"group id 重复：{group_id}")
        group_ids.add(group_id)

        passage_id = norm(group.get("passageId")) or first_passage_id
        if not passage_id:
            issues.error(f"{where}.passageId", "无法确定所属 passage。")
            continue
        if passage_id not in passage_ids:
            issues.error(f"{where}.passageId", f"找不到 passage id：{passage_id}")
            continue
        group["passageId"] = passage_id

        group_type = normalize_type(group.get("type"))
        group["type"] = group_type
        if not TYPE_LABELS.get(group_type):
            issues.warn(f"{where}.type", f"未知题型 {group_type!r}，将按原样显示。")

        if not norm(group.get("instructions")):
            issues.warn(f"{where}.instructions", "缺少题目说明。")

        group_options = validate_options(
            group.get("options"), f"{where}.options", issues,
            auto_labels=False, allow_markers=False,
        )
        group["options"] = group_options

        questions = group.get("questions")
        if not isinstance(questions, list) or not questions:
            issues.error(f"{where}.questions", "至少需要一道题。")
            continue

        for q_index, question in enumerate(questions):
            q_where = f"{where}.questions[{q_index}]"
            if not isinstance(question, dict):
                issues.error(q_where, "必须是对象。")
                continue

            number = as_int(question.get("number"))
            if number is None:
                issues.error(f"{q_where}.number", "题号必须是整数。")
                continue
            if number <= 0:
                issues.error(f"{q_where}.number", "题号必须大于 0。")
            if number in number_set:
                issues.error(f"{q_where}.number", f"题号重复：{number}")
            number_set.add(number)
            question_numbers.append(number)

            question_type = normalize_type(question.get("type") or group_type)
            question["type"] = question_type
            if not TYPE_LABELS.get(question_type):
                issues.warn(f"{q_where}.type", f"未知题型 {question_type!r}。")

            stem = norm(question.get("stem"))
            question["stem"] = stem
            if not stem:
                issues.error(f"{q_where}.stem", "题干不能为空。")

            analysis = norm(question.get("analysis"))
            question["analysis"] = analysis
            if not analysis:
                issues.error(f"{q_where}.analysis", "解析不能为空。")

            q_options = validate_options(
                question.get("options"), f"{q_where}.options", issues,
                auto_labels=True, allow_markers=True,
            )
            question["options"] = q_options
            effective_options = q_options or group_options

            validate_answer(question, question_type, effective_options, q_where, issues)

            confidence = norm(question.get("confidence")) or "high"
            if confidence not in {"high", "medium", "low"}:
                issues.warn(f"{q_where}.confidence", f"未知取值 {confidence!r}，按 high 处理。")
                confidence = "high"
            question["confidence"] = confidence
            if confidence != "high":
                low_confidence += 1

            keywords = question.get("keywords")
            if not isinstance(keywords, list) or not keywords:
                issues.error(f"{q_where}.keywords", "每道题至少需要 1 个关键词。")
                keywords = []
            if len(keywords) > 6:
                issues.warn(f"{q_where}.keywords", f"关键词有 {len(keywords)} 个，建议控制在 1–4 个。")

            keyword_map: dict[str, dict[str, Any]] = {}
            for k_index, keyword in enumerate(keywords):
                k_where = f"{q_where}.keywords[{k_index}]"
                if not isinstance(keyword, dict):
                    issues.error(k_where, "必须是对象。")
                    continue
                term = norm(keyword.get("term"))
                keyword["term"] = term
                if not term:
                    issues.error(f"{k_where}.term", "不能为空。")
                    continue
                if "{{" in term or "}}" in term:
                    issues.error(f"{k_where}.term", "关键词本身不能包含 {{ 或 }}。")
                if term in keyword_map:
                    issues.error(f"{k_where}.term", f"同一题内关键词重复：{term}")
                    continue
                if len(term) > 45:
                    issues.warn(f"{k_where}.term", "关键词偏长，建议不超过 45 个字符。")

                anchor = keyword.get("anchor")
                if not isinstance(anchor, dict):
                    issues.error(f"{k_where}.anchor", "必须是对象：{paraId, quote}。")
                    continue
                para_id = norm(anchor.get("paraId"))
                quote = norm(anchor.get("quote"))
                anchor["paraId"] = para_id
                anchor["quote"] = quote
                if not para_id:
                    issues.error(f"{k_where}.anchor.paraId", "不能为空（填段落 id，不是标签）。")
                    continue
                if not quote:
                    issues.error(f"{k_where}.anchor.quote", "不能为空。必须从原文逐字复制一句证据。")
                    continue

                para = para_lookup.get((passage_id, para_id))
                if para is None:
                    issues.error(
                        f"{k_where}.anchor.paraId",
                        f"在 passage {passage_id!r} 中找不到段落 id {para_id!r}。",
                    )
                    continue

                para_text = norm(para.get("text"))
                count = para_text.count(quote)
                if count == 0:
                    message = f"引文没有逐字出现在段落 {para_id!r} 中。请从 case.json 的段落正文复制。"
                    hint = best_match_hint(para_text, quote)
                    if hint:
                        message += "\n      " + hint
                    other = []
                    for (other_pid, other_para_id), other_para in para_lookup.items():
                        if other_pid != passage_id or other_para_id == para_id:
                            continue
                        if quote in norm(other_para.get("text")):
                            other.append(other_para_id)
                    if other:
                        message += f"\n      该句实际出现在段落：{', '.join(other)}；请修正 paraId。"
                    issues.error(f"{k_where}.anchor.quote", message)
                else:
                    occurrence = as_int(keyword.get("occurrence"))
                    if occurrence is None:
                        occurrence = 1
                    keyword["occurrence"] = occurrence
                    if occurrence < 1:
                        issues.error(f"{k_where}.occurrence", "必须 >= 1。")
                    elif occurrence > count:
                        issues.error(
                            f"{k_where}.occurrence",
                            f"引文在段落中只出现 {count} 次，occurrence={occurrence} 超出范围。",
                        )
                    elif count > 1 and "occurrence" not in keyword:
                        issues.warn(
                            f"{k_where}.anchor.quote",
                            f"引文在段落中出现 {count} 次，默认定位第 1 次；如不对请加 occurrence。",
                        )
                words = len(quote.split())
                if words > 60:
                    issues.warn(f"{k_where}.anchor.quote", f"证据句有 {words} 词，建议截取最小充分句（<= 60 词）。")
                if quote == para_text and words > 15:
                    issues.warn(f"{k_where}.anchor.quote", "证据句等于整段，定位范围过大，建议只保留关键句。")

                keyword_map[term] = keyword

            used_any: set[str] = set()
            used_in_analysis: set[str] = set()
            check_markers(question.get("stem"), f"{q_where}.stem", keyword_map, used_any, issues)
            check_markers(question.get("analysis"), f"{q_where}.analysis", keyword_map, used_any, issues)
            check_markers(question.get("trap"), f"{q_where}.trap", keyword_map, used_any, issues)
            for t_index, term in enumerate(marker_terms(question.get("analysis"))):
                if term in keyword_map:
                    used_in_analysis.add(term)
            for o_index, option in enumerate(question.get("options") or []):
                check_markers(option.get("text"), f"{q_where}.options[{o_index}]", keyword_map, used_any, issues)

            if keywords and not marker_terms(analysis):
                issues.error(
                    f"{q_where}.analysis",
                    "解析里没有任何 {{关键词}} 标记。请把定位词/同义替换写成 {{term}}。",
                )
            for term in keyword_map:
                if term not in used_in_analysis:
                    issues.error(
                        f"{q_where}.analysis",
                        f"关键词 {term!r} 没有出现在解析中。每个 keyword 都必须在 analysis 里用 {{{{{term}}}}} 标记。",
                    )
            if keyword_map and not used_any:
                issues.error(q_where, "关键词没有被任何字段使用。")

            stats["keywords"] += len(keyword_map)
            stats["questions"] += 1

        stats["groups"] += 1

    if question_numbers:
        if question_numbers != sorted(question_numbers):
            issues.warn("questionGroups", "题目顺序与题号不一致，HTML 将按 JSON 顺序显示。")
        expected = set(range(min(question_numbers), max(question_numbers) + 1))
        missing = sorted(expected - set(question_numbers))
        if missing:
            issues.warn("questionGroups", f"题号不连续，缺少：{', '.join(map(str, missing))}。")

    if low_confidence:
        issues.warn("$", f"有 {low_confidence} 道题标记为非 high 置信度，页面上会显示提示。")

    return stats


def render_kw_button(info: dict[str, Any], term: str) -> str:
    return (
        f'<button type="button" class="kw" data-kw="{esc(info["id"])}" '
        f'data-q="{esc(info["number"])}" data-para="{esc(info["para_dom"])}" '
        f'data-quote="{esc(info["quote"])}" data-occurrence="{esc(info["occurrence"])}" '
        f'data-para-label="{esc(info["para_label"])}" '
        f'aria-label="定位关键词：{esc(term)}（第 {esc(info["number"])} 题）" '
        f'title="点击定位到原文第 {esc(info["para_label"])} 段">{esc(term)}</button>'
    )


def render_marked(text: str, keyword_map: dict[str, dict[str, Any]]) -> str:
    if not text:
        return ""
    out: list[str] = []
    last = 0
    for match in MARKER_RE.finditer(text):
        out.append(esc(text[last:match.start()]))
        term = norm(match.group(1))
        info = keyword_map.get(term)
        if info:
            out.append(render_kw_button(info, term))
        else:
            out.append(esc(match.group(0)))
        last = match.end()
    out.append(esc(text[last:]))
    return "".join(out)


def render_options(
    options: list[dict[str, str]],
    shared: bool = False,
    keyword_map: dict[str, dict[str, Any]] | None = None,
) -> str:
    if not options:
        return ""
    cls = "shared-options" if shared else "options"
    items = []
    for option in options:
        text = option.get("text") or ""
        text_html = render_marked(text, keyword_map) if keyword_map and not shared else esc(text)
        items.append(
            f'<li><span class="opt-label">{esc(option.get("label"))}</span>'
            f'<span class="opt-text">{text_html}</span></li>'
        )
    return f'<ul class="{cls}">' + "".join(items) + "</ul>"


def render_passage(passage: dict[str, Any], p_index: int, para_dom: dict[tuple[str, str], str]) -> str:
    passage_id = norm(passage.get("id"))
    number = as_int(passage.get("number")) or (p_index + 1)
    title = norm(passage.get("title"))
    intro = norm(passage.get("intro"))
    blocks: list[str] = []
    blocks.append(f'<article class="passage" id="passage-{p_index + 1}" data-passage-id="{esc(passage_id)}">')
    blocks.append(f'<div class="passage-kicker">Reading Passage {esc(number)}</div>')
    if title:
        blocks.append(f'<h2 class="passage-title">{esc(title)}</h2>')
    if intro:
        blocks.append(f'<div class="passage-intro">{esc(intro)}</div>')
    blocks.append('<div class="passage-body">')
    for para_index, para in enumerate(passage.get("paragraphs") or []):
        para_id = norm(para.get("id"))
        dom_id = para_dom.get((passage_id, para_id), para_dom_id(p_index, para_index))
        label = norm(para.get("label"))
        label_html = f'<span class="para-label" aria-hidden="true">{esc(label)}</span>' if label else ""
        cls = "para" if label else "para no-label"
        blocks.append(
            f'<p class="{cls}" id="{dom_id}" data-para-id="{esc(para_id)}">'
            f'{label_html}<span class="para-text">{esc(norm(para.get("text")))}</span></p>'
        )
    blocks.append("</div></article>")
    return "\n".join(blocks)


def render_question(
    question: dict[str, Any],
    group: dict[str, Any],
    passage: dict[str, Any],
    p_index: int,
    q_index: int,
) -> str:
    number = as_int(question.get("number")) or (q_index + 1)
    group_type = normalize_type(group.get("type"))
    question_type = normalize_type(question.get("type") or group_type)
    stem = norm(question.get("stem"))
    analysis = norm(question.get("analysis"))
    answer = norm(question.get("answer"))
    answer_text = norm(question.get("answerText"))
    confidence = norm(question.get("confidence")) or "high"
    trap = norm(question.get("trap"))
    vocab = question.get("vocab") or []
    q_options = question.get("options") or []

    keyword_map: dict[str, dict[str, Any]] = {}
    review_items: list[dict[str, Any]] = []
    review_seen: set[tuple[str, str, int]] = set()
    for k_index, keyword in enumerate(question.get("keywords") or []):
        term = norm(keyword.get("term"))
        anchor = keyword.get("anchor") or {}
        para_id = norm(anchor.get("paraId"))
        quote = norm(anchor.get("quote"))
        occurrence = as_int(keyword.get("occurrence")) or 1
        para = None
        para_index = 0
        for i, candidate in enumerate(passage.get("paragraphs") or []):
            if norm(candidate.get("id")) == para_id:
                para = candidate
                para_index = i
                break
        dom = para_dom_id(p_index, para_index) if para is not None else ""
        label = norm(para.get("label")) if para else ""
        para_label = label or str(para_index + 1)
        keyword_map[term] = {
            "id": f"q{number}-k{k_index + 1}",
            "number": number,
            "para_dom": dom,
            "quote": quote,
            "occurrence": occurrence,
            "para_label": para_label,
        }
        review_key = (para_id, quote, occurrence)
        if para is not None and quote and review_key not in review_seen:
            review_seen.add(review_key)
            review_items.append({
                "para_dom": dom,
                "quote": quote,
                "occurrence": occurrence,
                "para_label": para_label,
            })

    qtype_html = ""
    if question_type != group_type:
        qtype_html = f'<span class="qtype">{esc(type_label(question_type))}</span>'

    blocks: list[str] = []
    blocks.append(f'<article class="qcard" id="q-{number}" data-question="{number}">')
    blocks.append('<div class="q-head">')
    blocks.append(f'<span class="qnum" aria-hidden="true">{esc(number)}</span>')
    blocks.append(f'<span class="qtype">Question {esc(number)}</span>')
    blocks.append(qtype_html)
    blocks.append("</div>")
    blocks.append(f'<div class="qstem"><p>{render_marked(stem, keyword_map)}</p></div>')
    if q_options:
        blocks.append(render_options(q_options, keyword_map=keyword_map))
    blocks.append('<div class="q-actions">')
    blocks.append(
        f'<button type="button" class="toggle-answer" aria-expanded="true" aria-controls="ans-{number}">'
        f'<span class="btn-label">收起解析</span></button>'
    )
    blocks.append("</div>")
    blocks.append(f'<div class="answer-box" id="ans-{number}">')

    confidence_html = ""
    if confidence == "medium":
        confidence_html = '<span class="confidence">推断 · 中</span>'
    elif confidence == "low":
        confidence_html = '<span class="confidence low">推断 · 低</span>'

    blocks.append('<div class="answer-line">')
    blocks.append('<span class="answer-tag">答案</span>')
    blocks.append(f'<strong class="answer-value">{esc(answer)}</strong>')
    if answer_text and answer_text.lower() != answer.lower():
        blocks.append(f'<span class="answer-note">{esc(answer_text)}</span>')
    blocks.append(confidence_html)
    blocks.append("</div>")

    if review_items:
        blocks.append('<div class="review">')
        blocks.append('<div class="review-label">原文回顾 <span>先读原文证据，再看解析</span></div>')
        for item in review_items:
            blocks.append(
                f'<div class="review-quote">'
                f'<span class="review-para">{esc(item["para_label"])}</span>'
                f'<span class="review-text" lang="en">{esc(item["quote"])}</span>'
                f'<button type="button" class="review-locate" '
                f'data-para="{esc(item["para_dom"])}" '
                f'data-quote="{esc(item["quote"])}" '
                f'data-occurrence="{esc(item["occurrence"])}" '
                f'data-para-label="{esc(item["para_label"])}" '
                f'aria-label="定位原文第 {esc(item["para_label"])} 段" '
                f'title="在左侧原文中定位">定位原文</button>'
                f'</div>'
            )
        blocks.append('</div>')

    blocks.append('<div class="analysis">')
    blocks.append('<div class="analysis-label">解析 <span>点击高亮关键词定位原文</span></div>')
    blocks.append(f"<p>{render_marked(analysis, keyword_map)}</p>")
    blocks.append("</div>")

    if trap:
        blocks.append(f'<div class="callout trap"><b>易错点</b>{render_marked(trap, keyword_map)}</div>')
    if vocab:
        vocab_items = []
        for item in vocab:
            word = norm(item.get("word"))
            meaning = norm(item.get("meaning"))
            if word:
                vocab_items.append(f"<li><em>{esc(word)}</em> — {esc(meaning)}</li>")
        if vocab_items:
            blocks.append('<div class="vocab"><b>词汇</b><ul>' + "".join(vocab_items) + "</ul></div>")

    blocks.append("</div></article>")
    return "\n".join(blocks)


def render_group(
    group: dict[str, Any],
    g_index: int,
    passages_by_id: dict[str, dict[str, Any]],
    passage_index_by_id: dict[str, int],
) -> str:
    passage_id = norm(group.get("passageId"))
    passage = passages_by_id.get(passage_id) or {}
    p_index = passage_index_by_id.get(passage_id, 0)
    passage_number = as_int(passage.get("number")) or (p_index + 1)
    group_type = normalize_type(group.get("type"))
    questions = group.get("questions") or []
    numbers = [as_int(q.get("number")) for q in questions if as_int(q.get("number")) is not None]
    if numbers:
        derived_range = f"Questions {min(numbers)}–{max(numbers)}"
        short_range = f"Q{min(numbers)}–{max(numbers)}"
    else:
        derived_range = "Questions"
        short_range = "Questions"
    range_text = norm(group.get("range")) or derived_range
    instructions = norm_lines(group.get("instructions"))
    group_options = group.get("options") or []

    blocks: list[str] = []
    blocks.append(f'<section class="qgroup" id="group-{g_index + 1}" data-group-id="{esc(norm(group.get("id")))}">')
    blocks.append('<div class="group-head">')
    blocks.append(f'<p class="group-range">{esc(range_text)}</p>')
    blocks.append(
        f'<p class="group-type">{esc(type_label(group_type))} · '
        f'<a class="passage-ref" href="#passage-{p_index + 1}">Passage {esc(passage_number)}</a></p>'
    )
    blocks.append("</div>")
    if instructions:
        lines = "".join(f"<p>{esc(line)}</p>" for line in instructions.split("\n") if line)
        blocks.append(f'<div class="instructions">{lines}</div>')
    if group_options:
        blocks.append(render_options(group_options, shared=True))
    for q_index, question in enumerate(questions):
        blocks.append(render_question(question, group, passage, p_index, q_index))
    blocks.append("</section>")
    return "\n".join(blocks)


def render_header(case: dict[str, Any], stats: dict[str, int]) -> str:
    meta = case.get("meta") or {}
    title = norm(meta.get("title")) or "IELTS Reading"
    subtitle = norm(meta.get("subtitle"))
    exam = norm(meta.get("exam")) or "IELTS Reading"
    time_limit = as_int(meta.get("timeLimit"))
    answer_source = norm(meta.get("answerSource")) or "derived"

    answer_label = {
        "official": "答案：官方答案页",
        "mixed": "答案：官方 + 推导",
        "derived": "答案：原文推导",
    }.get(answer_source, "答案：原文推导")
    answer_chip_class = "chip-accent" if answer_source == "official" else "chip"

    low_confidence = 0
    for group in case.get("questionGroups") or []:
        for question in group.get("questions") or []:
            if norm(question.get("confidence")) in {"medium", "low"}:
                low_confidence += 1

    chips = [
        f'<span class="chip chip-accent">{esc(exam)}</span>',
        f'<span class="chip">{stats["passages"]} 篇</span>',
        f'<span class="chip">{stats["questions"]} 题</span>',
        f'<span class="chip">{stats["keywords"]} 个关键词</span>',
        f'<span class="chip {answer_chip_class}">{esc(answer_label)}</span>',
    ]
    if time_limit:
        chips.append(f'<span class="chip chip-optional">建议 {esc(time_limit)} 分钟</span>')
    if low_confidence:
        chips.append(f'<span class="chip chip-warn chip-optional">{low_confidence} 题低置信</span>')

    sub_html = f'<p class="brand-sub">{esc(subtitle)}</p>' if subtitle else ""
    return f"""<header class="topbar">
  <div class="topbar-inner">
    <div class="brand">
      <div class="brand-mark" aria-hidden="true">R</div>
      <div class="brand-text">
        <h1 title="{esc(title)}">{esc(title)}</h1>
        {sub_html}
        <div class="meta-chips">{''.join(chips)}</div>
      </div>
    </div>
    <div class="top-actions">
      <button type="button" class="btn btn-primary" id="toggleAll"><span class="btn-label">收起全部解析</span></button>
      <button type="button" class="btn action-secondary" id="printBtn">打印 / PDF</button>
    </div>
  </div>
</header>"""


def render_footer(case: dict[str, Any]) -> str:
    meta = case.get("meta") or {}
    created = norm(meta.get("createdAt")) or datetime.now().strftime("%Y-%m-%d")
    source = norm(meta.get("source"))
    note = norm(meta.get("note"))
    answer_source = norm(meta.get("answerSource")) or "derived"
    lines = [f"<p>由 IELTS Reading HTML 生成 · {esc(created)} · v{BUILD_VERSION}</p>"]
    if source:
        lines.append(f"<p>来源：{esc(source)}</p>")
    if note:
        lines.append(f"<p>{esc(note)}</p>")
    if answer_source == "derived":
        lines.append("<p>答案与解析由模型根据原文推导，仅供学习参考；如有官方答案，请以官方为准。</p>")
    elif answer_source == "mixed":
        lines.append("<p>部分答案来自官方答案页，部分由原文推导；冲突处请以官方答案为准。</p>")
    lines.append('<p class="fine">原文与题目版权归原作者及出版方所有；本文件仅供个人学习使用，请勿用于商业传播。</p>')
    return '<footer class="site-footer">' + "".join(lines) + "</footer>"


def render_body(case: dict[str, Any], stats: dict[str, int]) -> str:
    passages = case.get("passages") or []
    groups = case.get("questionGroups") or []

    passages_by_id: dict[str, dict[str, Any]] = {}
    passage_index_by_id: dict[str, int] = {}
    para_dom: dict[tuple[str, str], str] = {}
    for p_index, passage in enumerate(passages):
        passage_id = norm(passage.get("id"))
        passages_by_id[passage_id] = passage
        passage_index_by_id[passage_id] = p_index
        for para_index, para in enumerate(passage.get("paragraphs") or []):
            para_dom[(passage_id, norm(para.get("id")))] = para_dom_id(p_index, para_index)

    passage_nav = ""
    if len(passages) > 1:
        links = "".join(
            f'<a href="#passage-{i + 1}">Passage {as_int(p.get("number")) or (i + 1)}</a>'
            for i, p in enumerate(passages)
        )
        passage_nav = f'<nav class="passage-nav" aria-label="文章切换"><span>Passage</span>{links}</nav>'

    group_nav_links = []
    for g_index, group in enumerate(groups):
        numbers = [
            as_int(q.get("number"))
            for q in (group.get("questions") or [])
            if as_int(q.get("number")) is not None
        ]
        label = f"Q{min(numbers)}–{max(numbers)}" if numbers else f"Group {g_index + 1}"
        group_nav_links.append(f'<a href="#group-{g_index + 1}">{esc(label)}</a>')
    group_nav = (
        '<nav class="group-nav" aria-label="题目组切换"><span>题目</span>'
        + "".join(group_nav_links)
        + "</nav>"
    )

    passage_html = "\n".join(
        render_passage(passage, p_index, para_dom) for p_index, passage in enumerate(passages)
    )
    group_html = "\n".join(
        render_group(group, g_index, passages_by_id, passage_index_by_id)
        for g_index, group in enumerate(groups)
    )

    answer_items = []
    for group in groups:
        for question in group.get("questions") or []:
            number = as_int(question.get("number"))
            if number is None:
                continue
            answer = norm(question.get("answer"))
            answer_text = norm(question.get("answerText"))
            title = answer_text if answer_text and answer_text.lower() != answer.lower() else ""
            title_attr = f' title="{esc(title)}"' if title else ""
            answer_items.append(
                f'<a class="answer-jump" href="#q-{number}" data-target="q-{number}"{title_attr}>'
                f'<span class="num">{esc(number)}</span><span class="ans">{esc(answer)}</span></a>'
            )
    answer_key = (
        '<details class="answer-key">'
        f'<summary>答案速查 <span>{stats["questions"]} 题 · 点击题号跳转</span></summary>'
        '<div class="answer-grid">' + "".join(answer_items) + "</div></details>"
    ) if answer_items else ""

    return f"""<main class="workspace" id="top">
  <section class="pane passage-pane" aria-label="阅读原文">
    <div class="pane-head">
      <div><h2>Reading Passage</h2><p>原文 · 逐字还原</p></div>
      <div class="pane-hint">点击解析中的关键词<br>精确高亮原文证据句</div>
    </div>
    {passage_nav}
    <div class="pane-inner">
      {passage_html}
    </div>
  </section>
  <section class="pane question-pane" aria-label="题目与解析">
    <div class="pane-head">
      <div><h2>Questions &amp; Analysis</h2><p>答案与解析默认展开 · 关键词可点击定位</p></div>
      <div class="pane-hint">{stats["questions"]} 题 · {stats["keywords"]} 个关键词</div>
    </div>
    {group_nav}
    {group_html}
    {answer_key}
  </section>
</main>
<button type="button" class="back-btn" id="backToAnalysis" hidden>← 返回解析</button>
<div class="toast" id="toast" role="status" aria-live="polite"></div>"""


def render_html(case: dict[str, Any], stats: dict[str, int]) -> str:
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"找不到模板：{TEMPLATE_PATH}")
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    meta = case.get("meta") or {}
    title = norm(meta.get("title")) or "IELTS Reading"
    subtitle = norm(meta.get("subtitle"))
    page_title = f"{title} · {subtitle}" if subtitle else f"{title} · IELTS Reading"

    page = (
        template
        .replace("<!--BUILD:TITLE-->", esc(page_title))
        .replace("<!--BUILD:HEADER-->", render_header(case, stats))
        .replace("<!--BUILD:BODY-->", render_body(case, stats))
        .replace("<!--BUILD:FOOTER-->", render_footer(case))
    )
    unresolved = [token for token in ("<!--BUILD:TITLE-->", "<!--BUILD:HEADER-->", "<!--BUILD:BODY-->", "<!--BUILD:FOOTER-->") if token in page]
    if unresolved:
        raise RuntimeError(f"模板占位符未替换：{', '.join(unresolved)}")
    return page


def print_issues(issues: Issues) -> None:
    for level, where, message in issues.items[:150]:
        print(f"[{level}] {where}: {message}")
    if len(issues.items) > 150:
        print(f"… 还有 {len(issues.items) - 150} 条问题未显示。")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Validate an IELTS reading case JSON and build an interactive single-file HTML."
    )
    parser.add_argument("case", help="Path to case.json")
    parser.add_argument("-o", "--out", help="Output HTML path (default: index.html next to case.json)")
    parser.add_argument("--check", action="store_true", help="Validate only; do not write HTML")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    parser.add_argument("--open", action="store_true", help="Open the generated HTML in the default browser")
    args = parser.parse_args(argv)

    case_path = Path(args.case).expanduser().resolve()
    if not case_path.exists():
        print(f"[ERROR] 找不到文件：{case_path}")
        return 2
    try:
        raw_case = load_case(case_path)
    except json.JSONDecodeError as exc:
        print(f"[ERROR] JSON 解析失败：第 {exc.lineno} 行第 {exc.colno} 列：{exc.msg}")
        return 2
    except OSError as exc:
        print(f"[ERROR] 读取失败：{exc}")
        return 2

    case = normalize_case(raw_case)
    issues = Issues()
    stats = validate_case(case, issues)
    print_issues(issues)

    errors = issues.errors
    warnings = issues.warnings
    print(
        f"\n统计：{stats['passages']} 篇 / {stats['paragraphs']} 段 / "
        f"{stats['groups']} 组 / {stats['questions']} 题 / {stats['keywords']} 个关键词"
    )
    print(f"校验：{len(errors)} 个错误，{len(warnings)} 个警告")

    if errors:
        print("结果：FAILED。请修复 ERROR 后重试。")
        return 1
    if args.strict and warnings:
        print("结果：FAILED（--strict 将警告视为错误）。")
        return 1
    if args.check:
        print("结果：OK（仅校验，未生成 HTML）。")
        return 0

    out_path = Path(args.out).expanduser().resolve() if args.out else case_path.with_name("index.html")
    try:
        html_text = render_html(case, stats)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html_text, encoding="utf-8", newline="\n")
    except (OSError, RuntimeError, FileNotFoundError) as exc:
        print(f"[ERROR] 生成失败：{exc}")
        return 2

    size_kb = out_path.stat().st_size / 1024
    print(f"结果：OK。已生成 {out_path}（{size_kb:.1f} KB）")
    if args.open:
        webbrowser.open(out_path.as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
