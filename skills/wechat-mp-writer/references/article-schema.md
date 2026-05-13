# Article.json 中间产物结构（v2 契约层）

## 为什么要中间产物

v1 是"主题进 → HTML 出"的黑箱。一旦读者要求改某段、补某条数据、换某张图，就得整篇重写。v2 引入 `article.json` 作为可见、可改、可量化的中间状态：

- **可改**：要换某段事实，只动 `facts[]` 里的一条 + 重渲染引用它的 `draft_sections[]`
- **可量化**：`quality_check.py` 直接扫这个 JSON 算指标，不用解析 HTML
- **可复用**：写完一篇，下一篇相似主题可以复用 `search_results[]` 和 `facts[]`
- **可审计**：每条事实带来源等级、每张图带审查报告，读者要追问"你这个数据哪来的"答得上

---

## 文件位置约定

每篇文章生成时落到当前工作目录：

```
./articles/<slug>/article.json        # 中间产物（必有）
./articles/<slug>/article.html        # 最终成稿（必有）
./articles/<slug>/images/             # 下载的原图（保留供复用）
./articles/<slug>/quality-report.txt  # quality_check.py 输出
./articles/<slug>/vision-reviews.json # 所有图片的 vision 审查记录
```

`<slug>` 为标题英文化或拼音化的 kebab-case（如 `deepseek-r1-reasoning`）。

---

## 顶层字段（必填 9 个 + 选填 3 个）

```jsonc
{
  "schema_version": "2.0",          // 必填，预留 v3 升级路径

  "meta": { ... },                  // 必填，元数据
  "search_results": [ ... ],        // 必填，原始搜集（含 grade）
  "angles": [ ... ],                // 必填，候选角度（≥3 个）
  "chosen_angle": { ... },          // 必填，最终采用角度
  "outline": [ ... ],               // 必填，章节大纲
  "facts": [ ... ],                 // 必填，事实库（每条带 grade）
  "draft_sections": [ ... ],        // 必填，分段草稿
  "images_plan": [ ... ],           // 必填，图片规划 + vision 审查
  "source_report": { ... },         // 必填，来源分级汇总（自动计算）

  "compliance_report": { ... },     // 选填，quality_check.py 写入
  "edit_log": [ ... ],              // 选填，多轮修改记录
  "publish_state": { ... }          // 选填，wechat_api.py 上传/草稿/发布状态
}
```

---

## 字段详解

### meta（元数据）

```jsonc
{
  "meta": {
    "title": "DeepSeek R1 凭什么在数学题上打平 o1？",  // 必填，最终标题
    "title_candidates": [                              // 选填，淘汰的候选
      "DeepSeek R1 推理能力深度拆解",
      "国产推理模型新王：R1 评测全记录",
      "..."
    ],
    "subtitle": "把 R1 的训练方法、评测、局限一次看清",  // 选填
    "profile_snapshot": {                              // 必填，本次创作时的画像快照
      "positioning": "AI 行业深度分析",
      "audience": "技术从业者 + 关注 AI 的产品经理",
      "tone": "犀利锐评",
      "track": ["AI", "大模型", "评测"]
    },
    "created_at": "2026-05-13T20:30:00+08:00",         // 必填，ISO 8601
    "updated_at": "2026-05-13T21:15:00+08:00",         // 必填，最后修改
    "word_count": 2850,                                // 必填，最终字数
    "word_budget": {                                   // 必填，对标新智元等头部公号
      "tier": "medium",                                // short / medium / long
      "target": 2800,                                  // 目标字数
      "min": 2200,                                     // 下限（低于=单薄）
      "max": 4000                                      // 上限（高于=读不完，硬阈值 ≤6000）
    },
    "estimated_read_minutes": 7,                       // 必填，按 400 字/分钟
    "language": "zh-CN",                               // 必填
    "layout_variant": {                                // 必填，本篇用了哪种排版骨架
      "id": "data_lead",                               // 见 layout-variants.md 七骨架 enum
      "rationale": "事实密集、对比强烈，用数据先行式开头",
      "h2_decoration": "ink_underline",                // 见 layout-variants.md 视觉装饰库
      "accent_color": "#8b3a3a",                       // 本篇专属强调色
      "image_rhythm": "front_heavy"                    // 图文节奏：front_heavy / even / tail_heavy
    },
    "recent_layouts": [                                // 最近 5 篇用过的 variant id（防重复）
      "story_open", "qa_list", "timeline", "story_open", "data_lead"
    ]
  }
}
```

