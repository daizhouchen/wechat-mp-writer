# 图片获取 + 匹配 + 视觉审查 SOP（v2 图片 pipeline 本体）

## 0. 这份文档要解决什么

v1 的图片处理是个三步黑箱：

```
按主题搜 → 下载 → 上传
```

结果是：搜词糊、下载乱、上传完才发现一半图不对题、有水印、或在手机上根本看不清。

v2 把这条线拆成 6 段、每段都有审查和回退：

```
实体级搜词 → 多源抓取 → 去重 → vision 审查 → 段落匹配 → 失败回退
```

**SKILL.md §6 走到"图片配图"这一步时，本文档是该步骤的方法论本体**。SKILL.md 只负责调度顺序与 article.json 字段写回，所有"为什么这样做"和"具体阈值"在本文档里。

字段定义见 `article-schema.md` 的 `images_plan[]` 与 `vision_review`。本文档不重复定义字段，只描述流程与判定规则。

---

## 1. 为什么 v1 的图片处理不行

复盘 v1 真实问题，全部 v2 都要修：

1. **搜词太泛**。"AI"、"科技"、"互联网"、"大模型"——搜回来的全是没意义的概念图（蓝色发光的脑子、电路板、抽象人形），段落讲 DeepSeek R1 也配这种图，完全没信息量
2. **该配实体图时配概念图**。段落明明在讲 Sam Altman 的某次表态、或 H100 芯片、或某条具体的论文图表，配的却是"AI 主题感"通用图
3. **没去重**。一次搜 5 张图，下回来发现 3 张是同一张图被不同站点裁过的版本（连水印都一样），白占数量
4. **没 vision 审查**。下完直接塞正文，水印图、模糊图、字幕没擦干净的截图、不对题的图全进来了，发布后才被读者吐槽
5. **段落匹配靠顺序**。第 3 张图按下标放第 3 段，但其实它讲的是第 7 段的事——读者看到图不对应正文，会怀疑文章是凑的

v2 要把每一项都修掉，且修掉的代价不能让创作流程崩。

---

## 2. 完整 Pipeline 总览

```
draft_sections.html （写完的段落 HTML，含 facts_cited）
    │
    ▼
[1] 实体抽取 + 搜词生成（每段 1-3 个搜词候选）
    │   写入：images_plan[i].search_keywords
    ▼
[2] 多源抓取（按 P1 → P5 优先级）
    │   写入：images_plan[i].candidates
    ▼
[3] 去重（URL 去重 + 感知哈希）
    │   candidates 收敛到 ≤5 个
    ▼
[4] Vision 审查（topicality / clarity / mobile_fit）
    │   写入：images_plan[i].vision_review
    │   verdict=fail 的踢出 candidates
    ▼
[5] 段落匹配（按 image_intent 语义评分，不按顺序）
    │   写入：images_plan[i].section_id, .chosen
    ▼
[6] 失败回退（重搜 → SVG → 引述块 → 跳过）
    │   写入：images_plan[i].fallback_used / .fallback_type
    ▼
images_plan[] 完成
    │
    ▼
wechat_api.py 上传 + 草稿（回填 wechat_media_id / wechat_url）
```

每一步都对应 article.json 的具体字段（详见 §10 映射表）。

---

## 3. 实体抽取 + 搜词生成

**目标**：从段落里抽出"实体"——公司名、产品名、人名、模型名、事件名、地标——再为每个实体生成针对性搜词。

### 抽取顺序（优先级从高到低）

1. 优先用段落的 `facts_cited` 里的事实文本。事实是已经精炼过的实体集合，最干净
2. 其次用 H2/H3 标题里的名词
3. 兜底用段落首句（首句通常承担"提出本段对象"的功能）

### 搜词候选生成规则

每段至少生成 **2 个** 候选搜词，互为备份。三类按需用：

