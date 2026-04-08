# 微信公众号 HTML 兼容性说明

## 支持的标签

以下标签可安全使用：

| 标签 | 用途 | 注意事项 |
|------|------|----------|
| `<section>` | 区块布局 | 最常用的布局容器 |
| `<p>` | 段落 | 基础段落 |
| `<span>` | 行内文本 | 配合 style 做样式 |
| `<strong>` / `<b>` | 加粗 | |
| `<em>` / `<i>` | 斜体 | |
| `<br>` | 换行 | |
| `<hr>` | 分割线 | 可用 style 自定义样式 |
| `<img>` | 图片 | src 必须为 mmbiz.qpic.cn 域名 |
| `<a>` | 超链接 | 仅支持公众号文章链接和白名单域名 |
| `<h1>`-`<h4>` | 标题 | 建议用 h2-h3 |
| `<blockquote>` | 引用块 | 自带左侧绿条样式 |
| `<ul>` / `<ol>` / `<li>` | 列表 | |
| `<table>` / `<tr>` / `<td>` | 表格 | 支持但样式需内联 |
| `<sup>` / `<sub>` | 上下标 | |

## 不支持的标签和特性

以下在微信中**无效**或**会被过滤**：

- `<script>` — 所有 JavaScript 被过滤
- `<style>` — 外部/内部样式表不支持，只能用 inline style
- `<iframe>` — 不支持嵌入
- `<form>` / `<input>` / `<button>` — 不支持表单
- `<video>` / `<audio>` — 需使用微信自有的音视频组件
- `<link>` / `<meta>` — 不支持
- `class` / `id` 属性 — 会被过滤，所有样式必须 inline
- `position: fixed` / `position: absolute` — 不支持定位
- `float` — 部分支持，不推荐使用
- `@media` 查询 — 不支持
- `animation` / `transition` — 不支持
- 外部字体 — 不支持 `@font-face`

## 样式编写规范

所有样式必须通过 `style` 属性内联：

```html
<!-- 正确 -->
<p style="font-size: 15px; color: #3f3f3f; line-height: 1.8; margin-bottom: 20px;">
  段落内容
</p>

<!-- 错误 — class 会被过滤 -->
<p class="paragraph">段落内容</p>
```

## 图片规范

```html
<!-- 正确：使用微信域名图片 -->
<img src="https://mmbiz.qpic.cn/mmbiz_jpg/xxxxx/0?wx_fmt=jpeg"
     style="width: 100%; height: auto; display: block; margin: 10px auto;"
     data-ratio="0.667" data-type="jpeg" />

<!-- 错误：使用外部图片 -->
<img src="https://example.com/image.jpg" />
```

图片必须先通过 `POST /cgi-bin/media/uploadimg` 上传获取微信域名URL。

## 超链接规范

```html
<!-- 支持：公众号文章链接 -->
<a href="https://mp.weixin.qq.com/s/xxxxx" style="color: #1e88e5;">阅读原文</a>

<!-- 支持：白名单域名（如腾讯系产品） -->
<a href="https://weixin.qq.com/xxxxx">链接</a>

<!-- 不支持：普通外链 — 点击无效 -->
<a href="https://github.com/xxx">不会生效</a>
```

## 常用排版 HTML 模板

### 标题样式
```html
<h2 style="font-size: 18px; font-weight: bold; color: #1a1a1a; border-left: 4px solid #1e88e5; padding-left: 12px; margin: 30px 0 15px 0;">
  章节标题
</h2>
```

### 强调色块
```html
<section style="background: #f7f7f7; border-left: 3px solid #ff6b35; padding: 15px 20px; margin: 15px 0; border-radius: 0 4px 4px 0;">
  <p style="font-size: 15px; color: #666; line-height: 1.8; margin: 0;">
    重点内容
  </p>
</section>
```

### 引用块
```html
<blockquote style="border-left: 3px solid #ccc; padding: 10px 15px; color: #999; font-size: 14px; margin: 15px 0;">
  引用文字
</blockquote>
```

### 分割线
```html
<hr style="border: none; border-top: 1px dashed #eaeaea; margin: 25px 0;" />
```

### 图片带说明
```html
<section style="text-align: center; margin: 20px 0;">
  <img src="微信域名图片URL" style="width: 100%; height: auto; border-radius: 4px;" />
  <p style="font-size: 12px; color: #999; margin-top: 8px;">图片说明文字</p>
</section>
```
