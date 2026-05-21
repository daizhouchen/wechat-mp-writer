#!/usr/bin/env bash
# wechat-mp-writer v2.1 通用一键发布脚本
#
# 跟随每篇文章拷贝到 ./articles/<slug>/publish.sh，无需修改即可用。
#
# 用法：
#   ./publish.sh                — 走完整流程到草稿（最稳）
#   ./publish.sh --preview      — 草稿 + 发预览（需账号有 preview 权限）
#   ./publish.sh --auto         — 草稿 + 预览 + 直接发布（需 freepublish 权限）
#   ./publish.sh --update <id>  — 覆盖更新已有草稿（避免堆积）
#
# 内置：跨目录 .env 查找 / JSON 容错 / 48001 自动降级 / digest 自动截断
#
# 配置：在 article 目录下放 article.meta（key=value 形式，可选；缺失则用脚本顶部默认）
#   TITLE=...
#   DIGEST=...
#   AUTHOR=...
#   THUMB=images/cover.png
#   ARTICLE_HTML=article.html        # 可选：默认 article.html
#   IMAGES="images/a.png images/b.png images/c.png"   # 内文图按出现顺序

set -e

ARTICLE_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="${WECHAT_SKILL_DIR:-$HOME/.claude/skills/wechat-mp-writer/scripts}"
cd "$ARTICLE_DIR"

# ----------------------------------------------------------------------------
# 加载 .env（向上 5 层 + $HOME）
# ----------------------------------------------------------------------------
for d in . .. ../.. ../../.. ../../../.. "$HOME"; do
  if [ -f "$d/.env" ]; then
    [ -t 1 ] && echo "  using env: $(cd "$d" && pwd)/.env" >&2
    set -a; source "$d/.env"; set +a
    break
  fi
done

# ----------------------------------------------------------------------------
# 加载 article.meta（如有），否则从默认推断
# ----------------------------------------------------------------------------
TITLE=""
DIGEST=""
AUTHOR=""
THUMB="images/cover.png"
ARTICLE_HTML="article.html"
IMAGES=""

if [ -f article.meta ]; then
  set -a; source article.meta; set +a
fi

# 兜底：从 article.json 读
if [ -z "$TITLE" ] && [ -f article.json ]; then
  TITLE=$(python3 -c "import json; m=json.load(open('article.json'))['meta']; print(m.get('title',''))")
  DIGEST=$(python3 -c "import json; m=json.load(open('article.json'))['meta']; print(m.get('digest',''))")
  AUTHOR=$(python3 -c "import json; m=json.load(open('article.json'))['meta'].get('profile_snapshot',{}); print(m.get('author','')) ")
fi

if [ -z "$TITLE" ]; then
  echo "✗ 缺 TITLE，请创建 article.meta 或填 article.json.meta.title" >&2
  exit 1
fi

