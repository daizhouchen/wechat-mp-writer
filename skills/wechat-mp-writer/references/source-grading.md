# 来源分级方法论（v2 信任度核心）

## 0. 这份文档在做什么

**一句话目标**：为每条 `facts[]` 和 `search_results[]` 打 A/B/C/D 四级，让读者在文末看到一份"本文来源透明度"报告，知道哪些是一手原始、哪些是模型自己推断。

**SKILL.md 引用位置**：
- §3 信息搜集：每条 `search_results` 落库时即打 `grade`
- §4.3 事实抽取：每条 `fact` 取多源中最高 grade
- §5 质量闸门：`quality_check.py` 调用本文件第 5 节的星级规则
- §7 渲染：把 `source_report` 渲染成第 4 节定义的 HTML 块塞到文末

**和姊妹文档的关系**：
- `article-schema.md` — 定义了 `source_type` enum 和 `source_report` 字段；本文件是其"打分手册"，不重定义字段
- `content-engine.md` — 在"事实密度"小节会引用本文件第 2 节的 A/B 级清单
- `scripts/quality_check.py` — 直接消费本文件第 3 节的映射表和第 5 节的星级规则

---

## 1. 为什么要分级

公众号生态里有三件事在系统性破坏读者信任：

1. **标题党**：标题写"独家爆料"，正文是别家媒体三天前的稿子
2. **数据造假**：随手编一个"占比 73%"，没人核对
3. **AI 杜撰**：模型把"听过的"和"看过的"混在一起输出，连作者自己都分不清

分级不是给学者看的学术规范，而是建立读者信任的小动作——和维基百科的脚注、《纽约客》的 fact-checker 文化是同一种东西：**让"我哪里得到这个信息"变成一个可见的事实，而不是黑箱**。

读者扫一眼文末的"A 级 7 处、D 级 1 处"，对全文的可信度立刻有体感。这比任何"业内人士"、"独家获悉"都更能建立长期信任。

---

## 2. A/B/C/D 完整定义

### A 级 = 一手原始

**定义**：发起方 / 当事人 / 官方机构的直接出品。

**包含**：
- 公司官方 blog / 公告 / newsroom（anthropic.com/news、openai.com/blog、deepmind.google/discover/blog）
- 上市公司财报、招股书、SEC 10-K / 10-Q、港交所公告
- 学术论文（arxiv、顶刊、顶会 proceedings）
- 政府数据（国家统计局、央行、欧盟委员会、美国劳工部）
- 法律文书、判决书、监管批文
- 当事人本人的公开发言（Sam Altman 的 X、雷军的微博、张一鸣的内部信流出原文）
- 官方 GitHub repo / 模型卡 / API 文档

**不算 A**：第三方对官方内容的解读 / 翻译 / 二次报道（即使翻译得很准）；公司官方公众号转发别家媒体的稿子。

**可信度**：极高，但要标注"官方倾向"——公司不会主动自爆短板，财报里"调整后净利润"和"GAAP 净利润"差得离谱时记得点出来。

### B 级 = 权威二手

**定义**：有专业声誉、有事实核查流程的二手报道。

**包含**：
- 通讯社：路透、彭博、AP、AFP、新华社（事件类快讯而非评论）
- 一线大报深度报道：WSJ、NYT、FT、《财新》深度、《晚点 LatePost》、《硅星人》深度组、《华尔街见闻》调查稿
- 业内权威研究机构：Gartner、IDC、QuestMobile、CNNIC、Statista（注明数据源的版本，非简单二手编译）
- 行业知名长文 / newsletter：Stratechery、The Information、Stratechery、《张小珺商业访谈录》、《晚点对话》、《硅基立场》深度
- 知名学者 / 行业分析师的署名长文（如 Benedict Evans、Ben Thompson、傅盛公开演讲实录）
- 经过事实核查的播客 / 视频（a16z 访谈、Lex Fridman、张小珺访谈，引用时锁定到具体时间戳）

**不算 B**：媒体的快讯短消息 / 编译稿 / 通稿改写 / 没有记者署名的"小编"短文（落 C）。

**可信度**：高。但记者也有立场——同一事件路透和《纽约时报》可能用不同口径，多源对照更稳。

### C 级 = 普通二手

**定义**：质量参差、需个案判断的内容。

**包含**：
- 普通媒体快讯 / 编译稿 / 营销稿
- 自媒体大号文章（即使 10w+，也属 C，除非内容是其本人原创调研被同行验证过）
- 知乎高赞答主、X / 微博 / 小红书 KOL 评论（除非他本人是当事人——那升 A）
- 行业群聊截图、未署名爆料
- 普通记者短消息 / 通稿改头条
- 公司公关稿、PR newswire 稿

