# 排版组件库（v2.1）

## 0. 这份文档要解决什么

v2 的默认排版只是「H2 + 段落 + 引用块」，看着像个人博客。v2.1 要把默认排版做到「晚点 LatePost / 量子位 / 36氪深度组」那种公号大刊水平——每个组件都是 inline-style，可直接 paste 到微信编辑器，9 个组件覆盖深稿写作 90% 场景。

**硬约束**：每篇文章必须用 **≥ 4 个组件**（在 SKILL.md §5 有强制要求 + quality_check.py 扫）。

---

## 设计原则（先读再用）

1. **全 inline style**：微信编辑器只认 inline，class/id 全被滤
2. **双保险设计**：任何颜色对比都至少 background + color + border 三重，避免微信编辑器把单一 color/background 滤掉时不可读
3. **暖橙 #7a5500 是默认主色**，浅米黄 #fdf8ee / 卡片浅米 #f5f0e8 是默认浅底——但每篇可以按 profile 的 accent_color 替换
4. **无 emoji 装饰**（红线 1）；箭头/星星等 unicode 装饰也禁止（被 emoji 词库扫到）
5. **不要全部组件堆一篇**：4-7 个组件足够，超过 8 个视觉密度过高

---

## 组件 1：章节大数字编号

**用途**：每个 H2 替代品。Georgia 衬线大字 + 装饰短线，扫读时强视觉锚。
**适用骨架**：`comparison_table` / `list_breakdown` / `qa_list` / `timeline`
**频率**：每个一级章节用一次（一篇 5-8 个）。

```html
<section style="margin: 50px 0 22px 0;">
  <div style="display: flex; align-items: baseline; gap: 14px; margin-bottom: 8px;">
    <span style="font-size: 36px; font-weight: 700; color: #7a5500; line-height: 1; font-family: Georgia, serif;">01</span>
    <span style="font-size: 12px; color: #7a5500; letter-spacing: 3px; flex: 1;">— — — — — — — — — —</span>
  </div>
  <h2 style="font-size: 19px; font-weight: bold; color: #1a1a1a; margin: 0; line-height: 1.5;">章节标题在这里</h2>
</section>
```

**色变**：朱砂主调时 `color: #8b3a3a`；深青时 `color: #1e4d8b`。

---

## 组件 2：Pull quote 拉引用块

**用途**：把核心金句独立呼吸，serif 字体 + 浅米黄底显示这是「重点」。
**适用骨架**：所有
**频率**：一篇 2-4 处，过多失去强调作用。

```html
<section style="border-left: 3px solid #7a5500; background: #fdf8ee; padding: 16px 22px; margin: 24px 0; border-radius: 0 4px 4px 0;">
  <p style="font-size: 17px; line-height: 1.75; color: #1a1a1a; margin: 0; font-weight: 500; font-family: Georgia, 'Songti SC', serif;">
    在这里写最值得拎出来的那句话。一般是金句、判断、反常识结论。
  </p>
</section>
```

**注意**：只放金句不放论证。论证段落继续用普通 `<p>`。

---

## 组件 3：首屏数据卡

**用途**：开头 200 字内甩出关键数字，3 秒抓住注意力。`data_lead` 骨架的视觉锚。
**适用骨架**：`data_lead`（必用）/ `comparison_table`（强烈推荐）

```html
<section style="background: linear-gradient(180deg, #fdf8ee 0%, #fff 100%); padding: 22px 22px 12px; margin: 0 0 28px; border-radius: 8px; border: 1px solid #f5f0e8;">
  <p style="margin: 0 0 14px;">
    <span style="font-size: 32px; font-weight: 700; color: #7a5500; font-family: Georgia, serif;">$500K</span>
    <span style="font-size: 14px; color: #666; margin-left: 10px;">Anthropic Consumer PM · base + equity + signing</span>
  </p>
  <p style="margin: 0 0 14px;">
    <span style="font-size: 32px; font-weight: 700; color: #1a1a1a; font-family: Georgia, serif;">¥4.5w</span>
    <span style="font-size: 14px; color: #666; margin-left: 10px;">国内某二线大厂「AI 产品经理」· 月薪</span>
  </p>
  <p style="margin: 0; color: #3f3f3f; font-size: 14px;">两边都叫 AI PM，但只要把 JD 摊开 5 分钟，你会发现是两种工种。</p>
</section>
```

**变体**：单数字时省去 `<p>` 重复块；3+ 数字时考虑改用「圆点列表卡」（组件 5）。

---

## 组件 4：富对比表（双保险表头）

**用途**：横评 / 多维度对比的核心视觉锚。
**适用骨架**：`comparison_table`（必用）