### search_results（搜集原始素材）

每条搜索结果都要进，**这是后续 facts 的原料**。一条只代表"我搜到了什么"，还没判断要不要用。

```jsonc
{
  "search_results": [
    {
      "id": "sr-001",                    // 必填，sr-NNN
      "query": "DeepSeek R1 训练方法",    // 必填，搜索词
      "tool": "WebSearch",               // 必填，WebSearch / WebFetch / 用户提供
      "source_url": "https://github.com/deepseek-ai/DeepSeek-R1/...",
      "source_type": "github_official",  // 必填，见下方 enum
      "grade": "A",                      // 必填，A/B/C/D（见 source-grading.md）
      "title": "DeepSeek-R1 论文",
      "snippet": "We introduce our first-generation reasoning models, ...",
      "fetched_at": "2026-05-13T20:32:00+08:00",
      "raw_content_path": "./articles/deepseek-r1/raw/sr-001.md"  // 选填，长内容存盘
    }
  ]
}
```

**source_type enum**（决定 grade 的核心依据，详见 source-grading.md）:
- `paper_arxiv` / `paper_journal` / `paper_conference` → A
- `official_blog` / `official_announcement` / `github_official` / `regulatory_filing` → A
- `wire_news` (路透/彭博/AP) / `tier1_media` (财新/华尔街日报/纽约时报) → B
- `industry_report` (Gartner/IDC/QuestMobile) → B
- `journalist_longform` (深度报道) → B
- `tier2_media` / `corporate_pr` → C
- `social_post` (微博/X/小红书/知乎答主) → C
- `user_provided` → 视质量定 B/C
- `model_inference` → D（无外部源支撑，只是模型推断）

### angles（候选角度）

主题确定后必须先生成 ≥3 个角度，对比评分再选。**避免直接进入写作 = 偷懒**。

```jsonc
{
  "angles": [
    {
      "id": "ang-1",
      "angle_text": "R1 的开源策略对国产推理模型生态的冲击",
      "differentiation": "大多数评测文都在比分，少有人谈生态影响",
      "audience_fit_score": 4,        // 0-5，对画像 audience 的契合度
      "fact_density_score": 3,        // 0-5，能找到的 A/B 级事实多不多
      "freshness_score": 5,           // 0-5，是否抢热点
      "total_score": 12,              // 三项加和
      "rationale": "..."
    },
    { "id": "ang-2", ... },
    { "id": "ang-3", ... }
  ],
  "chosen_angle": {
    "ref": "ang-1",                    // 必填，角度 id
    "tweaks": "聚焦在模型尺寸 / 训练成本 / API 价格三个具象维度"  // 选填
  }
}
```

### outline（章节大纲）

```jsonc
{
  "outline": [
    {
      "section_id": "sec-1",
      "section_title": "R1 出现之前，国内推理模型在做什么",
      "section_intent": "建立背景，让读者知道 R1 的对照系",
      "estimated_words": 400,
      "facts_needed": ["fact-001", "fact-002"],   // 引用 facts 数组的 id
      "image_intent": "Qwen / Yi / Kimi 等 logo 拼图，或行业全景图"
    },
    {
      "section_id": "sec-2",
      "section_title": "R1 的训练管线：拆开看每一层都做了什么",
      "section_intent": "兑现'机制层'，不能只说'强',要说'为什么强'",
      "estimated_words": 700,
      "facts_needed": ["fact-003", "fact-004", "fact-005"],
      "image_intent": "训练管线流程图（自绘 SVG，因为没有公开图）"
    }
    // ...
  ]
}
```

### facts（事实库）⭐ 核心字段

每篇文章的命脉。**没有 facts 就是空中楼阁**。

```jsonc
{
  "facts": [
    {
      "id": "fact-001",
      "text": "DeepSeek-R1-Zero 在 AIME 2024 上 pass@1 取得 71.0%，超过 OpenAI o1-mini 的 63.6%",  // 必填，具体可核证
      "type": "data",                  // 必填：data / quote / event / mechanism
      "source_ref": ["sr-001"],        // 必填，对应 search_results 的 id（可多源）
      "grade": "A",                    // 必填，多源时取最高
      "used_in_section": ["sec-3"],    // 必填，被哪些章节引用
      "fact_anchor": "Table 1, page 8",  // 选填，原文定位（页码/段落）
      "confidence_note": ""            // 选填，对该事实的不确定性说明
    },
    {
      "id": "fact-002",
      "text": "Sam Altman 在 2025-01-26 的 X 帖子中评价 DeepSeek 是 'a very impressive model'",
      "type": "quote",
      "source_ref": ["sr-008"],
      "grade": "A",
      "used_in_section": ["sec-1", "sec-5"],
      "fact_anchor": "https://x.com/sama/status/...",
      "confidence_note": ""
    }
  ]
}
```