| 类别 | 模板 | 例子 |
|------|------|------|
| 实体级（首选） | `<实体名> + <修饰词>` | `Sam Altman portrait 2024`、`DeepSeek R1 model card`、`NVIDIA H100 chip photo` |
| 场景级（次选） | `<事件名> + <时间>` | `OpenAI Dev Day 2024`、`WAIC 2024 keynote stage` |
| 概念级（兜底） | `<领域> + <视觉概念>` | `reasoning model architecture diagram`、`MoE expert routing illustration` |

### 反例 vs 正例对比

| 反例 | 为什么不行 | 正例 |
|------|----------|------|
| `AI` | 太泛，出来的都是抽象概念图 | `OpenAI logo official` |
| `科技` | 词太大，等于没搜 | `NVIDIA GTC 2024 stage` |
| `深度学习` | 学术抽象词，搜回来全是教学示意图 | `transformer architecture original paper figure` |
| `DeepSeek R1 推理能力强` | 把动词形容词带进去，搜索引擎理解不了 | `DeepSeek R1 model card` |
| `中国 AI 发展` | 国家+领域+趋势三层抽象叠加 | `Baidu Wenxin keynote 2024` |
| `创业不易` | 情绪词，搜回来是配图垃圾场 | `YC W24 demo day` |

### 何时跳过搜词、直接走 SVG

- 段落讲的是抽象机制（如"GRPO 与 PPO 的区别"），公开图源大概率没有 → 直接进 §8 降级 A
- 段落讲的是对比表（如"R1 vs o1 各项评测分数"），用 SVG/HTML 表格更清晰

---

## 4. 多源抓取（优先级表）

按 P1 → P5 顺序尝试。前一级有合格结果就停。

| 优先级 | 源 | 何时用 | 合规 | 工具调用 |
|--------|----|--------|------|---------|
| P1 | Wikimedia Commons API | 实体（人物 / 产品 / 地标 / logo）首选 | CC-BY / CC-BY-SA / Public Domain，安全 | `image_search.py --source wikimedia --query "<搜词>"` |
| P2 | 官方 newsroom / press kit | 公司 logo、产品官方图、发布会现场图 | 官方通常允许编辑使用，需保留 caption 注明 | `image_search.py --source official --url <press_kit_url>` |
| P3 | Unsplash API | 概念图、场景图（办公室、城市、设备） | CC0，但实体（人物）图慎用——可能不是本人 | `image_search.py --source unsplash --query "<搜词>"` |
| P4 | 用户本地素材库 | 用户预先放在 `~/.wechat-assets/` 的图 | 用户自负 | `image_search.py --source local --query "<搜词>"` |
| P5 | Web 通用图片搜索（WebSearch） | 兜底，且只对实体确实没出处时用 | **必须人工核 license** | `image_search.py --source web --query "<搜词>"`，结果强制走人工审查 |
| 兜底 | 自绘 SVG / 引述块 | 全部失败时 | N/A，自有内容 | 自动降级（详见 §8） |

### 严禁来源

- ❌ **Pinterest**：聚合站，license 不明，几乎所有图都是再上传
- ❌ **Google 图片搜索结果直拉**：搜索引擎不解决 license
- ❌ **国内门户网站缩略图**（新浪 / 网易 / 搜狐）：版权混乱 + 经常带原站水印
- ❌ **任何带其他公众号水印的图**：直接侵权
- ❌ **小红书 / 微博图片直链**：作者署名权 + 平台 ToS 问题
- ❌ **抖音视频截图**：除非是用户本人的视频

### 抓取数量约束

每个 image slot 抓 **3-5** 张候选就够。多了 vision 审查耗时长（每张 1-3s × 数量），且去重后留下的也就这个量级。

---

## 5. 去重

两层去重，按顺序跑：

### 第一层：URL 去重
- 同 URL 不重复下载（candidates 里同 url 只留 1 条）
- 含 query string 的 URL 先脱掉 `?w=&h=&q=` 这类尺寸参数再比对