```html
<section style="margin: 24px 0; overflow-x: auto;">
  <table style="width: 100%; border-collapse: collapse; font-size: 14px; line-height: 1.65; border-radius: 8px; overflow: hidden;">
    <thead>
      <tr style="background: #f5f0e8;">
        <th style="padding: 14px 10px; text-align: left; color: #7a5500; font-weight: 700; font-size: 15px; border-bottom: 3px solid #7a5500; width: 22%;">维度</th>
        <th style="padding: 14px 10px; text-align: left; color: #7a5500; font-weight: 700; font-size: 15px; border-bottom: 3px solid #7a5500;">A 列</th>
        <th style="padding: 14px 10px; text-align: left; color: #7a5500; font-weight: 700; font-size: 15px; border-bottom: 3px solid #7a5500;">B 列</th>
      </tr>
    </thead>
    <tbody>
      <tr style="background: #fff;">
        <td style="padding: 12px 10px; border-bottom: 1px solid #f0eadb; vertical-align: top;"><strong style="color: #7a5500;">行项 1</strong></td>
        <td style="padding: 12px 10px; border-bottom: 1px solid #f0eadb; vertical-align: top;">A 内容</td>
        <td style="padding: 12px 10px; border-bottom: 1px solid #f0eadb; vertical-align: top; color: #666;">B 内容</td>
      </tr>
      <tr style="background: #fdf8ee;">
        <td style="padding: 12px 10px; border-bottom: 1px solid #f0eadb; vertical-align: top;"><strong style="color: #7a5500;">行项 2</strong></td>
        <td style="padding: 12px 10px; border-bottom: 1px solid #f0eadb; vertical-align: top;">A 内容</td>
        <td style="padding: 12px 10px; border-bottom: 1px solid #f0eadb; vertical-align: top; color: #666;">B 内容</td>
      </tr>
      <!-- 更多行：交替 #fff / #fdf8ee -->
    </tbody>
  </table>
</section>
```

**双保险关键**（known-traps 验证过的）：
- 表头 **不要** 用 `background: #7a5500; color: #fff`（白字在某些微信渲染下被滤）
- 必须 **浅底 + 深色字 + 底部 3px 强调线** 三重防线
- 隔行变色用 `#fff` / `#fdf8ee`（不要太深，不然字色对比也弱）

---

## 组件 5：圆点列表卡

**用途**：列举性内容（5-9 项的赛道、工具、要点等）。比裸 `<ul>` 更有质感。
**适用骨架**：所有；尤其 `list_breakdown` / `qa_list`

```html
<section style="background: #fafaf5; padding: 18px 20px; border-radius: 8px; margin: 20px 0;">
  <div style="display: flex; gap: 12px; margin-bottom: 12px; align-items: flex-start;">
    <span style="flex-shrink: 0; width: 6px; height: 6px; background: #7a5500; border-radius: 50%; margin-top: 11px;"></span>
    <div style="flex: 1;">
      <span style="font-weight: 600; color: #1a1a1a; font-size: 15px;">名称</span>
      <span style="color: #666; font-size: 14px; margin-left: 6px;">— 一句话描述</span>
    </div>
  </div>
  <!-- 重复多个 -->
</section>
```

---

## 组件 6：三色 persona 卡

**用途**：分类型横向比较（如 Marily Nika 三种 AI PM persona）。每张卡独立色边框暗示分类。
**适用骨架**：`comparison_table` / `list_breakdown` / 任何需要分人群/分类型的

```html
<section style="border: 1px solid #eee; border-left: 4px solid #8b3a3a; border-radius: 6px; padding: 18px 20px; margin-bottom: 16px;">
  <div style="display: flex; align-items: baseline; gap: 12px; margin-bottom: 8px;">
    <span style="font-size: 24px; font-weight: bold; color: #8b3a3a; line-height: 1; font-family: Georgia, serif;">①</span>
    <h3 style="font-size: 16px; font-weight: bold; color: #1a1a1a; margin: 0;">第一类标题</h3>
  </div>
  <p style="font-size: 13px; color: #666; margin: 0 0 8px; line-height: 1.7;">
    <strong style="color: #8b3a3a;">代表</strong>　XXX, YYY
  </p>
  <p style="font-size: 13px; color: #666; margin: 0 0 8px; line-height: 1.7;">
    <strong style="color: #8b3a3a;">日常</strong>　日常工作描述
  </p>
  <p style="font-size: 13px; color: #666; margin: 0; line-height: 1.7;">
    <strong style="color: #8b3a3a;">画像</strong>　适合什么样的人
  </p>
</section>

<!-- 第二张卡：边框换色 #7a5500 / 第三张：#5c4a3a -->
```

**色组建议**（按主题）：
- 通用三色：`#8b3a3a`（朱砂） + `#7a5500`（暖橙） + `#5c4a3a`（大地色）
- 科技主题：`#1e4d8b`（深青） + `#7a5500` + `#3a3a3a`
- 永远是同色系内浓淡，不要彩虹色

---

## 组件 7：装饰分割「· · ·」

