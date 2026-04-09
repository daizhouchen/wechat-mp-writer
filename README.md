# wechat-mp-writer

微信公众号内容创作与发布 Claude Code Skill。从信息搜集、内容撰写、排版到 API 发布的端到端全自动工作流。

## 功能

- **用户画像持久化**：首次配置公众号定位、读者画像、写作风格、关注赛道，保存为 `.wechat-profile.md`，后续每次创作自动加载
- **主动信息搜集**：接到主题后自动用 WebSearch/WebFetch 搜集行业数据、专家观点、竞品分析，先出素材卡再动笔
- **去 AI 味创作**：禁止 emoji 装饰、禁止 AI 套话、像人类专家一样写作，输出有观点有温度的内容
- **多风格标题生成**：数字式/悬念式/痛点式/对比式/权威式/故事式等 8 种风格，生成 5+ 候选标题
- **8 种内容模板**：干货教程、观点评论、行业分析、产品介绍、活动推广、人物故事、盘点清单、对比测评
- **微信兼容 HTML 排版**：4 套预设配色、完整的文字层级体系、移动端适配
- **智能图片获取**：按内容实体搜索关联图片（而非泛泛的主题图片），自动下载、上传到微信服务器并替换
- **API 发布工作流**：创作 -> 上传素材 -> 存草稿 -> 预览 -> 确认 -> 发布
- **一条龙模式**：说"一条龙"或"全自动"，从搜集资料到发布全程无需确认，自动完成
- **合规检查**：广告法极限词检测、敏感词提醒、发布前二次确认
- **SEO 优化**：搜一搜关键词策略、社交传播优化、发布时间推荐、转发引导话术

## 安装

### 方式一：通过 Claude Code CLI 安装（推荐）

```bash
# 1. 注册 marketplace
claude plugin marketplace add https://github.com/daizhouchen/wechat-mp-writer.git

# 2. 安装插件（全局）
claude plugin install wechat-mp-writer@wechat-mp-writer --scope user

# 3. 重新加载（在 Claude Code 中执行）
/reload-plugins
```

安装完成后，在任何对话中说"写一篇公众号文章"或输入 `/wechat-mp-writer:wechat-mp-writer` 即可触发。

### 方式二：手动安装

```bash
# 克隆仓库
git clone https://github.com/daizhouchen/wechat-mp-writer.git

# 复制到 Claude Code 插件目录
cp -r wechat-mp-writer ~/.claude/plugins/cache/wechat-mp-writer/wechat-mp-writer/1.0.0/

# 在 Claude Code 中重新加载
/reload-plugins
```

### 卸载

```bash
claude plugin uninstall wechat-mp-writer@wechat-mp-writer
claude plugin marketplace remove wechat-mp-writer
```

## 配置

### 1. 公众号画像配置（首次使用时自动引导）

Skill 会引导你配置公众号定位、目标读者、写作风格等，保存为项目目录下的 `.wechat-profile.md`，后续自动加载。

### 2. 微信公众平台 API 凭据

发布功能需要配置 API 凭据：

```bash
# 在项目目录创建 .env 文件
cat > .env << 'EOF'
WECHAT_APP_ID=your_app_id
WECHAT_APP_SECRET=your_app_secret
WECHAT_PREVIEW_USER=your_wechat_id
EOF
```

获取方式：登录 [mp.weixin.qq.com](https://mp.weixin.qq.com) -> 设置与开发 -> 基本配置

验证：
```bash
python3 skills/wechat-mp-writer/scripts/wechat_api.py check
```

> 注意：预览和发布 API 需要**已认证的订阅号或服务号**。未认证账号可以正常创建草稿，然后在公众号后台手动发表。

## 使用方式

### 标准模式（带确认）

```
帮我写一篇关于 AI Agent 的公众号文章
```

Skill 会按步骤执行：搜集信息 -> 展示素材卡 -> 等你选角度 -> 生成标题候选 -> 撰写全文 -> 获取图片 -> 等你确认 -> 发布

### 一条龙模式（全自动）

```
一条龙帮我写一篇 AI 行业洞察的公众号文章并发布
```

从搜集资料到发布全程自动，无需任何确认。完成后输出简报。

## 目录结构

```
wechat-mp-writer/
├── .claude-plugin/
│   ├── plugin.json                 # 插件描述
│   └── marketplace.json            # Marketplace 注册信息
├── skills/
│   └── wechat-mp-writer/
│       ├── SKILL.md                # Skill 主文件（完整工作流指令）
│       ├── scripts/
│       │   ├── wechat_api.py       # 微信API工具（token/素材/草稿/发布）
│       │   └── compliance_check.py # 内容合规检查
│       └── references/
│           ├── content_templates.md    # 8种内容类型模板
│           ├── wechat_html_compat.md   # 微信HTML兼容性 + 排版组件
│           └── error_codes.md          # API错误码对照表
├── README.md
└── .gitignore
```

## License

MIT