### 第二层：感知哈希（pHash）
- 下载后对每张图算 pHash（8×8 灰度，64 位）
- 两两比对，相似度 ≥0.9（即 pHash 差异 ≤6 bit）视为重复
- 重复组里**保留分辨率最高那张**（手机展示再压不亏，反过来不行）

工具依赖：`image_search.py` 内部用 `imagehash` 库（`pip install imagehash` 是 image_search.py 的硬依赖，缺了就报 `E_DEPS_MISSING`）

去重后 candidates 数量收敛到 ≤5。

---

## 6. Vision 审查（最关键）

**每张备选图入正文前必须跑一次 vision 审查**。这是 v2 不可绕过的硬约束。审查不通过的图禁止进入 `chosen` 字段，只能留在 `candidates` 里供事后追查。

### v2.1 重大变化：Claude 自身 vision 是首选路径

> 在 Claude Code 交互式会话里，**直接用 Read 工具看图就能做 vision 审查**——不需要 ANTHROPIC_API_KEY，不需要跑 image_vision_review.py。这是 v2.1 的核心简化。

| 场景 | 推荐路径 | 何时用 |
|---|---|---|
| **★ 交互式会话（默认）** | **Claude Code 自身能力**：用 Read 工具读图 → 直接打三项分 → 写回 article.json.images_plan[i].vision_review | 用户在 Claude Code 里跟你协作写文章——这是 99% 情况 |
| 批量 / 自动化场景 | `scripts/image_vision_review.py batch --plan article.json` (调 Claude API) | sub-agent 跑、CI、夜间批处理；需要 ANTHROPIC_API_KEY |

**Claude 自身 vision 的标准动作**（每张候选图执行一次）：

```
1. Read tool 读图（./articles/<slug>/images/<filename>.png）
2. 按 §6 三项标准打分（topicality / clarity / mobile_fit 各 0-5）
3. 写回 article.json.images_plan[i].vision_review：
   {
     "topicality": <int 0-5>,
     "clarity": <int 0-5>,
     "mobile_fit": <int 0-5>,
     "total": <topicality + clarity + mobile_fit>,
     "verdict": "pass" 或 "fail",
     "notes": "<50 字内中文>",
     "model_used": "claude-opus-4-7-builtin (Read-tool vision)",
     "reviewed_at": "<ISO 时间戳>"
   }
4. verdict=fail 触发 §8 失败回退
```

无须任何外部 API 调用 — Claude Code 模型本身就是 vision 模型。

### 旧路径：scripts/image_vision_review.py（备选）

仅当以下场景用：
- sub-agent 跑（spawn 出去的 agent 没有交互式 Read 能力时）
- 批量审查 ≥20 张图（用 haiku 比手动 Read 快）
- CI / 自动化（无人值守）

模型选择：

| 场景 | 模型 | 理由 |
|------|------|------|
| 默认（速度优先） | `claude-haiku-4-5` | 单图 1-2s，准确度够 |
| 高质量场景（精度优先） | `claude-opus-4-7` | 单图 3-5s，遇到拿不准的图更稳 |

用户可在 `~/.wechat-profile.md` 的 `vision_review_via` 字段切换 `claude_self`（默认） / `script`。

审查结果写入 `images_plan[i].vision_review`（字段定义见 article-schema.md）。

### 审查三项分

#### 维度 1 — topicality（对题度，0-5）
图片内容和段落语义的相关程度。

| 分 | 标准 | 例子 |
|----|------|------|
| 5 | 图片正中心就是段落要讲的实体，无干扰 | 段落讲 Sam Altman，图就是 Sam Altman 正面照 |
| 4 | 实体在图中，但不是焦点 | 段落讲 OpenAI，图是 OpenAI 办公楼，logo 在角落 |
| 3 | 实体相关但不直接 | 段落讲 OpenAI，图是 Altman 在某次采访的截图 |
| 2 | 领域相关但不是同实体 | 段落讲 DeepSeek，图是通用大模型架构示意 |
| 1 | 仅风格相关 | 段落讲 AI 模型，图是蓝色发光科技底图 |
| 0 | 完全无关 | 段落讲 AI，图是猫咪 |