**用途**：章节切换时给读者呼吸点。比 `<hr>` 优雅。
**频率**：每篇 3-5 处；不要每个 H2 后都放（重复）。

```html
<p style="text-align: center; color: #7a5500; letter-spacing: 12px; margin: 36px 0; font-size: 14px;">· · ·</p>
```

**变体**：
- 简洁：`<p style="text-align:center; color:#ccc; margin:36px 0; font-size:14px;">·　·　·</p>`
- 中文古籍风：`<p style="text-align:center; color:#7a5500; margin:36px 0; letter-spacing:8px; font-size:16px; font-family: Songti SC, serif;">— 　— 　—</p>`

---

## 组件 8：编号圆 + 进阶补充框

**用途**：自查题、行动清单、步骤分解的视觉化。
**适用**：CTA / 自查 / How-to 段落

### 8a 编号圆

```html
<section style="display: flex; gap: 14px; margin-bottom: 16px; align-items: flex-start;">
  <span style="flex-shrink: 0; width: 28px; height: 28px; background: #7a5500; color: #fff; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 14px; font-weight: bold;">1</span>
  <span style="flex: 1; font-size: 15px; line-height: 1.7; color: #3f3f3f; padding-top: 3px;">问题 1 内容…</span>
</section>
```

### 8b 进阶补充框（CTA 强引导）

```html
<section style="background: #fdf8ee; padding: 18px 22px; border-radius: 8px; margin: 24px 0; border-left: 4px solid #7a5500;">
  <p style="font-size: 14px; color: #7a5500; font-weight: 600; margin: 0 0 10px;">如果你想往下深一层</p>
  <p style="font-size: 14px; color: #3f3f3f; line-height: 1.75; margin: 0;">
    具体可执行的 1-3 个起手动作，每个动作要可量化、可在一周内见成果。
  </p>
</section>
```

---

## 组件 9：图片渲染默认值（v2.1 新增）

**用途**：所有 inline 图片默认带圆角 + 阴影，封面更厚阴影。**裸图禁止**。

### 9a 普通正文图

```html
<section style="text-align: center; margin: 28px 0;">
  <img src="..." alt="..." style="width: 100%; height: auto; border-radius: 8px; box-shadow: 0 2px 12px rgba(0,0,0,0.06);"/>
</section>
```

### 9b 封面图（更厚阴影）

```html
<section style="text-align: center; margin: 24px 0 30px;">
  <img src="..." alt="..." style="width: 100%; height: auto; border-radius: 8px; box-shadow: 0 2px 12px rgba(0,0,0,0.08);"/>
</section>
```

### 9c 实体 logo（深底白图标，需加 padding）

```html
<section style="text-align: center; margin: 30px 0;">
  <img src="..." alt="..." style="max-width: 200px; height: auto; border-radius: 8px; background: #1a1a1a; padding: 24px;"/>
</section>
```

### 9d 字标 logo（透明底，无 padding）

```html
<section style="text-align: center; margin: 30px 0;">
  <img src="..." alt="..." style="max-width: 280px; height: auto;"/>
</section>
```

**禁止**：图下方加「图：来源 xxx / Wikimedia / CC-BY」caption（去 AI 痕迹红线，详见 SKILL.md §「去 AI 痕迹」）。

---

## 组件组合速查（按骨架）

| 骨架 | 必备组件 | 推荐组件 |
|---|---|---|
| `data_lead`（数据先行） | 1 + 3 + 4 | 2, 7, 9 |
| `story_open`（故事开篇） | 1 + 2 + 9 | 7, 8b |
| `qa_list`（问答列表） | 1 + 5 + 8a | 2, 7 |
| `timeline`（时间线） | 1 + 5 | 2, 6, 7 |
| `comparison_table`（对比表）| 1 + 4 + 6 | 2, 3, 7, 9 |
| `list_breakdown`（拆解清单）| 1 + 6 / 8a | 2, 5, 7, 8b |
| `quote_montage`（引语集）| 1 + 2（每条引语都用 pull quote） | 9 (人物头像), 7 |

---

## 与 SKILL.md / quality_check.py 对接

- SKILL.md §5 排版规范：默认引用本文件，每篇 ≥4 组件
- quality_check.py 加 `min_components` 检测（数 HTML 中本文件特征样式出现次数）
- article.json `meta.layout_variant.components_used: ["component_1", "component_4", ...]` 记录用了哪些

---

## 自检题（写完文章扫一遍）

1. 用了 ≥4 个组件吗？
2. 章节大数字（组件 1）是不是每个一级章节用一次？
3. Pull quote（组件 2）是不是只用在金句？2-4 处？
4. 对比表表头是不是浅底深字双保险（组件 4）？没用 white-on-dark？
5. 图片是不是都带圆角阴影（组件 9）？没有裸图？
6. 装饰分割（组件 7）是不是 3-5 处？没每个 H2 都用？
7. 颜色是不是同色系？没出现彩虹色 / 多种主色混搭？
