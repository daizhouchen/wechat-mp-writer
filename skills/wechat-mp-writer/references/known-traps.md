# 已知陷阱清单（v2.1 实战沉淀）

> 这份文档是「$500K vs 月薪 4 万」一文 5 版迭代踩出来的所有坑。每条都附**现象 / 根因 / 解决 / 预防 check**。读完这份文档，你不会重复踩同样的坑。

## 用法

写文章前过一遍「预防 check」清单。debug 时按现象关键词搜本文档。

---

## 类目 A · 微信编辑器渲染陷阱（5 条）

### A1 · 表头白字+深底在微信里被滤成"无色差"

**现象**：表格表头用 `background: #7a5500; color: #fff`，本地浏览器看清晰，进微信编辑器后白字消失或变成默认色，表头跟普通行没色差。

**根因**：微信编辑器对某些 inline `color: #fff` + `background: <dark>` 组合有"美化滤镜"，会丢失部分样式。

**解决**：**双保险设计** — 任何颜色对比都至少 **background + color + border 三重防线**：
```html
<!-- ✗ 错 -->
<th style="background: #7a5500; color: #fff;">维度</th>

<!-- ✓ 对：浅底 + 深色字 + 底部 3px 强调线 -->
<th style="background: #f5f0e8; color: #7a5500; font-weight: 700;
           border-bottom: 3px solid #7a5500;">维度</th>
```

任何一层被滤掉，剩下两层仍保证色差可读。

**预防 check**：所有 `color: #fff` 配 dark `background` 的组合都要审计。layout-components.md 组件 4 已给出双保险表头模板。

---

### A2 · digest 上限是 120 字节不是 120 字符

**现象**：跑 `add_draft` 时返 `45004 description size out of limit`。digest 文案明明只有 100 字。

**根因**：微信文档说"120 字符"，实际接口校验的是 **120 字节**。中文 UTF-8 是 3 字节/字 → 实际只能塞 ~40 个汉字。

**解决**：digest 文案压到 **40 中文字符** 以内（或 120 字节内）。

**预防 check**：
- quality_check.py v2.1 加 `digest_byte_size` 指标自动扫
- publish.sh v2.1 加自动二分截断逻辑

---

### A3 · 48001 接口未授权（个人订阅号 / 未认证号）

**现象**：跑 `preview` 或 `freepublish/submit` 都返 `48001 api unauthorized`。

**根因**：你的公众号是**个人订阅号**或**未微信认证**。这两种状态下：
- ✓ 可用：access_token / draft/add / draft/update / material/add_material / media/uploadimg
- ✗ 不可用：message/mass/preview / freepublish/submit / 群发等高权接口

**解决**：
- 个人创作场景：跑到 draft 即停，登录 mp.weixin.qq.com 后台手动「发表」
- 长期需要全自动 → 升级到「服务号」或「订阅号 + 微信认证」（年费 300 元）

**预防 check**：v2.1 的 `wechat_api.py check` 命令会预探接口权限矩阵，提前告诉你能干什么不能干什么。

---

### A4 · 公众号样式过滤的"黑名单"

**现象**：本地浏览器看着排版好好的，进微信编辑器变样。

**根因**：微信编辑器只支持 inline style 的子集。已知会被滤的：
- `class` / `id` 属性 → 全部忽略
- `<style>` 标签 → 内容忽略
- `position: fixed/absolute/sticky` → 失效
- `@media` 查询 → 失效
- `animation` / `transition` → 失效
- 部分 `color: #fff` 组合（见 A1）
- 外部字体 `@font-face` / Google Fonts → 失效

**解决**：所有样式必须 inline；任何"花活"都要在微信编辑器里实测。

**预防 check**：layout-components.md 里的 9 个组件全部已经实测兼容微信。

---

### A5 · 外链跳转无效

**现象**：正文 `<a href="https://example.com">` 在公众号里点击无反应。

**根因**：公众号正文只支持公众号互链（`mp.weixin.qq.com/s/...`）和白名单域名。

**解决**：
- 引用外部文章 → 把 URL 写成纯文本，让读者复制
- 推荐自己的文章 → 用公众号互链
- 不要在正文挂 GitHub / Medium / 个人博客的链接

**预防 check**：quality_check.py 的 `external_links` 指标会扫到。

---

## 类目 B · 封面 SVG 制作陷阱（3 条）

### B1 · 多字号文字混排时 baseline 对齐塌

**现象**：封面里 `$500K vs 月薪 4 万`，"vs" 和大字看着对不齐，要么偏上要么偏下。

**根因**：默认 SVG `<text>` 用 alphabetic baseline（基线在字母底部）。两个不同字号的文字共享同一 y 时，小字看起来"沉"在大字下面。