**可信度**：中等。可作为"角度启发"或"信号源"——例如某个爆料先在 X 出现，再去找官方源印证；但 C 级**不能作为某个事实的唯一来源**。

### D 级 = 模型推断（必须显式标注）

**定义**：模型基于训练知识生成、但本次搜集中**没有找到外部源支撑**的内容。

**何时不可避免**：
- 写历史背景，但当下网络没有合适的事实源（如"2010 年代初的中国移动互联网格局"）
- 做合理推算（如"按英伟达公开的 H100 单卡价格 + DeepSeek 论文披露的 GPU 小时数推算，训练成本约 X"）
- 解释通用概念（如"什么是 chain-of-thought"——不需要外部源，但要写"按惯例理解"而非"研究表明"）

**强制规则**：
- 文章里出现 D 级事实，必须在该句末或段尾用小字标注：`<sup style="color:#999">未核证</sup>` 或 `<sup style="color:#999">据 X 推算</sup>`
- D 级在 `source_report.by_grade` 里必须显示，**不能藏起来**
- D 级占比 ≥ 30% → `quality_check.py` 直接给"参考价值有限"警告 + 星级降为 ★

---

## 3. 怎么打分（操作流程）

### Step 1：定 source_type
对每条 `search_results[]`，按 `article-schema.md` §search_results 里的 `source_type` enum 选最匹配的（`paper_arxiv` / `official_blog` / `wire_news` / `tier1_media` / `industry_report` / `journalist_longform` / `tier2_media` / `corporate_pr` / `social_post` / `user_provided` / `model_inference`）。

### Step 2：source_type → grade 映射

| source_type | grade | 备注 |
|---|---|---|
| `paper_arxiv` / `paper_journal` / `paper_conference` | A | 同行评议 / 预印本均算 |
| `official_blog` / `official_announcement` | A | 公司 / 机构自家域名 |
| `github_official` | A | 项目方维护的 repo / model card |
| `regulatory_filing` | A | SEC / 港交所 / 央行公示 |
| `wire_news` (路透/彭博/AP) | B | 引用时锁定 wire 服务 + 时间戳 |
| `tier1_media` (财新/WSJ/FT/NYT/晚点) | B | 必须是带记者署名的深度稿 |
| `industry_report` (Gartner/IDC/QuestMobile) | B | 引用版本号 + 发布日期 |
| `journalist_longform` | B | 个人 newsletter 也算（Stratechery 等） |
| `tier2_media` | C | 36氪快讯、虎嗅短文等 |
| `corporate_pr` | C | 公司公关稿、PR newswire |
| `social_post` | C | 普通 KOL 微博 / X / 小红书 |
| `user_provided` | B 或 C | 看用户提供的源本身的级别（截图原出处） |
| `model_inference` | D | 必须显式标注，不能藏 |

### Step 3：多源时取最高级
同一 `fact` 如果在 3 个来源出现（`source_ref` 数组有 3 个 sr-id），`grade` 取**最高的那个**。例如 fact-005 同时被 arxiv 论文（A）+ 路透报道（B）+ 知乎转述（C）支撑 → `grade = "A"`。

### Step 4：边界判断（常见 case）

| 边界情况 | 裁定 | 理由 |
|---|---|---|
| 知名个人 X 帖子转发官方公告原文 | A | 内容本身是官方原文，不是个人评论 |
| 公关稿（corporate_pr） | C | 公司利益相关，不是中立事实 |
| 同事件路透快讯 + 财新深度 | B | 引用以财新为主，路透时间戳作辅；都是 B |
| 模型生成"X 公司 2024 年营收 Y 亿"未找到外部源 | D 或删除 | 不能假装是事实，要么标 D 要么删 |
| 用户提供的某图 / 某段文字截图 | 看截图来源 | 截图来自 SEC 文件 → A；截图来自某群聊 → C |
| 知名学者在播客里的口头说法 | B | 算 journalist_longform，但要标"据 XX 在 YY 播客 ZZ 时刻" |
| arxiv 论文但作者自爆数据未公开 | A | 仍算 A，但 confidence_note 写"作者自报，未独立复现" |
| 业内群"内部消息"无署名爆料 | C | 不能升级，除非后续被官方或 A 级源证实再升 |

---

## 4. 信任度报告呈现

### JSON 形态
直接落到 `article.json.source_report`，字段定义见 `article-schema.md`。本文件不重定义字段，只规定**渲染逻辑**：

- `total_facts` = `facts[]` 数组长度
- `by_grade` = 按每条 fact 的 `grade` 计数
- `by_grade_pct` = 各 grade 占比，保留 1 位小数
- `confidence_stars` = 见第 5 节规则
- `confidence_rules` = 把命中的规则原文回写（让读者能复算）
- `limitations` = 数组，每条一句人话写"哪个事实不够强 / 为什么"

