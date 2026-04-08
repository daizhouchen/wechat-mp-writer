#!/usr/bin/env python3
"""
微信公众号内容合规检查脚本
检查广告法极限词、敏感词等合规风险
"""

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 广告法极限词库
# ---------------------------------------------------------------------------

ABSOLUTE_TERMS = [
    "最好", "最佳", "最优", "最强", "最大", "最小", "最高", "最低", "最快",
    "第一", "首个", "首选", "唯一", "独家", "顶级", "顶尖", "极致",
    "绝对", "绝无仅有", "史无前例", "前所未有",
    "100%", "百分之百", "百分百", "零风险", "零缺陷",
    "永久", "永远", "万能", "全能",
    "国家级", "世界级", "全球首",
    "驰名商标", "中国名牌", "免检",
]

EXAGGERATION_TERMS = [
    "秒杀", "碾压", "完爆", "吊打", "封神",
    "必备", "必须", "必买", "必看",
    "神器", "神药", "灵丹妙药",
    "祖传", "秘方", "特效",
    "保证", "承诺", "包治", "包好", "包瘦", "包过",
    "立即见效", "立竿见影", "药到病除",
]

MEDICAL_FINANCE_TERMS = [
    "治愈", "根治", "疗效", "药效",
    "稳赚", "保本", "高收益", "零风险投资",
    "躺赚", "暴富", "财务自由",
]

# ---------------------------------------------------------------------------
# 检查逻辑
# ---------------------------------------------------------------------------

def strip_html_tags(html_content):
    """移除 HTML 标签，只保留文本内容"""
    return re.sub(r"<[^>]+>", "", html_content)


def check_content(content, is_html=True):
    """检查内容合规性，返回问题列表"""
    text = strip_html_tags(content) if is_html else content
    issues = []

    # 检查各类词库
    categories = [
        ("广告法极限词", ABSOLUTE_TERMS, "high"),
        ("夸张宣传用语", EXAGGERATION_TERMS, "medium"),
        ("医疗/金融敏感词", MEDICAL_FINANCE_TERMS, "high"),
    ]

    for category, terms, severity in categories:
        for term in terms:
            # 查找所有出现位置
            positions = [m.start() for m in re.finditer(re.escape(term), text)]
            if positions:
                for pos in positions:
                    # 提取上下文
                    start = max(0, pos - 10)
                    end = min(len(text), pos + len(term) + 10)
                    context = text[start:end]
                    issues.append({
                        "term": term,
                        "category": category,
                        "severity": severity,
                        "position": pos,
                        "context": f"...{context}...",
                        "suggestion": _get_suggestion(term),
                    })

    return issues


def _get_suggestion(term):
    """为敏感词提供替换建议"""
    suggestions = {
        "最好": "优质/出色/推荐",
        "最佳": "优选/优质/出色",
        "最强": "强劲/领先/卓越",
        "第一": "领先/前列/头部",
        "唯一": "稀有/少见/独特",
        "绝对": "非常/极为/相当",
        "100%": "高达/接近全部",
        "永久": "长期/持久/长效",
        "必备": "推荐/值得拥有",
        "必买": "推荐入手/值得考虑",
        "神器": "好物/利器/工具",
        "保证": "力求/致力于",
        "治愈": "改善/缓解/辅助",
        "稳赚": "预期收益/历史表现",
        "顶级": "高端/优质/精选",
    }
    return suggestions.get(term, "建议替换为更客观的表述")


def format_report(issues):
    """格式化检查报告"""
    if not issues:
        return "✓ 合规检查通过，未发现敏感词"

    high = [i for i in issues if i["severity"] == "high"]
    medium = [i for i in issues if i["severity"] == "medium"]

    lines = []
    lines.append(f"⚠ 发现 {len(issues)} 处合规风险（高风险 {len(high)}，中风险 {len(medium)}）\n")

    if high:
        lines.append("【高风险 — 建议必须修改】")
        for i, issue in enumerate(high, 1):
            lines.append(f"  {i}. 「{issue['term']}」({issue['category']})")
            lines.append(f"     上下文：{issue['context']}")
            lines.append(f"     替换建议：{issue['suggestion']}")
        lines.append("")

    if medium:
        lines.append("【中风险 — 建议酌情修改】")
        for i, issue in enumerate(medium, 1):
            lines.append(f"  {i}. 「{issue['term']}」({issue['category']})")
            lines.append(f"     上下文：{issue['context']}")
            lines.append(f"     替换建议：{issue['suggestion']}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="微信公众号内容合规检查")
    parser.add_argument("--content", help="直接传入内容字符串")
    parser.add_argument("--file", help="从文件读取内容")
    parser.add_argument("--json", action="store_true", help="输出JSON格式")

    args = parser.parse_args()

    if args.file:
        content = Path(args.file).read_text(encoding="utf-8")
    elif args.content:
        content = args.content
    else:
        content = sys.stdin.read()

    if not content.strip():
        print("错误：未提供待检查内容", file=sys.stderr)
        sys.exit(1)

    issues = check_content(content)

    if args.json:
        print(json.dumps(issues, ensure_ascii=False, indent=2))
    else:
        print(format_report(issues))

    # 如果有高风险问题，exit code = 1
    if any(i["severity"] == "high" for i in issues):
        sys.exit(1)


if __name__ == "__main__":
    main()
