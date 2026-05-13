#!/usr/bin/env python3
"""
图片搜索与多源抓取脚本（v2 image pipeline 第 1-3 步）

功能：
  - 实体级搜词生成（从段落 facts_cited / 标题抽实体）
  - 多源抓取（Wikimedia Commons / Unsplash / 官方源 / 本地素材库 / Web）
  - URL 去重 + 感知哈希去重（仅当 imagehash 可用）

使用：
  python image_search.py search --keywords "Sam Altman 2024" --source wikimedia --limit 5
  python image_search.py search --keywords "OpenAI logo" --source official --url https://openai.com/favicon.ico
  python image_search.py dedupe --dir ./articles/deepseek-r1/images/

环境变量：
  UNSPLASH_ACCESS_KEY — Unsplash API access key（仅 source=unsplash 时需要）
  ANTHROPIC_API_KEY — 后续 image_vision_review.py 用，不在本脚本

输出：JSON 列表写到 stdout 或指定文件，每条含 url / local_path / source / license。

设计原则：纯 stdlib，第三方依赖（PIL / imagehash）按需 import 不强制。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# 全局配置
# ---------------------------------------------------------------------------

USER_AGENT = "wechat-mp-writer/2.0 (https://github.com/daizhouchen/wechat-mp-writer)"

# 严禁来源黑名单（域名包含即拒绝）
FORBIDDEN_DOMAINS = [
    "pinterest.com",
    "pinimg.com",
    "google.com/imgres",   # Google 图片预览 URL
    "weibo.com",           # 微博图片版权不明
    "zhihu.com",           # 知乎图片版权不明
    "163.com",             # 网易门户缩略图
    "sina.com.cn",         # 新浪门户缩略图
    "sohu.com",            # 搜狐门户缩略图
]

# 默认 license（按 source 推断）
LICENSE_BY_SOURCE = {
    "wikimedia_commons": "cc_by_sa_4",  # 大多数为 CC-BY-SA 4.0
    "unsplash": "unsplash_license",      # 类 CC0 但带 Unsplash 限制
    "official": "fair_use_editorial",
    "local": "user_owned",
    "web": "needs_manual_review",
}


# ---------------------------------------------------------------------------
# 实体抽取（简单规则版，复杂场景由调用方在外部抽好）
# ---------------------------------------------------------------------------

def extract_entities_from_text(text: str) -> list[str]:
    """
    从文本里抽出可能的实体。
    极简规则版：
      - 英文大写词组（OpenAI / DeepSeek / Sam Altman）
      - 模型/产品名（带数字或斜杠的：R1, GPT-4, H100, o1-mini）
      - 中文里夹带的英文 token
    """
    entities = set()

    # 英文 PascalCase / CamelCase / 大写词组（含连字符）
    for m in re.finditer(r"\b([A-Z][a-zA-Z]+(?:[\s\-][A-Z][a-zA-Z]+)*)\b", text):
        entities.add(m.group(1))

    # 模型/产品代号（字母数字混合，至少含一个数字）
    for m in re.finditer(r"\b([A-Za-z]+\-?\d+[A-Za-z0-9\-]*)\b", text):
        entities.add(m.group(1))

    # 过滤短词（≤2 字符）和纯数字
    return [e for e in entities if len(e) > 2 and not e.isdigit()]


def generate_search_queries(image_intent: str, facts: list[str] | None = None) -> list[str]:
    """
    给定 image_intent 和段落 facts，生成 2-5 个搜索词候选。

    候选层级：
      1. 实体级（最准）：实体 + 修饰（"Sam Altman portrait 2024"）
      2. 场景级：事件名 + 时间（"OpenAI Dev Day 2024"）
      3. 概念级（兜底）：领域 + 视觉概念（"reasoning model diagram"）
    """
    queries: list[str] = []
    seen: set[str] = set()

    def add(q: str):
        q = q.strip()
        if q and q not in seen:
            queries.append(q)
            seen.add(q)

    # Level 1: 实体级
    src_text = " ".join((facts or []) + [image_intent])
    entities = extract_entities_from_text(src_text)
    for ent in entities[:3]:
        add(f"{ent} portrait")
        add(f"{ent} logo")
        add(f"{ent}")

    # Level 2: 场景级（用 image_intent 关键词）
    intent_clean = re.sub(r"[，。、；：（）]", " ", image_intent)
    add(intent_clean.strip())

    # Level 3: 概念级（兜底）
    if not entities:
        add(image_intent + " diagram")
        add(image_intent + " illustration")

    return queries[:5]


# ---------------------------------------------------------------------------
# 来源抓取
# ---------------------------------------------------------------------------

def _http_get(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _is_forbidden(url: str) -> bool:
    return any(dom in url.lower() for dom in FORBIDDEN_DOMAINS)


def search_wikimedia(query: str, limit: int = 5) -> list[dict]:
    """通过 Wikimedia Commons API 搜图。"""
    api = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": f"filetype:bitmap {query}",
        "gsrnamespace": "6",
        "gsrlimit": str(limit),
        "prop": "imageinfo",
        "iiprop": "url|size|extmetadata",
        "iiurlwidth": "1200",
    }
    url = f"{api}?{urllib.parse.urlencode(params)}"
    try:
        raw = _http_get(url)
        data = json.loads(raw.decode("utf-8"))
    except Exception as e:
        sys.stderr.write(f"[wikimedia] query failed: {e}\n")
        return []

    pages = (data.get("query") or {}).get("pages") or {}
    results: list[dict] = []
    for _pid, page in pages.items():
        infos = page.get("imageinfo") or []
        if not infos:
            continue
        info = infos[0]
        thumb_url = info.get("thumburl") or info.get("url")
        if not thumb_url:
            continue
        meta = info.get("extmetadata") or {}
        license_short = (meta.get("LicenseShortName") or {}).get("value", "")
        results.append({
            "url": thumb_url,
            "source": "wikimedia_commons",
            "license": _normalize_wm_license(license_short),
            "title": page.get("title", ""),
            "width": info.get("width", 0),
            "height": info.get("height", 0),
        })
    return results


def _normalize_wm_license(short: str) -> str:
    s = (short or "").lower()
    if "cc0" in s or "public domain" in s or "pd-" in s:
        return "public_domain"
    if "cc by-sa" in s or "cc-by-sa" in s:
        return "cc_by_sa_4"
    if "cc by" in s or "cc-by" in s:
        return "cc_by_4"
    return "wikimedia_other"


def search_unsplash(query: str, limit: int = 5) -> list[dict]:
    """通过 Unsplash API 搜图（需 UNSPLASH_ACCESS_KEY）。"""
    key = os.environ.get("UNSPLASH_ACCESS_KEY")
    if not key:
        sys.stderr.write("[unsplash] UNSPLASH_ACCESS_KEY 未设置，跳过\n")
        return []

    url = f"https://api.unsplash.com/search/photos?query={urllib.parse.quote(query)}&per_page={limit}"
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Authorization": f"Client-ID {key}",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        sys.stderr.write(f"[unsplash] query failed: {e}\n")
        return []

    results = []
    for item in data.get("results", []):
        results.append({
            "url": item["urls"].get("regular") or item["urls"].get("full"),
            "source": "unsplash",
            "license": "unsplash_license",
            "title": item.get("description") or item.get("alt_description") or "",
            "width": item.get("width", 0),
            "height": item.get("height", 0),
        })
    return results


def search_official(urls: list[str]) -> list[dict]:
    """对官方/手动指定的 URL 列表做基础校验。"""
    results = []
    for url in urls:
        if _is_forbidden(url):
            sys.stderr.write(f"[official] 拒绝禁用源: {url}\n")
            continue
        results.append({
            "url": url,
            "source": "official",
            "license": "fair_use_editorial",
            "title": "",
            "width": 0,
            "height": 0,
        })
    return results


def search_local(dirpath: str, query: str) -> list[dict]:
    """在本地素材库（用户配置的目录）按文件名匹配 query。"""
    d = Path(dirpath).expanduser()
    if not d.exists():
        return []
    q_lower = query.lower()
    results = []
    for p in d.glob("**/*"):
        if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
            if q_lower in p.stem.lower():
                results.append({
                    "url": p.as_uri(),
                    "local_path": str(p),
                    "source": "local",
                    "license": "user_owned",
                    "title": p.stem,
                    "width": 0,
                    "height": 0,
                })
    return results


# ---------------------------------------------------------------------------
# 下载 + 去重
# ---------------------------------------------------------------------------

def download_image(url: str, out_dir: Path) -> Path | None:
    """下载到 out_dir，文件名 = url hash + 后缀。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    name = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    ext = Path(urllib.parse.urlparse(url).path).suffix.lower() or ".jpg"
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        ext = ".jpg"
    out_path = out_dir / f"{name}{ext}"
    if out_path.exists():
        return out_path
    try:
        data = _http_get(url)
        out_path.write_bytes(data)
        return out_path
    except Exception as e:
        sys.stderr.write(f"[download] failed {url}: {e}\n")
        return None