### HTML 形态（渲染到公众号文末）

直接 inline 样式，不依赖任何外链 / class，符合微信公号编辑器兼容性（见 `wechat_html_compat.md`）：

```html
<section style="margin-top: 2em; padding: 1em 1.2em; background:#f5f0e8; border-left:3px solid #8b3a3a; font-size: 14px; color:#666; line-height:1.7;">
  <p style="margin: 0; font-weight: bold; color:#8b3a3a;">本文来源透明度</p>
  <p style="margin: 0.5em 0 0;">A 级（一手原始）7 处 · B 级（权威二手）3 处 · C 级（普通二手）1 处 · 作者推断 1 处</p>
  <p style="margin: 0.3em 0 0;">置信度 ★★★★ · A 占比 58.3% (≥50%) + D 占比 8.3% (&lt;15%)</p>
  <p style="margin: 0.6em 0 0; font-size: 12px; color:#999;">限制：训练成本数据来自第三方推算，原文未披露</p>
</section>
```

**渲染要点**：
- 不要用 emoji 替代 ★（部分微信主题字体会乱码），就用 `★★★★`
- D 级不要写"D 级"——读者不懂，写"作者推断"
- `limitations` 数组每条用单独 `<p>`，最多 3 条，超过的合并成"等"

---

## 5. 置信度星级规则

| 星级 | 触发条件 | 典型例子 |
|---|---|---|
| ★★★★★ | A ≥ 60% **且** D = 0 | 拆解一篇 arxiv 论文 + 引用官方 blog + 财报数据，全程没有推断 |
| ★★★★ | A ≥ 50% **且** D < 15% | AI 行业分析：5 条官方数据 + 2 条路透/财新 + 1 处合理推算 |
| ★★★ | A ≥ 30% | 行业综述：部分官方源 + 较多深度报道 + 少量 KOL 观点 |
| ★★ | 上述都不满足 | 大量二手报道拼接，原始源较少 |
| ★ | D ≥ 30% | 历史回顾文 / 推测性长文，模型推断占比过大；标"参考价值有限" |

**判定顺序**：从上往下匹配，命中即停（★ 是兜底）。`confidence_rules` 字段必须把命中的判据原文写回，例如 `"A 占比 58.3% (≥50%) + D 占比 8.3% (<15%) → 4 星"`。

---

## 6. 来源透明度的"反向用途"

这套分级表不只是给读者看的"信任标签"，它还是一个三方都能用的基础设施：

- **读者**：扫一眼判断要不要相信、要不要转给同事；如果是 ★ 单星就当观点参考，不当数据引用
- **平台审核 / fact-checker**：每条 `fact` 在 `source_ref` 里指向了具体 `sr-id`，可以快速跳到原文核对，不用从头扒
- **被报道公司的公关 / 法务**：如果有错误投诉，能精确指向"你这篇文章引的 sr-007 是某某 KOL 微博，C 级，不是事实"，沟通效率比"你这篇文章瞎写"高得多

这就是分级的"信任基础设施"价值——把"我说的是真的"从一句口号变成一张可核查的表。长期看，这是把公众号写作从流量游戏拉回内容生意的关键变量之一。

---

## 7. 自检题（写完文章后逐条问自己）

1. `facts[]` 里 A 级是不是 ≥ 5 条？（少于 5 条说明搜集不够，回 §3 再搜）
2. 每条 D 级 fact 在正文对应位置是不是有 `<sup>未核证</sup>` / `<sup>据 X 推算</sup>` 标注？
3. 信任度报告 HTML 块在文末有没有？样式是不是 inline（没有外链 class）？
4. `confidence_stars` 字段和 HTML 里显示的星数是不是一致？（写脚本时常见 bug）
5. `confidence_rules` 字段是不是把判据原文写回了？（不能只写"4 星"，要写"为什么 4 星"）
6. `limitations` 数组是不是 ≥ 1 条？（任何文章都有限制，写"无"是偷懒）
7. 多源 fact 的 `grade` 是不是取了最高级？（核查 `source_ref` 长度 > 1 的条目）
8. `source_type = corporate_pr` 的内容有没有作为某事实的唯一来源？（如果有，必须降级或补强 A/B 源）

---

## 附录：和 distiller 系列的差异

`book-distiller` / `movie-distiller` / `domain-onboarding` 也用 A/B/C/D，但它们的 A 级是"原著文本 / 影片本身 / 学术教科书"。本文件适配公众号语境，把 A 级重新定义为"公司官方 / 论文 / 财报 / 政府数据"——因为公众号写的多是**正在发生**的事，没有"原著"可对照，最接近"原著"的就是当事方的直接出品。
