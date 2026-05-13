#!/usr/bin/env python3
"""
图片视觉审查脚本（v2 image pipeline 第 4 步）

用 Claude Vision 审查每张候选图，打三项分：
  - topicality（对题度，0-5）
  - clarity（清晰度，0-5）
  - mobile_fit（手机适配，0-5）

判定规则：
  - verdict = pass ⟺ 总分 ≥ 10 且任一项不 ≤ 2
  - verdict = fail ⟺ 总分 < 10 或任一项 ≤ 2

使用：
  python image_vision_review.py review --image cand-001.png --intent "Sam Altman 在 OpenAI 发布会上发言" --section-text "Sam Altman 在 1 月 26 日的 X 帖子里说 ..."
  python image_vision_review.py batch --plan article.json   # 扫整个 images_plan
  python image_vision_review.py batch --plan article.json --model claude-haiku-4-5

环境变量：
  ANTHROPIC_API_KEY — 必须

依赖：
  pip install anthropic
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_MODEL = "claude-haiku-4-5"  # 审查多张图，速度优先；用户可换 claude-opus-4-7

VISION_PROMPT_TEMPLATE = """请审查这张图作为微信公众号配图的适配度。

段落主题（image_intent）：{intent}

段落正文摘要：{section_text}

请按以下三个维度打分（0-5 整数），并给出综合 verdict：

1. topicality（对题度）：图片内容和段落语义的相关性
   - 5：图片正中心就是段落要讲的实体
   - 3：实体相关但不直接（如讲 OpenAI 配 Sam Altman 采访截图）
   - 1：仅风格相关（如讲 AI 配蓝色科技底图）
   - 0：完全无关

2. clarity（清晰度）：分辨率 + 水印 + 字幕干扰
   - 5：高分辨率（≥1200px 宽）+ 无水印
   - 3：分辨率刚够手机看（750-1200px）+ 有少量水印
   - 1：模糊或多水印
   - 0：根本看不清

3. mobile_fit（手机适配）：缩到 750px 宽后主体是否清晰
   - 5：主体清晰，重点元素 ≥1/3 屏可见
   - 3：主体偏小但能看出
   - 1：手机上几乎没意义
   - 0：完全不能看

判定规则：
  - 总分 ≥ 10 且没有任一项 ≤ 2 → verdict = "pass"
  - 否则 → verdict = "fail"

只输出严格 JSON（不要任何解释或 markdown 代码块），形如：
{{"topicality": 4, "clarity": 5, "mobile_fit": 4, "total": 13, "verdict": "pass", "notes": "DeepSeek logo 清晰，缺 o1 元素 topicality 扣 1"}}

