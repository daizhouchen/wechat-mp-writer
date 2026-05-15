#!/usr/bin/env python3
"""
v2 质量闸门（量化扫描器）

扫 article.json + 最终 HTML，输出 20+ 项硬指标的 pass/fail 报告，
并把结果写回 article.json.compliance_report 和 source_report.

使用：
  python quality_check.py check --article article.json --html article.html
  python quality_check.py check --article article.json --html article.html --history ~/.wechat-history.json
  python quality_check.py compute-source-report --article article.json   # 仅算 source_report

设计原则：
  - 不依赖第三方包
  - 终端彩色输出 + JSON 报告双形态
  - 每项硬指标都有：name / value / threshold / pass / note / suggestion
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# 终端着色（无依赖）
# ---------------------------------------------------------------------------

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def _color(text, code):
    if not sys.stdout.isatty():
        return text
    return f"{code}{text}{RESET}"


# ---------------------------------------------------------------------------
# 加载 v1 兼容的 compliance_check 词库
# ---------------------------------------------------------------------------

try:
    sys.path.insert(0, str(Path(__file__).parent))
    from compliance_check import ABSOLUTE_TERMS, EXAGGERATION_TERMS, MEDICAL_FINANCE_TERMS
except Exception:
    ABSOLUTE_TERMS = []
    EXAGGERATION_TERMS = []
    MEDICAL_FINANCE_TERMS = []


# AI 套话词库（v2 红线 6/9/10 的检测）
AI_CLICHES = [
    "在数字化时代", "随着.*的.*发展", "在.*快速发展", "众所周知",
    "赋能", "底层逻辑", "顶层设计", "闭环", "抓手", "颗粒度",
    "让我们一起", "接下来我将", "综上所述", "总而言之",
    "拥抱.*未来", "迈向新阶段", "开启.*新篇章",
]

# 框架名（红线 6）
FRAMEWORK_NAMES = [
    "事实层", "机制层", "观点层",
    "波特五力", "马斯洛", "SWOT", "PEST", "BCG 矩阵",
    "OKR", "KPI", "MECE", "STAR 法则",
]

# 开场白综合症（红线 9，正文第一段必扫）
OPENING_CLICHES = [
    r"在.*[时代代]",
    r"随着.*的.*发展",
    r"今天.*想.*[聊谈讲]",
    r"众所周知",
    r"近年来",
    r"在当今",
]

# 总结八股（红线 10，文末段必扫）
ENDING_CLICHES = [
    "综上所述", "总而言之", "总的来说",
    "让我们.*[一起共同]", "拥抱.*未来",
    "迈向新阶段", "开启.*新篇章",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def html_to_plain(html: str) -> str:
    """剥 HTML 标签返回纯文本。"""
    no_script = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    no_style = re.sub(r"<style[^>]*>.*?</style>", " ", no_script, flags=re.DOTALL | re.IGNORECASE)
    return re.sub(r"<[^>]+>", " ", no_style)


def count_chinese_chars(text: str) -> int:
    return sum(1 for ch in text if "一" <= ch <= "鿿")


def count_mixed_reading_length(text: str) -> int:
    """v2.1 混合阅读量算法：中文字符 × 1 + 英文 token × 0.5
    替代纯中文计数——避免低估"OpenAI Anthropic Sam Altman"等大量英文实体的科技文。
    """
    zh = sum(1 for ch in text if "一" <= ch <= "鿿")
    en_tokens = len(re.findall(r"[A-Za-z]+", text))
    return zh + int(en_tokens * 0.5)


def utf8_byte_size(s: str) -> int:
    return len(s.encode("utf-8"))


# v2.1 AI 痕迹清单（成稿 HTML 不应出现）
AI_TRACE_PATTERNS = [
    r"信任度报告", r"置信度评分", r"置信度.{0,3}星",
    r"来源透明度", r"A\s*占比.*?%",
    r"图\s*[:：].{0,30}(Wikimedia|CC[\-\s]?BY|来源)",
    r"未核证", r"据.{0,8}推算",
    r"fact-\d+", r"sr-\d+", r"img-\w+",
    r"由\s*claude\s*生成", r"AI\s*工具.{0,10}产出",
    r"vision_review", r"source_report", r"compliance_report",
    r"★{2,}",  # 信任度星
]


def has_concrete_noun(text: str) -> bool:
    """段落里是否有具体名词（人/年份/数字/英文实体名）。"""
    if re.search(r"\d{4}", text):  # 年份
        return True
    if re.search(r"\d", text):  # 任何数字
        return True
    if re.search(r"[A-Z][a-zA-Z]+", text):  # 英文实体名
        return True
    if re.search(r"[一-鿿]{2,4}(?:公司|集团|科技|实验室|研究院)", text):
        return True
    return False


# ---------------------------------------------------------------------------
# 检查项
# ---------------------------------------------------------------------------

def check_a_grade_facts(article: dict) -> dict:
    facts = article.get("facts", [])
    a_count = sum(1 for f in facts if f.get("grade") == "A")
    return _build("a_grade_facts_count", a_count, ">=5", a_count >= 5,
                  note=f"A 级事实 {a_count} 条",
                  suggestion="再搜集 ≥1 条官方源/论文/财报数据")


def check_d_grade_ratio(article: dict) -> dict:
    facts = article.get("facts", [])
    if not facts:
        return _build("d_grade_ratio", 0, "<30%", True, note="无 facts，跳过")
    d_count = sum(1 for f in facts if f.get("grade") == "D")
    pct = round(d_count / len(facts) * 100, 1)
    return _build("d_grade_ratio", pct, "<30%", pct < 30,
                  note=f"D 级（模型推断）占比 {pct}%",
                  suggestion="过多模型推断会被判低星，补外部源支撑或删除")


def check_ai_cliches(article: dict, plain: str) -> dict:
    hits = []
    for pat in AI_CLICHES:
        for m in re.finditer(pat, plain):
            hits.append(m.group(0))
    return _build("ai_cliche_count", len(hits), "==0", len(hits) == 0,
                  note=f"AI 套话命中 {len(hits)} 处" + (f"：{hits[:3]}" if hits else ""),
                  suggestion="改用具体事实 / 场景 / 引语替代")


def check_framework_names(plain: str) -> dict:
    hits = [name for name in FRAMEWORK_NAMES if name in plain]
    return _build("framework_name_leak", len(hits), "==0", len(hits) == 0,
                  note=f"框架名泄漏 {hits}" if hits else "无泄漏",
                  suggestion="框架在脑不在纸——把框架名删掉，只留洞察")


def check_opening_clichés(article: dict) -> dict:
    sections = article.get("draft_sections", [])
    if not sections:
        return _build("opening_cliche", "n/a", "==0", True, note="无章节")
    first_html = sections[0].get("html", "")
    first_text = html_to_plain(first_html).strip()[:200]
    hits = [pat for pat in OPENING_CLICHES if re.search(pat, first_text)]
    return _build("opening_cliche", len(hits), "==0", len(hits) == 0,
                  note=f"开场白综合症 {hits}" if hits else "首段干净",
                  suggestion="正文第一句改成具体事实/场景/数字/引语")


def check_ending_clichés(article: dict) -> dict:
    sections = article.get("draft_sections", [])
    if not sections:
        return _build("ending_cliche", "n/a", "==0", True, note="无章节")
    last_html = sections[-1].get("html", "")
    last_text = html_to_plain(last_html).strip()[-300:]
    hits = [pat for pat in ENDING_CLICHES if re.search(pat, last_text)]
    return _build("ending_cliche", len(hits), "==0", len(hits) == 0,
                  note=f"总结八股 {hits}" if hits else "文末干净",
                  suggestion="改成具体下一步/反问/留白/CTA")


def check_concrete_noun_per_para(article: dict) -> dict:
    sections = article.get("draft_sections", [])
    bad_paras = 0
    total_paras = 0
    for sec in sections:
        plain = html_to_plain(sec.get("html", ""))
        paras = [p.strip() for p in re.split(r"\n\s*\n", plain) if p.strip() and len(p.strip()) > 30]
        for p in paras:
            total_paras += 1
            if not has_concrete_noun(p):
                bad_paras += 1
    if total_paras == 0:
        return _build("concrete_noun_per_para", "n/a", ">=80%", True, note="无段落")
    coverage = round((total_paras - bad_paras) / total_paras * 100, 1)
    return _build("concrete_noun_per_para", coverage, ">=80%", coverage >= 80,
                  note=f"含具体名词的段落 {coverage}%（模糊段 {bad_paras}/{total_paras}）",
                  suggestion="把'某公司/很多人/一些数据' 改成具体人名/公司/数字")


def check_word_count(article: dict, plain: str) -> dict:
    """v2.1 改用混合阅读量算法（中文 + 英文 token × 0.5）"""
    wc = count_mixed_reading_length(plain)
    budget = (article.get("meta") or {}).get("word_budget") or {}
    target_min = budget.get("min", 3500)
    target_max = budget.get("max", 5500)
    hard_limit = 8000  # v2.1 硬上限上调
    in_range = target_min <= wc <= target_max
    note = f"阅读量 {wc}（budget {target_min}-{target_max}，中英混合算法）"
    if wc > hard_limit:
        return _build("word_count", wc, f"<={hard_limit}", False,
                      note=f"{note} · 超过 {hard_limit} 硬上限",
                      suggestion=f"拆成系列文，单篇控制在 {hard_limit} 字内")
    return _build("word_count", wc, f"{target_min}-{target_max}", in_range,
                  note=note,
                  suggestion="按 budget 增删段落（深稿建议 medium 3500-5500）")


def check_digest_byte_size(article: dict) -> dict:
    """v2.1 新增：微信 digest 上限 120 字节（不是 120 字符），中文 ~40 字"""
    digest = (article.get("meta") or {}).get("digest", "") or ""
    bytes_n = utf8_byte_size(digest)
    return _build("digest_byte_size", bytes_n, "<=120", bytes_n <= 120,
                  note=f"摘要 {bytes_n} 字节（{len(digest)} 字符）",
                  suggestion="压到 ~40 中文字符（每个汉字 3 字节，120/3=40）")


def check_material_utilization(article: dict) -> dict:
    """v2.1 新增：素材榨干率 — 搜了的 search_results 至少 80% 在 facts 被引用"""
    sr = article.get("search_results", [])
    facts = article.get("facts", [])
    if not sr:
        return _build("material_utilization", "n/a", ">=80%", True, note="无 search_results")

    cited = set()
    for f in facts:
        for ref in f.get("source_ref", []):
            cited.add(ref)

    used = sum(1 for s in sr if s.get("id") in cited)
    pct = round(used / len(sr) * 100, 1)
    passed = pct >= 80
    sev = "fail" if pct < 40 else ("warn" if pct < 60 else "ok")
    return _build("material_utilization", f"{pct}%", ">=80%", passed,
                  note=f"搜 {len(sr)} 条，引用 {used} 条（{sev}）",
                  suggestion="补 facts 引用未用素材，或删除未用 search_results")


# v2.1.2 主题 → 风格匹配表
TOPIC_STYLE_MAPPING = {
    "tech_deep":  ["横评", "对比", "评测", "数据", "榜单", "估值", "薪资", "benchmark", "vs"],
    "cultural":   ["故事", "人物", "创始人", "离开", "创业", "反思", "批评", "文化", "价值观", "押注", "天花板", "讲故事"],
    "finance":    ["财报", "估值", "监管", "政策", "上市", "财经", "投行", "央行", "融资", "IPO"],
    "tutorial":   ["教程", "上手", "指南", "How-to", "工具", "清单", "步骤", "Top", "实操"],
    "retrospect": ["盘点", "年终", "演变", "历史", "周年", "大事件", "编年", "回顾"],
}


def check_style_topic_fit(article: dict) -> dict:
    """v2.1.2 新增：当前 style_preset 是否匹配主题关键词"""
    meta = article.get("meta") or {}
    layout = meta.get("layout_variant") or {}

    # 当前用的 style：由 (accent_color, h2_decoration, cover_template) 推断 preset
    accent = layout.get("accent_color", "")
    h2_dec = layout.get("h2_decoration", "")
    inferred_preset = None
    presets = {
        "tech_deep":  ("#7a5500", "chapter_number"),
        "cultural":   ("#8b3a3a", "classic_chinese_serial"),
        "finance":    ("#1e4d8b", "block_left_bar"),
        "tutorial":   ("#5c4a3a", "number_prefix"),
        "retrospect": ("#c62828", "dash_decoration"),
    }
    for name, (acc, h2) in presets.items():
        if accent == acc or h2_dec == h2:
            inferred_preset = name
            break

    # 主题文本：title + subtitle + chosen_angle
    title = meta.get("title", "")
    subtitle = meta.get("subtitle", "")
    angle = (article.get("chosen_angle") or {}).get("ref", "")
    angles = {a.get("id"): a.get("angle_text", "") for a in article.get("angles", [])}
    angle_text = angles.get(angle, "")
    topic_text = f"{title} {subtitle} {angle_text}"

    # 主题命中哪些 preset
    matched_presets = []
    for preset, kws in TOPIC_STYLE_MAPPING.items():
        for kw in kws:
            if kw in topic_text:
                matched_presets.append(preset)
                break

    if not matched_presets:
        return _build("style_topic_fit", "n/a", "topic ambiguous", True,
                      note="主题不明确，跳过适配检查（用 profile.style_default）")

    if not inferred_preset:
        return _build("style_topic_fit", "unknown", "set style_preset", False,
                      note="未设 layout_variant.accent_color，无法推断 preset",
                      suggestion="按 SKILL.md 主题适配章节选 5 preset 之一")

    if inferred_preset in matched_presets:
        return _build("style_topic_fit", inferred_preset, f"in {matched_presets}", True,
                      note=f"风格 {inferred_preset} 匹配主题命中的 preset {matched_presets}")

    return _build("style_topic_fit", inferred_preset, f"should be in {matched_presets}", False,
                  note=f"风格 {inferred_preset} 与主题不匹配——主题命中 {matched_presets}",
                  suggestion=f"换风格到 {matched_presets[0]}（详见 SKILL.md 主题→风格适配章节）")


def check_ai_traces(plain: str) -> dict:
    """v2.1 新增：扫成稿 HTML 里有无 AI 痕迹"""
    hits = []
    for pat in AI_TRACE_PATTERNS:
        for m in re.finditer(pat, plain):
            hits.append(m.group(0)[:30])
    uniq = list(dict.fromkeys(hits))[:5]  # 去重 + 截前 5
    return _build("ai_traces", len(hits), "==0", len(hits) == 0,
                  note=f"AI 痕迹命中 {len(hits)} 处" + (f"：{uniq}" if uniq else ""),
                  suggestion="把信任度报告/图来源标注/内部 ID/AI tagline 全部从 HTML 移除（只留在 article.json 内部）")


def check_layout_variety(article: dict, history_path: str | None) -> dict:
    meta = article.get("meta") or {}
    variant = (meta.get("layout_variant") or {}).get("id")
    recent = meta.get("recent_layouts", [])

    if not variant:
        return _build("layout_variety", "missing", "set", False,
                      note="未设 layout_variant.id",
                      suggestion="先选骨架，见 layout-variants.md §4")

    # 也尝试从历史文件读
    if history_path:
        p = Path(history_path).expanduser()
        if p.exists():
            try:
                hist = json.loads(p.read_text(encoding="utf-8"))
                recent = [r.get("variant_id") for r in hist.get("recent", [])][:5]
            except Exception:
                pass

    if not recent:
        return _build("layout_variety", variant, "no recent history", True,
                      note=f"用 {variant}（无历史）")

    last_3 = recent[:3]
    if variant in last_3:
        return _build("layout_variety", variant, "not in last 3", False,
                      note=f"{variant} 已在近 3 篇出现：{last_3}",
                      suggestion="换骨架，见 layout-variants.md §2 防重复规则")

    same_in_5 = recent[:5].count(variant)
    if same_in_5 >= 2:
        return _build("layout_variety", variant, "<=1 in last 5", False,
                      note=f"{variant} 近 5 篇出现 {same_in_5} 次",
                      suggestion="强烈建议换其他骨架")

    return _build("layout_variety", variant, "ok", True,
                  note=f"{variant} 与近 5 篇均不同")


def check_image_vision_pass(article: dict) -> dict:
    plan = article.get("images_plan", [])
    if not plan:
        return _build("image_vision_pass_rate", "n/a", "100%", True, note="无配图")
    chosen_with_review = [
        p for p in plan
        if p.get("vision_review", {}).get("verdict") == "pass"
        or p.get("fallback_used")
    ]
    pct = round(len(chosen_with_review) / len(plan) * 100, 1)
    return _build("image_vision_pass_rate", pct, "==100%", pct == 100,
                  note=f"通过 vision 审查或已 fallback：{len(chosen_with_review)}/{len(plan)}",
                  suggestion="未审查的图必须先跑 image_vision_review.py 或走 fallback")


def check_image_alt_text(article: dict) -> dict:
    plan = article.get("images_plan", [])
    if not plan:
        return _build("image_alt_text", "n/a", "all set", True, note="无配图")
    missing = [p for p in plan if not p.get("alt_text")]
    return _build("image_alt_text", len(missing), "==0", len(missing) == 0,
                  note=f"缺 alt 的图 {len(missing)} 张",
                  suggestion="每张图必须有 alt_text（无障碍 + SEO）")


def check_cover_aspect(article: dict) -> dict:
    plan = article.get("images_plan", [])
    cover = next((p for p in plan if p.get("role") == "cover"), None)
    if not cover:
        return _build("cover_aspect", "missing", "2.35:1", False,
                      note="无封面图",
                      suggestion="必须配 1 张封面图，比例 2.35:1")
    return _build("cover_aspect", "exists", "2.35:1", True,
                  note="封面已配（比例由 image_search.py 裁切保证）")


def check_image_text_ratio(article: dict, plain: str) -> dict:
    wc = count_chinese_chars(plain)
    plan = article.get("images_plan", [])
    inline_count = sum(1 for p in plan if p.get("role") == "inline")
    if inline_count == 0:
        return _build("image_text_ratio", 0, "1 image / 300-500 chars", False,
                      note="无正文图",
                      suggestion="≥1500 字文章至少配 3 张正文图")
    chars_per_image = wc // max(1, inline_count)
    in_range = 200 <= chars_per_image <= 700
    return _build("image_text_ratio", chars_per_image, "300-500 chars/img", in_range,
                  note=f"每图 {chars_per_image} 字（图 {inline_count} 张）",
                  suggestion="过密 → 删图；过疏 → 补图")


def check_facts_cited_per_section(article: dict) -> dict:
    sections = article.get("draft_sections", [])
    bad = []
    for sec in sections:
        cited = sec.get("facts_cited", [])
        if len(cited) < 2:
            bad.append(sec.get("section_id"))
    return _build("facts_cited_per_section", len(bad), "<=1 sections with <2 facts",
                  len(bad) <= 1,
                  note=f"{len(bad)} 个章节 facts_cited < 2：{bad[:3]}",
                  suggestion="每段至少 cite 2 条 facts，机制段更要 cite ≥3 条")


def check_compliance_legacy(plain: str) -> dict:
    """v1 旧词库扫描，向后兼容。"""
    hits = []
    for term in ABSOLUTE_TERMS + EXAGGERATION_TERMS + MEDICAL_FINANCE_TERMS:
        if term in plain:
            hits.append(term)
    return _build("compliance_legacy", len(hits), "==0", len(hits) == 0,
                  note=f"v1 合规词库命中 {len(hits)} 处" + (f"：{hits[:5]}" if hits else ""),
                  suggestion="改写或删除（广告法/极限词/夸大）")


def check_external_links(html: str) -> dict:
    """微信公众号正文不能外链跳转。"""
    bad = []
    for m in re.finditer(r'href="(https?://[^"]+)"', html):
        url = m.group(1)
        if "mp.weixin.qq.com" in url:
            continue
        bad.append(url)
    return _build("external_links", len(bad), "==0", len(bad) == 0,
                  note=f"非公众号外链 {len(bad)} 处" + (f"：{bad[:2]}" if bad else ""),
                  suggestion="改成纯文本 URL 或公众号互链")


def check_emoji_in_body(plain: str) -> dict:
    emoji_pat = re.compile(
        "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F0FF]"
    )
    hits = emoji_pat.findall(plain)
    return _build("emoji_in_body", len(hits), "==0", len(hits) == 0,
                  note=f"emoji 命中 {len(hits)}",
                  suggestion="正文不允许 emoji（v1 铁律 1）")


def check_first_screen_word_count(article: dict) -> dict:
    sections = article.get("draft_sections", [])
    if not sections:
        return _build("first_screen_words", 0, "<=300", True, note="无章节")
    first = sections[0]
    plain = html_to_plain(first.get("html", ""))
    wc = count_chinese_chars(plain)
    return _build("first_screen_words", wc, "<=300", wc <= 300,
                  note=f"首屏字数 {wc}",
                  suggestion="首屏字数应 ≤ 300，决定打开率")


def check_h2_count(html: str, article: dict) -> dict:
    h2_count = len(re.findall(r"<h2", html, re.IGNORECASE))
    sections_count = len(article.get("draft_sections", []))
    expect_min = max(2, sections_count - 1)
    expect_max = sections_count + 1
    in_range = expect_min <= h2_count <= expect_max
    return _build("h2_count", h2_count, f"{expect_min}-{expect_max}", in_range,
                  note=f"H2 数 {h2_count}（章节数 {sections_count}）",
                  suggestion="H2 数应与章节数对齐")


def check_dissent_or_limitation(plain: str) -> dict:
    """红线 8：每篇 ≥1 处反方观点或局限承认"""
    patterns = [
        r"[但但是然而不过][，,]",
        r"也.{0,5}指出",
        r"边界.{0,5}是",
        r"局限.{0,5}是",
        r"短板",
        r"缺点",
        r"反方",
        r"caveat",
    ]
    matched = sum(1 for pat in patterns if re.search(pat, plain))
    return _build("dissent_or_limitation", matched, ">=1", matched >= 1,
                  note=f"反方/局限提示 {matched} 处",
                  suggestion="必须 ≥1 处反方观点或局限承认（红线 8）")


def check_title_candidates(article: dict) -> dict:
    cands = (article.get("meta") or {}).get("title_candidates", [])
    return _build("title_candidates", len(cands), ">=3", len(cands) >= 3,
                  note=f"标题候选 {len(cands)} 个",
                  suggestion="必须 ≥3 个候选，按 9 分制选最高")


# ---------------------------------------------------------------------------
# Source report
# ---------------------------------------------------------------------------

def compute_source_report(article: dict) -> dict:
    facts = article.get("facts", [])
    total = len(facts)
    by_grade = {"A": 0, "B": 0, "C": 0, "D": 0}
    for f in facts:
        g = f.get("grade", "D")
        by_grade[g] = by_grade.get(g, 0) + 1
    pct = {g: round(by_grade[g] / total * 100, 1) if total else 0 for g in by_grade}

    # 星级（与 source-grading.md §5 一致）
    a_pct = pct["A"]
    d_pct = pct["D"]
    if a_pct >= 60 and d_pct == 0:
        stars = "★★★★★"
        rules = f"A 占比 {a_pct}% (≥60%) + D = 0% → 5 星"
    elif a_pct >= 50 and d_pct < 15:
        stars = "★★★★"
        rules = f"A 占比 {a_pct}% (≥50%) + D 占比 {d_pct}% (<15%) → 4 星"
    elif a_pct >= 30:
        stars = "★★★"
        rules = f"A 占比 {a_pct}% (≥30%) → 3 星"
    elif d_pct >= 30:
        stars = "★"
        rules = f"D 占比 {d_pct}% (≥30%) → 1 星（参考价值有限）"
    else:
        stars = "★★"
        rules = f"未达高星级阈值 → 2 星"

    return {
        "total_facts": total,
        "by_grade": by_grade,
        "by_grade_pct": pct,
        "confidence_stars": stars,
        "confidence_rules": rules,
        "limitations": (article.get("source_report") or {}).get("limitations", []),
    }


# ---------------------------------------------------------------------------
# 执行 + 输出
# ---------------------------------------------------------------------------

def _build(name, value, threshold, passed, note="", suggestion=""):
    return {
        "name": name,
        "value": value,
        "threshold": threshold,
        "pass": passed,
        "note": note,
        "suggestion": suggestion,
    }


CHECKS_REGISTRY = [
    ("a_grade_facts", lambda a, h, p, hist: check_a_grade_facts(a)),
    ("d_grade_ratio", lambda a, h, p, hist: check_d_grade_ratio(a)),
    ("material_utilization", lambda a, h, p, hist: check_material_utilization(a)),  # v2.1 新增
    ("ai_cliches", lambda a, h, p, hist: check_ai_cliches(a, p)),
    ("ai_traces", lambda a, h, p, hist: check_ai_traces(p)),  # v2.1 新增
    ("style_topic_fit", lambda a, h, p, hist: check_style_topic_fit(a)),  # v2.1.2 新增
    ("framework_names", lambda a, h, p, hist: check_framework_names(p)),
    ("opening_cliches", lambda a, h, p, hist: check_opening_clichés(a)),
    ("ending_cliches", lambda a, h, p, hist: check_ending_clichés(a)),
    ("concrete_noun", lambda a, h, p, hist: check_concrete_noun_per_para(a)),
    ("word_count", lambda a, h, p, hist: check_word_count(a, p)),  # v2.1 改混合算法
    ("digest_byte_size", lambda a, h, p, hist: check_digest_byte_size(a)),  # v2.1 新增
    ("layout_variety", lambda a, h, p, hist: check_layout_variety(a, hist)),
    ("vision_pass", lambda a, h, p, hist: check_image_vision_pass(a)),
    ("alt_text", lambda a, h, p, hist: check_image_alt_text(a)),
    ("cover_aspect", lambda a, h, p, hist: check_cover_aspect(a)),
    ("image_text_ratio", lambda a, h, p, hist: check_image_text_ratio(a, p)),
    ("facts_cited", lambda a, h, p, hist: check_facts_cited_per_section(a)),
    ("compliance_legacy", lambda a, h, p, hist: check_compliance_legacy(p)),
    ("external_links", lambda a, h, p, hist: check_external_links(h)),
    ("emoji_body", lambda a, h, p, hist: check_emoji_in_body(p)),
    ("first_screen", lambda a, h, p, hist: check_first_screen_word_count(a)),
    ("h2_count", lambda a, h, p, hist: check_h2_count(h, a)),
    ("dissent", lambda a, h, p, hist: check_dissent_or_limitation(p)),
    ("title_candidates", lambda a, h, p, hist: check_title_candidates(a)),
]


def run_all_checks(article_path: str, html_path: str | None, history_path: str | None):
    article = json.loads(Path(article_path).read_text(encoding="utf-8"))
    html = ""
    if html_path and Path(html_path).exists():
        html = Path(html_path).read_text(encoding="utf-8")
    plain = html_to_plain(html) if html else " ".join(
        html_to_plain(s.get("html", "")) for s in article.get("draft_sections", [])
    )

    results = []
    for cid, fn in CHECKS_REGISTRY:
        try:
            r = fn(article, html, plain, history_path)
            results.append(r)
        except Exception as e:
            results.append(_build(cid, "error", "n/a", False, note=str(e)))

    passed = sum(1 for r in results if r["pass"])
    failed = len(results) - passed

    # source_report 同步算
    src_report = compute_source_report(article)

    # 写回
    article["compliance_report"] = {
        "passed": passed,
        "failed": failed,
        "checks": results,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    article["source_report"] = src_report

    Path(article_path).write_text(
        json.dumps(article, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return results, src_report, passed, failed


def print_report(results, src_report, passed, failed):
    print()
    print(_color(f"=== Quality Gate Report ({passed} pass / {failed} fail) ===", BOLD))
    print()

    for r in results:
        marker = _color("PASS", GREEN) if r["pass"] else _color("FAIL", RED)
        print(f"  [{marker}] {_color(r['name'], BOLD)} = {r['value']}  (要求 {r['threshold']})")
        if r["note"]:
            print(f"         {_color(r['note'], DIM)}")
        if not r["pass"] and r["suggestion"]:
            print(f"         {_color('建议: ' + r['suggestion'], YELLOW)}")
        print()

    print(_color(f"Source report: {src_report['confidence_stars']}", BOLD))
    print(f"  A {src_report['by_grade']['A']} · B {src_report['by_grade']['B']} · "
          f"C {src_report['by_grade']['C']} · D {src_report['by_grade']['D']} "
          f"(共 {src_report['total_facts']})")
    print(f"  {_color(src_report['confidence_rules'], DIM)}")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_check(args):
    results, src_report, passed, failed = run_all_checks(
        args.article, args.html, args.history,
    )
    if args.json:
        print(json.dumps({
            "passed": passed,
            "failed": failed,
            "checks": results,
            "source_report": src_report,
        }, ensure_ascii=False, indent=2))
    else:
        print_report(results, src_report, passed, failed)
    sys.exit(0 if failed == 0 else 1)


def cmd_compute_source(args):
    article = json.loads(Path(args.article).read_text(encoding="utf-8"))
    src = compute_source_report(article)
    article["source_report"] = src
    Path(args.article).write_text(
        json.dumps(article, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(src, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="v2 quality gate")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_check = sub.add_parser("check", help="跑全部 21 项检查")
    p_check.add_argument("--article", required=True)
    p_check.add_argument("--html", help="最终 HTML（选填）")
    p_check.add_argument("--history", help="排版历史 JSON（选填）")
    p_check.add_argument("--json", action="store_true", help="JSON 输出（CI 友好）")
    p_check.set_defaults(func=cmd_check)

    p_src = sub.add_parser("compute-source-report", help="只算 source_report")
    p_src.add_argument("--article", required=True)
    p_src.set_defaults(func=cmd_compute_source)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