#### 维度 2 — clarity（清晰度，0-5）

| 分 | 标准 |
|----|------|
| 5 | 高分辨率（≥1200px 长边）+ 无水印 + 无字幕干扰 |
| 4 | 分辨率够 + 有少量水印（如 Wikimedia 角标，可接受） |
| 3 | 分辨率刚够手机看（750-1200px）+ 有水印 |
| 2 | 分辨率偏低（<750px）或水印明显 |
| 1 | 模糊 + 多水印 |
| 0 | 根本看不清 |

#### 维度 3 — mobile_fit（手机适配，0-5）
公众号 90% 阅读在手机上。这是 v1 最容易栽的维度。

| 分 | 标准 |
|----|------|
| 5 | 缩到手机宽（750px）后主体清晰，重点元素 ≥1/3 屏可见 |
| 4 | 缩到手机宽后主体可见 |
| 3 | 缩到手机宽后主体偏小但能看出 |
| 2 | 缩到手机宽后只能看出大致是个什么 |
| 1 | 手机上几乎没意义（如复杂大表格、密集流程图） |
| 0 | 完全不能看 |

### 判定规则

```
verdict = pass  ⟺  total ≥ 10  AND  no item ≤ 2
verdict = fail  ⟺  total < 10   OR  any item ≤ 2
```

- 三项总分 ≥10 且没有任一项 ≤2 → `pass`
- 总分够但某项 ≤2 也判 `fail`（防止"两项 5 分一项 1 分"凑过）
- `verdict = fail` 触发 §8 失败回退

### Vision Prompt 模板

`image_vision_review.py` 内置以下 prompt（这里给 reference 作为说明，不需要在 SKILL.md 里手写）：

```
请审查这张图作为微信公众号配图的适配度。

段落主题：<image_intent>
段落正文摘要：<section_first_sentence + facts_cited[0].text>

请按以下三个维度打分（0-5），并给出综合 verdict：

1. topicality（对题度）：图片内容和段落语义的相关性
2. clarity（清晰度）：分辨率、水印、字幕干扰
3. mobile_fit（手机适配）：缩到 750px 宽后主体是否清晰

输出 JSON：
{
  "topicality": <int 0-5>,
  "clarity": <int 0-5>,
  "mobile_fit": <int 0-5>,
  "verdict": "pass" | "fail",
  "notes": "<不超过 50 字的中文说明>"
}
```

所有审查记录另外汇总写入 `./articles/<slug>/vision-reviews.json`，方便事后复盘"为什么这张被踢"。

---

## 7. 段落匹配

**目标**：每张通过审查的图，匹配到最合适的段落。**不按顺序，按语义**。

### 匹配算法

1. 每段在 `outline` 阶段已经写了 `image_intent`（这段需要什么样的图）
2. 每张候选图在搜词阶段也带了一个 `image_intent`（这张图想表达什么）
3. 计算两者的语义相似度
   - **简单版本**（默认）：关键词重合度 + Jaccard 系数
   - **高级版本**（用户开启 embedding 模式）：embedding cosine similarity
4. 每段最多分配 1-2 张图，避免轰炸
5. 图文比目标：**300-500 字 / 图**（quality_check.py 会扫这个比值）

### 特殊位置规则

| 位置 | 规则 |
|------|------|
| 封面图 | 必须 2.35:1 比例；topicality ≥4 且 clarity ≥4，否则换图 |
| 开篇行业大图 | mobile_fit ≥4（首屏在手机上看不清等于自杀） |
| CTA 图（关注 / 二维码） | 用户配置的固定模板，跳过 vision 审查 |
| 段尾图 | topicality ≥3 即可（起视觉断点作用，对题要求略放宽） |

