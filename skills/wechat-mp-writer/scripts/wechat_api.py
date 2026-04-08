#!/usr/bin/env python3
"""
微信公众平台 API 工具脚本
支持：token管理、素材上传、草稿管理、预览、发布

使用前请确保设置环境变量：
  WECHAT_APP_ID — 公众号 AppID
  WECHAT_APP_SECRET — 公众号 AppSecret

或在项目根目录创建 .env 文件。
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

# ---------------------------------------------------------------------------
# 配置与常量
# ---------------------------------------------------------------------------

API_BASE = "https://api.weixin.qq.com"
TOKEN_CACHE_FILE = Path(__file__).parent / ".token_cache.json"

# 尝试从 .env 文件加载环境变量
def _load_dotenv():
    """从项目中查找 .env 文件并加载环境变量（不覆盖已有变量）"""
    for search_dir in [Path.cwd(), Path(__file__).parent.parent, Path.home()]:
        env_file = search_dir / ".env"
        if env_file.exists():
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        key, value = key.strip(), value.strip().strip("'\"")
                        if key and key not in os.environ:
                            os.environ[key] = value
            return
_load_dotenv()


def _get_credentials():
    app_id = os.environ.get("WECHAT_APP_ID", "")
    app_secret = os.environ.get("WECHAT_APP_SECRET", "")
    if not app_id or not app_secret:
        print("错误：未设置 WECHAT_APP_ID 或 WECHAT_APP_SECRET 环境变量", file=sys.stderr)
        print("请参考 SKILL.md 中的 API 配置引导完成设置", file=sys.stderr)
        sys.exit(1)
    return app_id, app_secret


# ---------------------------------------------------------------------------
# HTTP 辅助
# ---------------------------------------------------------------------------

def _api_get(path, params=None):
    url = f"{API_BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _api_post_json(path, params=None, body=None):
    url = f"{API_BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _api_post_multipart(path, params, filepath, form_fields=None):
    """上传文件（multipart/form-data）"""
    url = f"{API_BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    boundary = "----WechatMPWriterBoundary"
    body_parts = []

    # 额外表单字段
    if form_fields:
        for key, value in form_fields.items():
            body_parts.append(f"--{boundary}\r\n".encode())
            body_parts.append(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
            body_parts.append(f"{value}\r\n".encode())

    # 文件字段
    filename = os.path.basename(filepath)
    body_parts.append(f"--{boundary}\r\n".encode())
    body_parts.append(
        f'Content-Disposition: form-data; name="media"; filename="{filename}"\r\n'.encode()
    )
    body_parts.append(b"Content-Type: application/octet-stream\r\n\r\n")
    with open(filepath, "rb") as f:
        body_parts.append(f.read())
    body_parts.append(b"\r\n")
    body_parts.append(f"--{boundary}--\r\n".encode())

    body = b"".join(body_parts)
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


# ---------------------------------------------------------------------------
# Token 管理（带缓存 + 自动刷新）
# ---------------------------------------------------------------------------

def _get_cached_token():
    if TOKEN_CACHE_FILE.exists():
        with open(TOKEN_CACHE_FILE) as f:
            cache = json.load(f)
        if cache.get("expires_at", 0) > time.time() + 60:
            return cache["access_token"]
    return None


def _save_token(token, expires_in):
    cache = {
        "access_token": token,
        "expires_at": time.time() + expires_in,
        "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(TOKEN_CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def get_access_token(force_refresh=False):
    if not force_refresh:
        cached = _get_cached_token()
        if cached:
            return cached

    app_id, app_secret = _get_credentials()
    result = _api_get("/cgi-bin/token", {
        "grant_type": "client_credential",
        "appid": app_id,
        "secret": app_secret,
    })

    if "access_token" not in result:
        print(f"获取 access_token 失败：{result}", file=sys.stderr)
        sys.exit(1)

    _save_token(result["access_token"], result.get("expires_in", 7200))
    return result["access_token"]


def _call_with_retry(func, max_retries=2):
    """带 token 自动刷新的重试包装器"""
    for attempt in range(max_retries + 1):
        result = func()
        errcode = result.get("errcode", 0)
        if errcode == 0:
            return result
        if errcode in (40001, 42001) and attempt < max_retries:
            print(f"Token 过期（errcode={errcode}），正在刷新...", file=sys.stderr)
            get_access_token(force_refresh=True)
            continue
        # 非 token 错误或重试耗尽
        _handle_error(result)
        return result
    return result


def _handle_error(result):
    errcode = result.get("errcode", 0)
    errmsg = result.get("errmsg", "unknown")
    suggestions = {
        40001: "检查 AppSecret 是否正确",
        40002: "检查请求参数格式",
        40013: "检查 AppID 是否正确",
        41001: "缺少 access_token 参数",
        42001: "access_token 已过期，请重新获取",
        45009: "API 调用频率超限，请稍后再试（每日限5000次）",
        45028: "素材数量超过限制",
        48001: "该 API 接口未授权，请检查公众号权限",
    }
    suggestion = suggestions.get(errcode, "请参考微信官方文档排查")
    print(f"\n错误码：{errcode}", file=sys.stderr)
    print(f"错误信息：{errmsg}", file=sys.stderr)
    print(f"建议操作：{suggestion}", file=sys.stderr)


# ---------------------------------------------------------------------------
# 功能命令
# ---------------------------------------------------------------------------

def cmd_check(args):
    """检查 API 凭据是否可用"""
    token = get_access_token(force_refresh=True)
    print(f"✓ access_token 获取成功")
    print(f"  Token: {token[:16]}...")
    print(f"  缓存文件: {TOKEN_CACHE_FILE}")


def cmd_upload_image(args):
    """上传正文内图片（返回微信域名URL）"""
    token = get_access_token()

    def do_upload():
        return _api_post_multipart(
            "/cgi-bin/media/uploadimg",
            {"access_token": token},
            args.file_path,
        )

    result = _call_with_retry(lambda: _api_post_multipart(
        "/cgi-bin/media/uploadimg",
        {"access_token": get_access_token()},
        args.file_path,
    ))

    if "url" in result:
        print(f"✓ 图片上传成功")
        print(f"  URL: {result['url']}")
        print(json.dumps({"url": result["url"]}))
    else:
        print("✗ 图片上传失败", file=sys.stderr)


def cmd_upload_material(args):
    """上传永久素材（封面图等，返回media_id）"""
    result = _call_with_retry(lambda: _api_post_multipart(
        "/cgi-bin/material/add_material",
        {"access_token": get_access_token(), "type": args.type},
        args.file_path,
    ))

    if "media_id" in result:
        print(f"✓ 素材上传成功")
        print(f"  media_id: {result['media_id']}")
        if "url" in result:
            print(f"  URL: {result['url']}")
        print(json.dumps({"media_id": result["media_id"], "url": result.get("url", "")}))
    else:
        print("✗ 素材上传失败", file=sys.stderr)


def cmd_add_draft(args):
    """添加草稿"""
    article = {
        "title": args.title,
        "content": args.content,
        "digest": args.digest or "",
        "thumb_media_id": args.thumb_media_id,
        "author": args.author or "",
        "need_open_comment": args.need_open_comment,
        "only_fans_can_comment": args.only_fans_can_comment,
    }
    # 如果 content 是文件路径，读取文件
    if os.path.isfile(args.content):
        with open(args.content, "r", encoding="utf-8") as f:
            article["content"] = f.read()

    body = {"articles": [article]}

    result = _call_with_retry(lambda: _api_post_json(
        "/cgi-bin/draft/add",
        {"access_token": get_access_token()},
        body,
    ))

    if "media_id" in result:
        print(f"✓ 草稿添加成功")
        print(f"  media_id: {result['media_id']}")
        print(json.dumps({"media_id": result["media_id"]}))
    else:
        print("✗ 草稿添加失败", file=sys.stderr)


def cmd_preview(args):
    """预览文章（发送到指定微信号）"""
    body = {"media_id": args.media_id}
    if args.towxname:
        body["towxname"] = args.towxname
    elif args.touser:
        body["touser"] = args.touser
    else:
        # 尝试从环境变量获取
        preview_user = os.environ.get("WECHAT_PREVIEW_USER", "")
        if preview_user:
            if len(preview_user) > 20:
                body["touser"] = preview_user  # openid 通常较长
            else:
                body["towxname"] = preview_user
        else:
            print("错误：请指定 --towxname 或 --touser，或设置 WECHAT_PREVIEW_USER 环境变量", file=sys.stderr)
            sys.exit(1)

    body["msgtype"] = "mpnews"
    body["mpnews"] = {"media_id": args.media_id}

    result = _call_with_retry(lambda: _api_post_json(
        "/cgi-bin/message/mass/preview",
        {"access_token": get_access_token()},
        body,
    ))

    if result.get("errcode", 0) == 0:
        print(f"✓ 预览发送成功")
        print(f"  msg_id: {result.get('msg_id', 'N/A')}")
    else:
        print("✗ 预览发送失败", file=sys.stderr)


def cmd_publish(args):
    """正式发布"""
    result = _call_with_retry(lambda: _api_post_json(
        "/cgi-bin/freepublish/submit",
        {"access_token": get_access_token()},
        {"media_id": args.media_id},
    ))

    if "publish_id" in result:
        print(f"✓ 发布提交成功")
        print(f"  publish_id: {result['publish_id']}")
        print(json.dumps({"publish_id": result["publish_id"]}))
    else:
        print("✗ 发布提交失败", file=sys.stderr)


def cmd_publish_status(args):
    """查询发布状态"""
    result = _call_with_retry(lambda: _api_post_json(
        "/cgi-bin/freepublish/get",
        {"access_token": get_access_token()},
        {"publish_id": args.publish_id},
    ))

    if "publish_status" in result:
        status_map = {0: "发布成功", 1: "发布中", 2: "原文已删除", 3: "发布失败"}
        status = result["publish_status"]
        print(f"发布状态：{status_map.get(status, f'未知({status})')}")
        if status == 0 and "article_detail" in result:
            for item in result["article_detail"].get("item", []):
                article_url = item.get("article_url", "")
                if article_url:
                    print(f"  文章链接：{article_url}")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("✗ 查询失败", file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="微信公众平台 API 工具")
    sub = parser.add_subparsers(dest="command", help="可用命令")

    # check
    sub.add_parser("check", help="检查 API 凭据")

    # upload_image
    p = sub.add_parser("upload_image", help="上传正文内图片")
    p.add_argument("file_path", help="图片文件路径")

    # upload_material
    p = sub.add_parser("upload_material", help="上传永久素材")
    p.add_argument("file_path", help="文件路径")
    p.add_argument("--type", default="image", choices=["image", "voice", "video", "thumb"],
                   help="素材类型（默认 image）")

    # add_draft
    p = sub.add_parser("add_draft", help="添加草稿")
    p.add_argument("--title", required=True, help="文章标题")
    p.add_argument("--content", required=True, help="HTML内容或文件路径")
    p.add_argument("--digest", default="", help="文章摘要")
    p.add_argument("--thumb_media_id", required=True, help="封面图 media_id")
    p.add_argument("--author", default="", help="作者名")
    p.add_argument("--need_open_comment", type=int, default=1, help="是否开启评论")
    p.add_argument("--only_fans_can_comment", type=int, default=0, help="是否仅粉丝可评论")

    # preview
    p = sub.add_parser("preview", help="发送预览")
    p.add_argument("--media_id", required=True, help="草稿 media_id")
    p.add_argument("--towxname", default="", help="接收预览的微信号")
    p.add_argument("--touser", default="", help="接收预览的 openid")

    # publish
    p = sub.add_parser("publish", help="正式发布")
    p.add_argument("--media_id", required=True, help="草稿 media_id")

    # publish_status
    p = sub.add_parser("publish_status", help="查询发布状态")
    p.add_argument("--publish_id", required=True, help="发布 ID")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "check": cmd_check,
        "upload_image": cmd_upload_image,
        "upload_material": cmd_upload_material,
        "add_draft": cmd_add_draft,
        "preview": cmd_preview,
        "publish": cmd_publish,
        "publish_status": cmd_publish_status,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