notes 限 50 字以内中文。"""


def _load_anthropic():
    try:
        from anthropic import Anthropic  # type: ignore
        return Anthropic
    except ImportError:
        sys.stderr.write("缺少依赖：pip install anthropic\n")
        sys.exit(2)


def _read_image_bytes(image_input: str) -> tuple[bytes, str]:
    """支持本地路径或 URL。返回 (bytes, media_type)"""
    p = Path(image_input)
    if p.exists():
        data = p.read_bytes()
    else:
        import urllib.request
        with urllib.request.urlopen(image_input, timeout=20) as resp:
            data = resp.read()
    suffix = (p.suffix.lower() if p.exists() else
              "." + image_input.rsplit(".", 1)[-1].lower())
    media_type = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif",
    }.get(suffix, "image/jpeg")
    return data, media_type


def review_one(image_input: str, intent: str, section_text: str,
               model: str = DEFAULT_MODEL, max_retries: int = 2) -> dict:
    """对单张图跑一次 vision 审查。"""
    Anthropic = _load_anthropic()
    client = Anthropic()  # 自动从 ANTHROPIC_API_KEY 读

    img_bytes, media_type = _read_image_bytes(image_input)
    img_b64 = base64.standard_b64encode(img_bytes).decode("utf-8")

    prompt = VISION_PROMPT_TEMPLATE.format(
        intent=intent,
        section_text=section_text[:300],
    )

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=300,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": img_b64,
                        }},
                        {"type": "text", "text": prompt},
                    ],
                }],
            )
            text = resp.content[0].text.strip()
            # 兼容偶尔的 markdown 包裹
            if text.startswith("```"):
                text = text.strip("`")
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            data = json.loads(text)
            # 强制规范
            data["total"] = int(data.get("topicality", 0)) + \
                            int(data.get("clarity", 0)) + \
                            int(data.get("mobile_fit", 0))
            data["verdict"] = _decide_verdict(data)
            data["model_used"] = model
            data["reviewed_at"] = datetime.now(timezone.utc).isoformat()
            return data
        except Exception as e:
            last_error = e
            time.sleep(1.5 * (attempt + 1))

    # 失败兜底
    return {
        "topicality": 0, "clarity": 0, "mobile_fit": 0, "total": 0,
        "verdict": "fail",
        "notes": f"vision API 调用失败：{last_error}"[:80],
        "model_used": model,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
    }


def _decide_verdict(data: dict) -> str:
    t = int(data.get("topicality", 0))
    c = int(data.get("clarity", 0))
    m = int(data.get("mobile_fit", 0))
    total = t + c + m
    if total >= 10 and min(t, c, m) > 2:
        return "pass"
    return "fail"


def cmd_review(args):
    result = review_one(
        image_input=args.image,
        intent=args.intent,
        section_text=args.section_text,
        model=args.model,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_batch(args):
    """扫 article.json.images_plan，对每个 candidate 跑审查。"""
    plan_path = Path(args.plan)
    article = json.loads(plan_path.read_text(encoding="utf-8"))
    images_plan = article.get("images_plan", [])

    sections_by_id = {s["section_id"]: s for s in article.get("draft_sections", [])}

    reviewed = 0
    for img_entry in images_plan:
        section_id = img_entry.get("section_id")
        section_text = ""
        if section_id and section_id in sections_by_id:
            html = sections_by_id[section_id].get("html", "")
            import re as _re
            section_text = _re.sub(r"<[^>]+>", "", html)[:300]

        intent = img_entry.get("image_intent", "")
        candidates = img_entry.get("candidates", [])

        for cand in candidates:
            target = cand.get("local_path") or cand.get("url")
            if not target:
                continue
            if "vision_review" in cand and not args.force:
                continue
            sys.stderr.write(f"  审查 {target}...\n")
            result = review_one(target, intent, section_text, model=args.model)
            cand["vision_review"] = result
            reviewed += 1
            time.sleep(0.5)

        # 选最佳候选（pass 中总分最高的）
        passing = [c for c in candidates if c.get("vision_review", {}).get("verdict") == "pass"]
        if passing:
            best = max(passing, key=lambda c: c["vision_review"]["total"])
            img_entry["chosen"] = {
                "local_path": best.get("local_path"),
                "url": best.get("url"),
            }
            img_entry["vision_review"] = best["vision_review"]
        else:
            # 全部 fail，标记 fallback 待降级
            img_entry["fallback_used"] = True
            img_entry["fallback_type"] = img_entry.get("fallback_type", "needs_decision")

    # 写回
    plan_path.write_text(json.dumps(article, ensure_ascii=False, indent=2), encoding="utf-8")
    sys.stderr.write(f"完成：{reviewed} 张审查，写回 {plan_path}\n")
    print(json.dumps({"reviewed": reviewed, "plan_file": str(plan_path)}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="v2 image vision review (Claude)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_one = sub.add_parser("review", help="审查单张图")
    p_one.add_argument("--image", required=True, help="本地路径或 URL")
    p_one.add_argument("--intent", required=True)
    p_one.add_argument("--section-text", default="")
    p_one.add_argument("--model", default=DEFAULT_MODEL)
    p_one.set_defaults(func=cmd_review)

    p_batch = sub.add_parser("batch", help="扫 article.json 的 images_plan")
    p_batch.add_argument("--plan", required=True)
    p_batch.add_argument("--model", default=DEFAULT_MODEL)
    p_batch.add_argument("--force", action="store_true", help="强制重审已有 vision_review 的图")
    p_batch.set_defaults(func=cmd_batch)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