### 防"图段错位"

匹配完一遍后跑一次 sanity check：
- 如果某段 `image_intent` 是 "Sam Altman 表态"，匹配到的图 vision_review.notes 里却没出现 "Altman" / "person" / "portrait" → 标 `low_confidence_match`，提醒用户人工复核

---

## 8. 失败回退（兜底策略）

按"重试 → 降级"两层处理，全自动。

### 第一层：重试（自动）

```
搜词组 1 全部 fail
    ↓
换搜词组 2（实体级 → 场景级）
    ↓
仍 fail：再换搜词组 3（场景级 → 概念级）
    ↓
仍 fail：进入第二层降级
```

每一轮重试都会把新 candidates 追加到 `images_plan[i].candidates`，并标记 `attempt_round`。事后能看到"这张图试过几轮"。

### 第二层：降级（自动 + 提示用户）

#### 降级 A：自绘 SVG 示意图
- **适用**：抽象概念、流程图、对比表（如训练管线图、benchmark 对比表）
- **怎么做**：根据段落 `facts_cited` 自动生成 SVG（image_search.py 调内置模板）
- **vision_review 仍要跑**：审查 SVG 是否清晰可读（重点看 mobile_fit）
- **写回 article.json**：`fallback_used: true, fallback_type: "svg_diagram"`

#### 降级 B：引述块（无图但加视觉强调块）
- **适用**：抽象概念无法画 SVG（如哲学论述、长引语）
- **怎么做**：用 `<blockquote>` + 醒目背景色 + 大字体替代图片，做视觉断点
- **写回 article.json**：`fallback_used: true, fallback_type: "quote_block"`

#### 降级 C：跳过（不放图）
- **适用**：段落短（<200 字）、不必要配图、或全文图已经足够
- **写回 article.json**：`fallback_used: true, fallback_type: "skip"`

### 降级触发顺序

```
重试 2 轮失败
    ↓
能画 SVG 吗？ → 降级 A
    ↓ 否
段落短或抽象？ → 降级 C（跳过）
    ↓ 否
降级 B（引述块）
```

降级后 SKILL.md §6 必须把降级原因 echo 给用户："本段没找到合适配图，已降级为 SVG 示意图，可手动替换"。

---

## 9. 公众号特有约束（必须遵守）

| 约束 | 数值 | 落实点 |
|------|------|--------|
| 封面长宽比 | 2.35:1 | image_search.py 抓封面时按比例裁切（PIL） |
| 封面文件大小 | ≤5MB（建议 ≤500KB） | image_search.py 用 PIL 压缩 |
| 正文图大小 | ≤5MB（建议 ≤300KB） | 同上 |
| 单图分辨率 | 长边 ≤1920px（公众号会自动压） | 上传前预压一次，避免在公号端被压糊 |
| 图片数量 | 1500 字以下 ≤3 图，3000 字 ≤8 图 | quality_check.py 扫 |
| alt 文字 | 必有 | image_search.py 强制生成（来自 image_intent） |
| 图片格式 | jpg / png / gif / webp（公号都支持） | webp 优先（文件最小） |
| 二维码图 | 单独的 CTA 图，不算正文图数量 | 用户配置专用 slot |

注意：微信公众号上传 API 对图片大小卡得没那么死，但**手机端流量友好**才是真目标。300KB 以内的正文图是好习惯。

---

## 10. Pipeline 与 article.json 的字段映射

明确告诉 SKILL.md：每一步往 article.json 哪些字段写。