**解决**：小字单独用 `dominant-baseline="central"` + 调 y 让中线和大字中心对齐：
```svg
<!-- $500K 字号 100, y=220（baseline）→ 视觉中心 y≈190 -->
<text x="60" y="220" font-size="100" font-weight="bold">$500K</text>
<!-- vs 字号 60, dominant-baseline="central" + y=190 让中线对齐 -->
<text x="430" y="190" font-size="60" dominant-baseline="central">vs</text>
<text x="540" y="220" font-size="100" font-weight="bold">月薪 4 万</text>
```

**预防 check**：image-pipeline.md §12 封面 SVG 模板库的 4 个模板都已修复此坑。

---

### B2 · file:// 协议被 playwright 阻止

**现象**：用 `mcp__playwright_browser_navigate` 访问 `file:///path/to/cover.html` 报错 `Access to "file:" protocol is blocked`。

**根因**：playwright 默认禁用 `file://` 协议（安全考虑）。

**解决**：起本地 http server：
```bash
cd ./images && python3 -m http.server 9876 &
playwright_navigate("http://127.0.0.1:9876/cover-render.html")
```

**预防 check**：publish.sh 模板里有现成的 helper 段。

---

### B3 · SVG → PNG 没现成工具

**现象**：环境没装 `rsvg-convert` / `imagemagick` / `inkscape`，cairosvg 也没。

**根因**：常见 minimal Linux 环境只有 stdlib，SVG 转换工具普遍缺失。

**解决**：用 playwright 截图作为通用 SVG → PNG 路径：
1. SVG 包进 HTML 设 viewport
2. 起 http server
3. playwright 加载 + screenshot → PNG

**预防 check**：image-pipeline.md §12 标明此为通用流程。

---

## 类目 C · wechat_api.py 调用陷阱（3 条）

### C1 · stdout 混有日志和 JSON

**现象**：`python3 wechat_api.py upload_image x.png | jq` 失败，因为开头有 "✓ 图片上传成功" 等非 JSON 行。

**根因**（v2.0 时）：所有 print 都到 stdout，混了人类日志和机器 JSON。

**解决**（v2.1 已改）：
- 人类日志全部改写到 `sys.stderr`
- stdout 只留纯 JSON
- 旧脚本调用 `tail -1 | jq` 仍兼容

**预防 check**：v2.1 的 wechat_api.py 已做完。新脚本调用直接 `python3 wechat_api.py xxx | python3 -c "import json,sys; print(json.load(sys.stdin)['url'])"` 即可。

---

### C2 · publish.sh 跨目录跑时 .env 找不到

**现象**：在 `./articles/<slug>/` 目录跑 `./publish.sh` 报 `WECHAT_APP_ID 未设置`，但根目录有 .env。

**根因**：`wechat_api.py` 的 `_load_dotenv` 只看 `Path.cwd()` / 脚本目录 / `Path.home()`，不会向上递归找。

**解决**：publish.sh 自己显式 source .env，向上找 5 层目录：
```bash
for d in . .. ../.. ../../.. ../../../.. "$HOME"; do
  [ -f "$d/.env" ] && { set -a; source "$d/.env"; set +a; break; }
done
```

**预防 check**：v2.1 的通用 publish.sh 已内置此逻辑。

---

### C3 · 草稿堆积无 update / delete 接口

**现象**：每次改完跑 publish.sh 都创建新草稿，迭代 5 版后草稿箱里 5 篇同名稿，用户手动删。

**根因**（v2.0 时）：wechat_api.py 只有 `add_draft`，没 `update_draft` / `delete_draft`。

**解决**（v2.1 已加）：
- `update_draft --media_id <id>` 覆盖更新
- `delete_draft --media_id <id>` 删除
- `list_drafts` 列草稿箱

publish.sh 加 `--update <id>` 参数覆盖更新。

**预防 check**：迭代时用 `./publish.sh --update <draft_id>` 而不是裸跑 `./publish.sh`。

---

## 类目 D · 内容质量陷阱（3 条）

### D1 · 字数算法只数中文字符（低估）

**现象**：科技文里大量英文实体（OpenAI / Anthropic / Sam Altman / evals），只数中文得 1610 字，实际阅读量 2700+ 字。quality_check 报 "字数不足"，但读起来不薄。

**根因**（v2.0 时）：`count_chinese_chars()` 只数 `'一'-'鿿'`，英文 token 全忽略。

**解决**（v2.1 已改）：用 `count_mixed_reading_length()`：
```python
阅读量 = 中文字符数 + 英文 token 数 × 0.5
```

**预防 check**：v2.1 的 quality_check.py 已用混合算法。

---

### D2 · 素材浪费（搜了不用）

**现象**：v1 信息搜集阶段抓了 14 条 search_results，成稿只引用 7 条（Marily Nika 三 persona 只一句带过）。读者读到「内容太薄」，写作者也觉得"白搜了"。

**根因**：SKILL.md / content-engine.md 没有"素材榨干率"指标，搜了多少 vs 用了多少没人扫。

**解决**（v2.1）：
- content-engine.md 新增 §"素材榨干率"：每条 `search_results[]` 至少在 `facts[]` 被引用一次
- quality_check.py 加 `material_utilization` 指标：< 80% warn，< 60% fail
- 不达标的两个选择：① 补 facts 引用未用素材 ② 删除未用 search_results