**type enum**:
- `data` — 数字 / 比例 / 时间 / 名次
- `quote` — 直接引语
- `event` — 已发生事件（"X 公司在 X 时间发布了 X"）
- `mechanism` — 机制性陈述（"R1 用 GRPO 而非 PPO 训练，因为 X"）

### draft_sections（分段草稿）

每段是一份完整 HTML 片段（不是 markdown）。**能直接 paste 到微信公号编辑器**。

```jsonc
{
  "draft_sections": [
    {
      "section_id": "sec-1",
      "title": "R1 出现之前，国内推理模型在做什么",
      "html": "<p>...</p><p>...</p>",
      "facts_cited": ["fact-001", "fact-002"],
      "word_count": 412,
      "specificity_check": {           // 自检结果
        "concrete_nouns_per_para": 2.3,  // 平均每段具体名词数
        "ai_cliche_count": 0,
        "passes_red_lines": true
      }
    }
  ]
}
```

### images_plan（图片规划 + 审查）⭐ 核心字段

**每张图都必须有 vision 审查记录**，没审查的图禁止入正文。

```jsonc
{
  "images_plan": [
    {
      "image_id": "img-cover",
      "role": "cover",               // cover / inline / cta
      "section_id": null,            // 封面无 section
      "image_intent": "传达'R1 vs o1 推理对决'的视觉",
      "search_keywords": ["DeepSeek logo", "OpenAI o1", "AI reasoning benchmark"],
      "candidates": [                // 抓取到的候选
        {
          "url": "https://upload.wikimedia.org/...",
          "source": "wikimedia_commons",
          "license": "cc_by_sa_4",
          "local_path": "./articles/deepseek-r1/images/cand-001.png"
        }
      ],
      "chosen": {
        "local_path": "./articles/deepseek-r1/images/cand-001.png",
        "wechat_media_id": "xxx",     // wechat_api.py 上传后回填
        "wechat_url": "https://mmbiz.qpic.cn/..."
      },
      "vision_review": {              // 必填字段，verdict=fail 触发重搜
        "topicality": 4,              // 0-5
        "clarity": 5,
        "mobile_fit": 4,
        "total": 13,
        "verdict": "pass",            // pass / fail
        "notes": "DeepSeek logo 清晰，色彩适合手机屏；缺 o1 元素，topicality 扣 1 分",
        "model_used": "claude-opus-4-7",
        "reviewed_at": "2026-05-13T20:50:00+08:00"
      },
      "alt_text": "DeepSeek R1 推理模型对决 OpenAI o1 的封面图",
      "caption": "图：DeepSeek 官方 logo / Wikimedia Commons CC BY-SA 4.0"
    },
    {
      "image_id": "img-sec3-fig1",
      "role": "inline",
      "section_id": "sec-3",
      "image_intent": "训练管线 SVG 示意图（无公开图源时降级）",
      "fallback_used": true,         // 必填，是否走了 fallback
      "fallback_type": "svg_diagram",  // svg_diagram / quote_block / skip
      // ... vision_review 仍然要跑（审查 SVG 是否清晰可读）
    }
  ]
}
```

**vision_review 阈值**（参考 image-pipeline.md 第 4 节）:
- 三项总分 ≥10 → verdict=pass
- 三项任一 ≤2 → verdict=fail（无论总分）
- verdict=fail → 触发重搜或降级

### source_report（信任度报告）

由 quality_check.py 自动生成，渲染到 HTML 文末。

```jsonc
{
  "source_report": {
    "total_facts": 12,
    "by_grade": { "A": 7, "B": 3, "C": 1, "D": 1 },
    "by_grade_pct": { "A": 58.3, "B": 25.0, "C": 8.3, "D": 8.3 },
    "confidence_stars": "★★★★",      // 4 星：A>50% 且 D<15%
    "confidence_rules": "A 占比 58.3% (≥50%) + D 占比 8.3% (<15%) → 4 星",
    "limitations": [
      "训练成本数据来自第三方推算，原文未披露",
      "..."
    ]
  }
}
```