| Pipeline 步骤 | 写入 article.json |
|---------------|------------------|
| 1. 实体抽取 + 搜词生成 | `images_plan[i].image_intent`、`images_plan[i].search_keywords` |
| 2. 多源抓取 | `images_plan[i].candidates[]`（每条含 url / source / license / local_path） |
| 3. 去重 | `images_plan[i].candidates[]` 收敛到 ≤5 |
| 4. Vision 审查 | `images_plan[i].vision_review`（topicality / clarity / mobile_fit / total / verdict / notes / model_used / reviewed_at） |
| 5. 段落匹配 | `images_plan[i].section_id`、`images_plan[i].chosen.local_path` |
| 6. 失败回退 | `images_plan[i].fallback_used`、`images_plan[i].fallback_type` |
| 上传后 | `images_plan[i].chosen.wechat_media_id`、`images_plan[i].chosen.wechat_url` |
| 全部审查记录汇总 | `./articles/<slug>/vision-reviews.json`（独立文件） |

字段类型与必填规则严格按 `article-schema.md` 的定义。本文档仅描述写入时机。

---

## 11. 自检题（每篇文章发布前过一遍）

1. 每张进 `chosen` 的图，`vision_review.verdict` 都是 `pass` 吗？
2. 有没有"AI 主题随便糊一张"的概念图（topicality ≤2）混进了正文？
3. 封面图是 2.35:1 吗？topicality 和 clarity 都 ≥4 吗？
4. 段落图是按 `image_intent` 匹配的，还是按下标顺序硬塞的？
5. 全文图文比在 300-500 字 / 图 区间吗？（quality_check.py 输出）
6. 所有图都有 `alt_text` 吗？（**caption 默认不渲染——见去 AI 痕迹章节**）
7. 有没有图触发了 `low_confidence_match`？是否人工复核过？

---

## 12. 封面 SVG 模板库（v2.1 新增 · fallback 用）

无现成图源时降级到自绘 SVG 封面，4 种模板覆盖深稿场景。每种都解决了已知 baseline 对齐等坑。

### 模板 12.1 数据反差型（适用：薪资 / 数据对比 / 横评开头）

```html
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1175 500" font-family="-apple-system, 'PingFang SC', sans-serif">
  <defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#1a1a1a"/><stop offset="1" stop-color="#2a2018"/></linearGradient></defs>
  <rect width="1175" height="500" fill="url(#bg)"/>
  <text x="60" y="80" font-size="22" fill="#7a5500" letter-spacing="4">CATEGORY · YEAR</text>
  <!-- 关键：vs 用 dominant-baseline=central + 单独 y，避免不同字号 baseline 对齐塌 -->
  <text x="60" y="220" font-size="100" font-weight="bold" fill="#fdf8ee">$500K</text>
  <text x="430" y="190" font-size="60" font-weight="300" fill="#7a5500" dominant-baseline="central" font-style="italic">vs</text>
  <text x="540" y="220" font-size="100" font-weight="bold" fill="#fdf8ee">月薪 4 万</text>
  <text x="60" y="305" font-size="42" font-weight="500" fill="#fdf8ee" letter-spacing="2">真假 AI PM 分水岭</text>
  <line x1="60" y1="395" x2="1115" y2="395" stroke="#7a5500" stroke-width="1" opacity="0.5"/>
  <text x="60" y="445" font-size="26" fill="#fdf8ee">Anthropic · OpenAI · Google AI · 字节 · 阿里</text>
  <text x="1115" y="480" font-size="16" fill="#888" text-anchor="end" letter-spacing="2">A what I</text>
</svg>
```

**关键技术点**：
- 不同字号文字混排时**必须** `dominant-baseline="central"` 单独 y 定位，否则 alphabetic baseline 让小字下沉
- 深底（#1a1a1a）+ 米白字（#fdf8ee）+ 暖橙强调（#7a5500），三色克制
- 公司名行用 ` · ` 分隔（**不要用 emoji 或多种 dingbat**，会被 quality_check 的 emoji 词库扫到）

### 模板 12.2 大字标语型（适用：观点 / 反常识结论开头）

