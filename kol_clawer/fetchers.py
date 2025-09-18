# -*- coding: utf-8 -*-
# fetchers.py
# 说明：统一封装三大平台的抓取逻辑。
# 优先使用 YouTube 官方API（如果提供了 API Key），否则回退到 yt-dlp。
# Instagram/TikTok：用 yt-dlp 直接解析公开页面。

import re
import requests
from yt_dlp import YoutubeDL

YOUTUBE_VIDEO_ID_RE = re.compile(
    r"(?:v=|/videos/|embed/|youtu\.be/|/shorts/)([A-Za-z0-9_-]{6,})"
)

def extract_youtube_id(url: str) -> str | None:
    """简易从 YouTube 链接里抽取 videoId（适配常见几种URL）"""
    m = YOUTUBE_VIDEO_ID_RE.search(url)
    return m.group(1) if m else None

def fetch_by_ytdlp(url: str) -> dict:
    """
    使用 yt-dlp 抓取公开页面的元数据与统计字段。
    返回规范化字典：{views, likes, comments}
    """
    # quiet=True 避免输出日志；nocheckcertificate让某些环境更宽松
    ydl_opts = {
        "quiet": True,
        "nocheckcertificate": True,
        "skip_download": True,
        "noplaylist": True,
        # 只要元数据
        "simulate": True,
        "forcejson": True,
        "extract_flat": False,
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        # 不同站点字段名会略有差异，这里做兼容
        views = info.get("view_count") or info.get("views") or 0
        likes = info.get("like_count") or info.get("likes") or 0
        comments = info.get("comment_count") or info.get("comments") or 0
        # 兜底：yt-dlp 部分站点可能只返回字符串，需要转 int
        views = int(views or 0)
        likes = int(likes or 0)
        comments = int(comments or 0)
        return {"views": views, "likes": likes, "comments": comments}

def fetch_youtube_with_api(url: str, api_key: str) -> dict:
    """
    使用 YouTube Data API v3 拉取统计数据（更合规更稳定）。
    前提：提供 api_key 且链接能提取出 videoId。
    """
    vid = extract_youtube_id(url)
    if not vid:
        # 提取不到 id 则回退到 ytdlp 再试
        return fetch_by_ytdlp(url)

    endpoint = "https://www.googleapis.com/youtube/v3/videos"
    params = {"part": "statistics", "id": vid, "key": api_key}
    r = requests.get(endpoint, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    items = data.get("items", [])
    if not items:
        # API 找不到，回退 ytdlp
        return fetch_by_ytdlp(url)
    stats = items[0]["statistics"]
    views = int(stats.get("viewCount", 0))
    likes = int(stats.get("likeCount", 0)) if "likeCount" in stats else 0
    comments = int(stats.get("commentCount", 0)) if "commentCount" in stats else 0
    return {"views": views, "likes": likes, "comments": comments}

def fetch_metrics(platform: str, url: str, youtube_api_key: str | None = None) -> dict:
    """
    统一入口：根据平台分发。
    - YouTube：若提供了 API Key，优先走官方API；否则用 yt-dlp。
    - Instagram/TikTok：用 yt-dlp。
    返回：{"views": int, "likes": int, "comments": int}
    """
    p = (platform or "").strip().lower()
    if p == "youtube":
        if youtube_api_key:
            try:
                return fetch_youtube_with_api(url, youtube_api_key)
            except Exception:
                # 失败则回退到 ytdlp
                pass
        return fetch_by_ytdlp(url)

    elif p in ("instagram", "tiktok"):
        return fetch_by_ytdlp(url)

    else:
        # 未知平台，尝试直接用 ytdlp
        return fetch_by_ytdlp(url)