# digest 自动截断到 120 字节
if [ -n "$DIGEST" ]; then
  TRIMMED=$(python3 -c "
import sys
d = sys.argv[1]
b = d.encode('utf-8')
if len(b) <= 120:
    print(d, end='')
else:
    s = d
    while len(s.encode('utf-8')) > 120:
        s = s[:-1]
    print(s, end='')
" "$DIGEST")
  DIGEST="$TRIMMED"
fi

# title 64 字节硬限制（微信 add_draft 限制；errcode 45003）
# 中文 3 字节、英文/数字/标点 1 字节；超限直接拒绝避免 API 浪费
if [ -n "$TITLE" ]; then
  TITLE_BYTES=$(python3 -c "import sys; print(len(sys.argv[1].encode('utf-8')))" "$TITLE")
  if [ "$TITLE_BYTES" -gt 64 ]; then
    echo "" >&2
    echo "✗ TITLE 超 64 字节限制（实际 $TITLE_BYTES 字节）" >&2
    echo "  当前: $TITLE" >&2
    echo "  提示: 中文 3 字节/字、英文+标点 1 字节/字 · 微信 add_draft 硬约束" >&2
    echo "  改 article.meta 里的 TITLE=\"...\" 后重跑" >&2
    exit 2
  fi
fi

# ----------------------------------------------------------------------------
# Step 1: 凭据 + 接口权限预检
# ----------------------------------------------------------------------------
echo "[1/6] 检查 API 凭据 + 接口权限..." >&2
PERM_JSON=$(python3 "$SKILL_DIR/wechat_api.py" check 2>/dev/null) || {
  echo "✗ API 凭据失败。请在项目根 .env 写：" >&2
  echo "  WECHAT_APP_ID=wx你的id" >&2
  echo "  WECHAT_APP_SECRET=你的secret" >&2
  echo "  WECHAT_PREVIEW_USER=你的微信号  # 选填" >&2
  exit 1
}
CAN_PREVIEW=$(echo "$PERM_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin)['permissions']['preview'])")
CAN_PUBLISH=$(echo "$PERM_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin)['permissions']['publish'])")

# ----------------------------------------------------------------------------
# Step 2: 上传封面
# ----------------------------------------------------------------------------
echo "[2/6] 上传封面 ($THUMB)..." >&2
THUMB_MEDIA_ID=$(python3 "$SKILL_DIR/wechat_api.py" upload_material "$THUMB" --type image \
                 | python3 -c "import json,sys; print(json.load(sys.stdin)['media_id'])")
echo "  thumb_media_id = ${THUMB_MEDIA_ID:0:20}..." >&2

# ----------------------------------------------------------------------------
# Step 3: 上传正文图（含封面也作为正文图首张）
# ----------------------------------------------------------------------------
echo "[3/6] 上传正文配图..." >&2
COVER_INLINE_URL=$(python3 "$SKILL_DIR/wechat_api.py" upload_image "$THUMB" \
                   | python3 -c "import json,sys; print(json.load(sys.stdin)['url'])")

declare -a INLINE_URLS
INLINE_URLS+=("$COVER_INLINE_URL")
for img in $IMAGES; do
  url=$(python3 "$SKILL_DIR/wechat_api.py" upload_image "$img" \
        | python3 -c "import json,sys; print(json.load(sys.stdin)['url'])")
  INLINE_URLS+=("$url")
done
echo "  ${#INLINE_URLS[@]} 张图已上传" >&2

# ----------------------------------------------------------------------------
# Step 4: 替换本地图 src → mmbiz URL，写 article-wechat.html
# 支持 base64 / 相对路径 (./images/...) / 绝对路径，按 img 出现顺序消费 INLINE_URLS
# ----------------------------------------------------------------------------
echo "[4/6] 渲染 wechat 版 HTML..." >&2
URLS_JSON=$(printf '%s\n' "${INLINE_URLS[@]}" | python3 -c "import json,sys; print(json.dumps([l.strip() for l in sys.stdin.read().splitlines() if l.strip()]))")

python3 - "$ARTICLE_HTML" "$URLS_JSON" << 'PYEOF'
import sys, re, json
from pathlib import Path
src_path, urls_json = sys.argv[1], sys.argv[2]
urls = json.loads(urls_json)
t = Path(src_path).read_text(encoding="utf-8")
# 按顺序替换所有本地 img src（base64 / 相对路径 / 绝对路径），跳过已有 http/mmbiz URL
inline_idx = [0]
def rep(m):
    src = m.group(1)
    if src.startswith('http') or 'mmbiz' in src:
        return m.group(0)
    if inline_idx[0] < len(urls):
        u = urls[inline_idx[0]]; inline_idx[0] += 1
        return m.group(0).replace(src, u)
    return m.group(0)
t = re.sub(r'<img[^>]+?src="([^"]+)"', rep, t)
out = Path(src_path).with_name("article-wechat.html")
out.write_text(t, encoding="utf-8")
print(f"  写入 {out} ({len(t)} chars · 替换 {inline_idx[0]} 张图)", file=sys.stderr)
PYEOF

# ----------------------------------------------------------------------------
# Step 5: 创建/更新草稿
# ----------------------------------------------------------------------------
if [ "$1" = "--update" ] && [ -n "$2" ]; then
  echo "[5/6] 更新已有草稿 $2..." >&2
  DRAFT_RESP=$(python3 "$SKILL_DIR/wechat_api.py" update_draft \
    --media_id "$2" --index 0 \
    --title "$TITLE" \
    --content article-wechat.html \
    --digest "$DIGEST" \
    --thumb_media_id "$THUMB_MEDIA_ID" \
    --author "$AUTHOR")
  DRAFT_MEDIA_ID="$2"
  echo "  草稿已更新：${DRAFT_MEDIA_ID:0:20}..." >&2
else
  echo "[5/6] 创建新草稿..." >&2
  DRAFT_MEDIA_ID=$(python3 "$SKILL_DIR/wechat_api.py" add_draft \
    --title "$TITLE" \
    --content article-wechat.html \
    --digest "$DIGEST" \
    --thumb_media_id "$THUMB_MEDIA_ID" \
    --author "$AUTHOR" \
    --need_open_comment 1 \
    --only_fans_can_comment 0 \
    | python3 -c "import json,sys; print(json.load(sys.stdin)['media_id'])")
  echo "  草稿已创建：${DRAFT_MEDIA_ID:0:20}..." >&2
fi

# ----------------------------------------------------------------------------
# Step 6: 预览（仅当账号有权限）
# ----------------------------------------------------------------------------
if [ "$1" = "--preview" ] || [ "$1" = "--auto" ]; then
  if [ "$CAN_PREVIEW" = "True" ] && [ -n "$WECHAT_PREVIEW_USER" ]; then
    echo "[6/6] 发送预览..." >&2
    python3 "$SKILL_DIR/wechat_api.py" preview --media_id "$DRAFT_MEDIA_ID" --towxname "$WECHAT_PREVIEW_USER"
    if [ "$1" = "--auto" ]; then
      read -p "预览已发到你微信，确认发布？输入 yes 继续: " CONF
      [ "$CONF" != "yes" ] && { echo "已取消，草稿仍在后台" >&2; exit 0; }
    fi
  else
    echo "[6/6] ⚠ 跳过预览 — preview 接口未授权或 WECHAT_PREVIEW_USER 未设" >&2
  fi
fi

# ----------------------------------------------------------------------------
# Step 7: 发布
# ----------------------------------------------------------------------------
if [ "$1" = "--auto" ]; then
  if [ "$CAN_PUBLISH" = "True" ]; then
    echo "[正式发布]" >&2
    PUB_ID=$(python3 "$SKILL_DIR/wechat_api.py" publish --media_id "$DRAFT_MEDIA_ID" \
             | python3 -c "import json,sys; print(json.load(sys.stdin)['publish_id'])")
    echo "  publish_id = $PUB_ID" >&2
    sleep 3
    python3 "$SKILL_DIR/wechat_api.py" publish_status --publish_id "$PUB_ID" >&2
  else
    echo "⚠ freepublish 接口未授权（个人订阅号 / 未认证号常见）。草稿已就绪，登录后台手动发表。" >&2
  fi
fi

# ----------------------------------------------------------------------------
# 落幕
# ----------------------------------------------------------------------------
echo "" >&2
echo "===========================================" >&2
echo "完成 · draft_media_id = $DRAFT_MEDIA_ID" >&2
echo "  本地预览版（base64 自包含）: $ARTICLE_DIR/$ARTICLE_HTML" >&2
echo "  公众号版（mmbiz URL）:     $ARTICLE_DIR/article-wechat.html" >&2
echo "===========================================" >&2

# stdout 输出 JSON 便于上游脚本调用
echo "{\"draft_media_id\": \"$DRAFT_MEDIA_ID\", \"thumb_media_id\": \"$THUMB_MEDIA_ID\", \"can_preview\": $CAN_PREVIEW, \"can_publish\": $CAN_PUBLISH}"