```html
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1175 500" font-family="-apple-system, 'PingFang SC', sans-serif">
  <rect width="1175" height="500" fill="#fdf8ee"/>
  <line x1="60" y1="60" x2="200" y2="60" stroke="#7a5500" stroke-width="3"/>
  <text x="60" y="100" font-size="20" fill="#7a5500" letter-spacing="3">2026 年 5 月</text>
  <text x="60" y="200" font-size="64" font-weight="bold" fill="#1a1a1a">大字标语第一行</text>
  <text x="60" y="280" font-size="64" font-weight="bold" fill="#7a5500">大字标语第二行（重音）</text>
  <text x="60" y="430" font-size="22" fill="#666">— 副标题 / 一句话总结</text>
  <text x="1115" y="480" font-size="16" fill="#999" text-anchor="end" letter-spacing="2">A what I</text>
</svg>
```

### 模板 12.3 公司 logo 拼接型（适用：横评 / 行业全景）

```html
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1175 500" font-family="-apple-system, 'PingFang SC', sans-serif">
  <rect width="1175" height="500" fill="#1a1a1a"/>
  <text x="60" y="100" font-size="56" font-weight="bold" fill="#fdf8ee">2026 AI 横评</text>
  <text x="60" y="160" font-size="22" fill="#7a5500" letter-spacing="2">8 家公司一次拆开看</text>

  <!-- 横向排 Anthropic / OpenAI / Google / Meta / 阿里 / 字节 / 美团 / DeepSeek -->
  <text x="60" y="280" font-size="32" font-weight="600" fill="#fdf8ee">Anthropic</text>
  <text x="280" y="280" font-size="32" fill="#7a5500">·</text>
  <text x="320" y="280" font-size="32" font-weight="600" fill="#fdf8ee">OpenAI</text>
  <text x="490" y="280" font-size="32" fill="#7a5500">·</text>
  <text x="530" y="280" font-size="32" font-weight="600" fill="#fdf8ee">Google</text>
  <text x="700" y="280" font-size="32" fill="#7a5500">·</text>
  <text x="740" y="280" font-size="32" font-weight="600" fill="#fdf8ee">Meta</text>
  <text x="60" y="350" font-size="32" font-weight="600" fill="#fdf8ee">阿里</text>
  <text x="180" y="350" font-size="32" fill="#7a5500">·</text>
  <text x="220" y="350" font-size="32" font-weight="600" fill="#fdf8ee">字节</text>
  <text x="340" y="350" font-size="32" fill="#7a5500">·</text>
  <text x="380" y="350" font-size="32" font-weight="600" fill="#fdf8ee">美团</text>
  <text x="500" y="350" font-size="32" fill="#7a5500">·</text>
  <text x="540" y="350" font-size="32" font-weight="600" fill="#fdf8ee">DeepSeek</text>

  <text x="1115" y="480" font-size="16" fill="#888" text-anchor="end" letter-spacing="2">A what I</text>
</svg>
```

### 模板 12.4 时间线型（适用：发展史 / 年终盘点）

```html
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1175 500" font-family="-apple-system, 'PingFang SC', sans-serif">
  <rect width="1175" height="500" fill="#fdf8ee"/>
  <text x="60" y="80" font-size="40" font-weight="bold" fill="#1a1a1a">主标题在这里</text>
  <text x="60" y="120" font-size="20" fill="#7a5500">2017 → 2026 · 一条时间线看清</text>

  <!-- 横向时间线 -->
  <line x1="80" y1="280" x2="1095" y2="280" stroke="#7a5500" stroke-width="2"/>
  <circle cx="180" cy="280" r="8" fill="#7a5500"/>
  <text x="180" y="320" text-anchor="middle" font-size="20" font-weight="bold" fill="#1a1a1a">2017</text>
  <text x="180" y="345" text-anchor="middle" font-size="14" fill="#666">起点</text>
  <circle cx="430" cy="280" r="8" fill="#7a5500"/>
  <text x="430" y="320" text-anchor="middle" font-size="20" font-weight="bold" fill="#1a1a1a">2020</text>
  <text x="430" y="345" text-anchor="middle" font-size="14" fill="#666">转折</text>
  <circle cx="680" cy="280" r="8" fill="#7a5500"/>
  <text x="680" y="320" text-anchor="middle" font-size="20" font-weight="bold" fill="#1a1a1a">2023</text>
  <text x="680" y="345" text-anchor="middle" font-size="14" fill="#666">爆发</text>
  <circle cx="930" cy="280" r="14" fill="#7a5500" stroke="#fdf8ee" stroke-width="3"/>
  <text x="930" y="325" text-anchor="middle" font-size="22" font-weight="bold" fill="#7a5500">2026</text>
  <text x="930" y="350" text-anchor="middle" font-size="14" fill="#666">现在</text>

  <text x="1115" y="480" font-size="16" fill="#999" text-anchor="end" letter-spacing="2">A what I</text>
</svg>
```