**预防 check**：写完跑 quality_check 看 `material_utilization` 数。

---

### D3 · 默认排版像个人博客

**现象**：v2 默认输出「H2 + 段落 + 引用块」三件套，读者觉得"普通"，达不到新智元 / 量子位 / 晚点 LatePost 那种深稿大刊感。

**根因**（v2.0 时）：SKILL.md §5 排版规范只列了「色块、引用、列表、图片」等通用元素，没有可直接复用的组件库。

**解决**（v2.1 已加）：
- 新增 `references/layout-components.md` — 9 个 inline-style 组件
- SKILL.md §5 强制每篇 ≥4 个组件
- 章节大数字编号 / pull quote / 数据卡 / 三色 persona 卡 / 圆点列表 / 装饰分割 / 编号圆 / 进阶补充框 / 富对比表

**预防 check**：article.json `meta.layout_variant.components_used` 记录用了哪些；quality_check 扫数量。

---

## 类目 E · 去 AI 痕迹陷阱（2 条）

### E1 · 信任度报告 / 图注 / tagline 一眼 AI

**现象**：v2 默认渲染：
- 文末「信任度评分 ★★★★ · A 占比 42.9%...」
- 每张图下方「图：xxx / Wikimedia · CC-BY-SA」
- 顶部「daizhouchen 实验集 · 一个 AI 应用创造者的实验现场」

读者一眼识别"这是 AI 写的"。

**根因**：distiller 系列把信任度报告 + 来源标注当成"专业"功能，但公众号生态里这些是 AI 痕迹。

**解决**（v2.1）：
- 默认 **不渲染** 到 HTML：信任度报告、图 caption（"图：来源 xxx"）、内部 ID（fact-001 / sr-005）、AI tagline
- 这些字段**只活在 article.json 内部**供 quality_check 用
- SKILL.md 新增「去 AI 痕迹」独立大章节
- profile 默认 `hide_ai_traces: true`

**预防 check**：quality_check.py v2.1 的 `ai_traces` 指标自动扫成稿 HTML 里有无以下字符串：
- 信任度 / 置信度 / 来源透明度 / A 占比.* %
- 图：xxx Wikimedia CC-BY 来源
- fact-N / sr-N / img-* 内部 ID
- ★ 评分星
- "由 Claude 生成" / "AI 工具产出"

任一命中即 fail。

---

### E2 · 图注语义不对应

**现象**：sec-3 讲 evals 配 Anthropic A logo，图注写"▲ Anthropic 把 evals 写进 JD 的具体公司"——logo 跟"具体公司"语义有距离，读者觉得"图跟图注不挨着"。

**根因**：AI 喜欢给图加"严谨说明"，但图本身（logo）和说明（论点）语义上经常错位。

**解决**：**所有图都不加 caption**。图就是图，旁边段落自然承接。这既解决"图注不对应"，又解决"图注本身是 AI 痕迹"。

**预防 check**：layout-components.md 组件 9 默认无 caption；E1 的 `ai_traces` 扫 "图：" 关键词。

---

## 速查索引

按现象搜本文档：

| 现象关键词 | 跳转 |
|---|---|
| 表头没色差 / 表头看不清 | A1 |
| 45004 description size | A2 |
| 48001 unauthorized | A3 |
| 排版进微信变样 | A4 |
| 外链点不动 | A5 |
| vs 字错位 / 大字小字对不齐 | B1 |
| file:// blocked | B2 |
| SVG 转 PNG 没工具 | B3 |
| stdout 混 JSON 和日志 | C1 |
| publish.sh .env 找不到 | C2 |
| 草稿箱堆积 | C3 |
| 字数太少（实际不薄） | D1 |
| 内容太薄 / 素材没用上 | D2 |
| 排版像个人博客 | D3 |
| 一眼像 AI 写的 | E1 |
| 图与图注对不上 | E2 |

---

## 沉淀来源

「$500K vs 月薪 4 万：真假 AI PM 分水岭」 5 版迭代真实记录：

- v1：基础流程 quality_check 21/21 ✓ 信任度 ★★★★
- v2：发现 publish.sh 跨目录 .env 失败 → 修复（C2）
- v2：发现 stdout 混 JSON → tail -1 临时救场（C1）
- v2：digest 45004 → 压缩文案（A2）
- v2：48001 接口权限缺失 → 跳过 publish（A3）
- v3：发现一眼 AI → 改 profile + 全删信任度报告 + caption + tagline（E1, E2）
- v3：发现封面 vs 错位 → dominant-baseline=central（B1）
- v4：用户反馈"内容太少"→ 加厚到 8 节，把搜的料全榨出来（D2）
- v5：用户反馈"排版能不能更好看"→ 加 8 个组件（D3）
- v5：用户反馈"表头没色差"→ 双保险设计（A1）

每个坑都是真金白银（时间）换来的。