**置信度星级规则**:
- ★★★★★ A≥60% 且 D=0
- ★★★★  A≥50% 且 D<15%
- ★★★   A≥30%
- ★★    其他
- ★     D≥30%（写"参考价值有限"）

### compliance_report（质量闸门报告）

由 `quality_check.py` 写入。详见 quality_check.py 输出格式。

```jsonc
{
  "compliance_report": {
    "passed": 18,
    "failed": 2,
    "checks": [
      { "name": "a_grade_facts_count", "value": 7, "threshold": 5, "pass": true },
      { "name": "ai_cliche_count", "value": 0, "threshold": 0, "pass": true },
      { "name": "image_vision_pass_rate", "value": 100, "threshold": 100, "pass": true },
      { "name": "first_screen_word_count", "value": 380, "threshold": 300, "pass": false, "note": "首屏字数 380 略高于 300，建议拆段" }
    ]
  }
}
```

### edit_log（修改记录，选填）

```jsonc
{
  "edit_log": [
    {
      "ts": "2026-05-13T21:00:00+08:00",
      "action": "swap_fact",
      "target": "fact-005",
      "before": "...",
      "after": "...",
      "reason": "用户要求换更新的数据"
    }
  ]
}
```

### publish_state（发布状态，选填）

```jsonc
{
  "publish_state": {
    "draft_media_id": "xxx",
    "draft_created_at": "2026-05-13T21:30:00+08:00",
    "preview_sent_to": "wxid_xxx",
    "publish_status": "published",     // draft / preview_sent / published / failed
    "publish_url": "https://mp.weixin.qq.com/s/...",
    "published_at": "2026-05-13T22:00:00+08:00"
  }
}
```

---

## 最小可运行示例

写一篇 5 段 + 4 图的短文，最小 article.json 应包含：

```jsonc
{
  "schema_version": "2.0",
  "meta": { "title": "...", "profile_snapshot": {...}, "created_at": "...", "updated_at": "...", "word_count": 1500, "estimated_read_minutes": 4, "language": "zh-CN" },
  "search_results": [ /* ≥3 条 */ ],
  "angles": [ /* ≥3 个 */ ],
  "chosen_angle": { "ref": "ang-1" },
  "outline": [ /* 5 段 */ ],
  "facts": [ /* ≥5 条，A 级 ≥3 */ ],
  "draft_sections": [ /* 5 段，每段含 html + facts_cited */ ],
  "images_plan": [ /* 4 图，每图含 vision_review */ ],
  "source_report": { /* 自动生成 */ }
}
```

完整示例见 `assets/examples/sample-article.json`。

---

## 字段必填 / 选填速查表

| 字段 | 必填 | 由谁写入 |
|------|------|---------|
| schema_version | ✓ | SKILL.md §3 创建时 |
| meta | ✓ | SKILL.md §3 + §4 持续更新 |
| meta.word_budget | ✓ | SKILL.md §3 创建时根据 tier 自动设 |
| meta.layout_variant | ✓ | SKILL.md §4.2 大纲前必须选定 |
| meta.recent_layouts | ✓ | SKILL.md §4.2 从 `~/.wechat-history.json` 读 |
| search_results | ✓ | SKILL.md §3 信息搜集 |
| angles | ✓ | SKILL.md §4.1 角度 |
| chosen_angle | ✓ | SKILL.md §4.1 角度选择 |
| outline | ✓ | SKILL.md §4.2 大纲 |
| facts | ✓ | SKILL.md §4.3 事实抽取 |
| draft_sections | ✓ | SKILL.md §4.4 撰写 |
| images_plan | ✓ | SKILL.md §6 图片 pipeline |
| source_report | ✓ | quality_check.py |
| compliance_report | 选填 | quality_check.py |
| edit_log | 选填 | 用户改动时 |
| publish_state | 选填 | wechat_api.py |

---

## 演化规则

- **schema_version** 每次破坏性改动必须 bump（v2.0 → v2.1 兼容；v2.0 → v3.0 不兼容）
- 新增字段先放 `meta.experimental.<field_name>`，稳定后提到顶层
- 删除字段必须保留 deprecated 标记一个版本
- quality_check.py 必须能读旧版本（向后兼容三个 minor 版本）