### 通用渲染流程（两条路径 · 按可用性选）

SVG → PNG（公众号上传需要 PNG），按以下优先级选：

**P1 · Playwright MCP（首选 · 还原度最高）**
1. 写 SVG 到 `./articles/<slug>/images/cover-render.html`（带 viewport 设置）
2. 用 playwright MCP `browser_navigate` 到 `data:text/html;base64,<...>` URL（避开 file:// 限制）+ `browser_take_screenshot` 输出 `cover.png`
3. Read 工具看 PNG 做 vision 审查
4. 走 publish.sh 上传

**P2 · PIL fallback（playwright 不可用时 · cron / 远程 agent / MCP 断连场景）** ★ v2.1.3 新增

playwright MCP 任何原因不可用（断连 / cron 环境 / data URL 太大 / 服务器禁端口）→ 直接用 PIL 画 PNG，零依赖只需 WenQuanYi 字体。

具体做法：
1. 复制模板 `~/.claude/skills/wechat-mp-writer/scripts/render_pil_template.py` 到 `./articles/<slug>/render_images.py`
2. 改 `OUT_DIR` / `ACCENT` (按 style_preset) / 文案内容
3. `python3 render_images.py` → 直接输出 PNG 到 images/
4. 走 vision 审查（Read 工具）+ publish.sh

PIL 路径的限制：
- 不支持复杂 SVG 渐变/曲线，但 90% 公众号配图都是 卡片+大字+矩阵 这种 PIL 完全 OK 的
- 文字必须用 WenQuanYi 字体路径：`/home/zcdai/.local/share/fonts/wqy-microhei/wqy-microhei.ttc`
- 单文件 < 100 行代码即可画出 cover_template (logo_collage / data_contrast / matrix)

实战参考：`/home/zcdai/kn/ms/articles/ai-agent-4-paths/render_images.py`（cron 自动撰文场景 / PIL 直画 cover + 决策矩阵 / 2 张 PNG 渲染时间 < 2 秒）

判定何时降到 P2：playwright MCP 调用一次报错 → 立即降到 P2，不重试。

---

## 13. 图片渲染默认值（v2.1 新增）

**所有 inline 图片必须带圆角 + 阴影**。裸图禁止。详细模板见 `references/layout-components.md` 组件 9。

```css
/* 普通正文图 */
border-radius: 8px;
box-shadow: 0 2px 12px rgba(0,0,0,0.06);

/* 封面图（更厚阴影） */
border-radius: 8px;
box-shadow: 0 2px 12px rgba(0,0,0,0.08);

/* 实体 logo（深底白图标，需加 padding 提升可读性） */
border-radius: 8px;
background: #1a1a1a;
padding: 24px;
```

quality_check.py 加扫描：所有 `<img>` 必须有 `border-radius`，否则 warn。
8. 降级图（SVG / quote_block）是否被用户知会？
9. 上传后每张图都拿到 `wechat_media_id` 了吗？没拿到的是哪张、为什么？
10. `vision-reviews.json` 是否完整保留（事后追查能复现判定）？

任何一条答 No，回到对应 §章节修。