def perceptual_hash(path: Path) -> str | None:
    """计算图片感知哈希。如 imagehash 不可用，回退到字节 md5（弱去重）。"""
    try:
        from PIL import Image  # type: ignore
        import imagehash  # type: ignore
        return str(imagehash.phash(Image.open(path)))
    except ImportError:
        return hashlib.md5(path.read_bytes()).hexdigest()
    except Exception:
        return None


def dedupe(image_records: list[dict], image_dir: Path | None = None) -> list[dict]:
    """
    image_records: 每条至少有 url, 可能有 local_path
    返回去重后的列表（保留首次出现）。
    URL 完全相同 → 视为重复
    若提供 local_path 且 imagehash 可用 → pHash 相似（汉明距离 ≤ 6）视为重复
    """
    seen_urls: set[str] = set()
    seen_hashes: set[str] = set()
    out: list[dict] = []
    for rec in image_records:
        if rec.get("url") in seen_urls:
            continue
        seen_urls.add(rec["url"])
        p = rec.get("local_path")
        if p and Path(p).exists():
            h = perceptual_hash(Path(p))
            if h and h in seen_hashes:
                continue
            if h:
                seen_hashes.add(h)
        out.append(rec)
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_search(args):
    queries: list[str] = []
    if args.keywords:
        queries = [args.keywords]
    elif args.intent:
        queries = generate_search_queries(args.intent, args.facts or [])

    results: list[dict] = []
    for q in queries:
        if args.source == "wikimedia":
            results.extend(search_wikimedia(q, limit=args.limit))
        elif args.source == "unsplash":
            results.extend(search_unsplash(q, limit=args.limit))
        elif args.source == "official":
            results.extend(search_official(args.url or []))
        elif args.source == "local":
            results.extend(search_local(args.local_dir or "~/.wechat-assets", q))
        else:
            sys.stderr.write(f"未知 source: {args.source}\n")
            sys.exit(2)
        time.sleep(1)  # 速率友好

    # 下载（可选）
    if args.download:
        out_dir = Path(args.download).expanduser()
        for r in results:
            if r.get("source") == "local":
                continue
            local = download_image(r["url"], out_dir)
            if local:
                r["local_path"] = str(local)

    # 去重
    results = dedupe(results)

    output = json.dumps(results, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output)


