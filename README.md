# wechat-mp-writer

微信公众号内容创作与发布 Claude Code Skill。

## 功能

- **内容创作**：多风格标题生成、多模板正文结构（干货教程/观点评论/行业分析/产品介绍/活动推广/人物故事）、风格参数化
- **排版规范**：手机端适配、配色方案、图片节奏控制
- **微信兼容 HTML**：输出符合微信公众号编辑器限制的内联样式 HTML
- **API 发布工作流**：创作 → 上传素材 → 草稿 → 预览 → 确认 → 发布
- **合规检查**：广告法极限词检测、敏感词提醒、发布前二次确认
- **SEO 优化**：关键词布局建议、发布时间推荐、转发引导话术

## 安装

将本目录放入 Claude Code 的 skill 目录中，或作为 plugin 安装。

## 配置

首次使用需要配置微信公众平台 API 凭据：

```bash
# 设置环境变量
export WECHAT_APP_ID=your_app_id
export WECHAT_APP_SECRET=your_app_secret

# 或创建 .env 文件
echo "WECHAT_APP_ID=your_app_id" > .env
echo "WECHAT_APP_SECRET=your_app_secret" >> .env
```

验证配置：
```bash
python3 scripts/wechat_api.py check
```

## 目录结构

```
wechat-mp-writer/
├── SKILL.md                        # Skill 主文件
├── scripts/
│   ├── wechat_api.py               # 微信API工具（token/素材/草稿/发布）
│   └── compliance_check.py         # 内容合规检查
├── references/
│   ├── content_templates.md        # 内容类型模板
│   ├── wechat_html_compat.md       # 微信HTML兼容性说明
│   └── error_codes.md              # API错误码对照表
└── README.md
```

## License

MIT