def cmd_dedupe(args):
    d = Path(args.dir).expanduser()
    if not d.exists():
        sys.stderr.write(f"目录不存在: {d}\n")
        sys.exit(2)
    records = []
    for p in d.glob("*"):
        if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
            records.append({"url": p.as_uri(), "local_path": str(p)})
    deduped = dedupe(records)
    removed = [r for r in records if r not in deduped]
    print(json.dumps({
        "kept": len(deduped),
        "removed": len(removed),
        "removed_files": [r["local_path"] for r in removed],
    }, ensure_ascii=False, indent=2))


def cmd_query_gen(args):
    qs = generate_search_queries(args.intent, args.facts or [])
    print(json.dumps(qs, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="v2 image search / fetch / dedupe")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_search = sub.add_parser("search", help="搜索图片")
    p_search.add_argument("--keywords", help="直接给关键词（跳过实体抽取）")
    p_search.add_argument("--intent", help="image_intent，自动生成搜词")
    p_search.add_argument("--facts", nargs="*", help="facts_cited 文本，辅助搜词生成")
    p_search.add_argument("--source", required=True,
                          choices=["wikimedia", "unsplash", "official", "local", "web"])
    p_search.add_argument("--url", nargs="*", help="source=official 时指定 URL 列表")
    p_search.add_argument("--local-dir", help="source=local 时本地素材库目录")
    p_search.add_argument("--limit", type=int, default=5)
    p_search.add_argument("--download", help="下载到该目录")
    p_search.add_argument("--output", help="结果写入文件（默认 stdout）")
    p_search.set_defaults(func=cmd_search)

    p_dedupe = sub.add_parser("dedupe", help="对目录里的图去重")
    p_dedupe.add_argument("--dir", required=True)
    p_dedupe.set_defaults(func=cmd_dedupe)

    p_q = sub.add_parser("query-gen", help="只生成搜词，不抓图")
    p_q.add_argument("--intent", required=True)
    p_q.add_argument("--facts", nargs="*")
    p_q.set_defaults(func=cmd_query_gen)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
