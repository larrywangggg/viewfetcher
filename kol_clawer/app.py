# -*- coding: utf-8 -*-
# app.py
# 运行： streamlit run app.py
# 功能：上传 .xlsx/.csv；填写可选的 YouTube API Key；点击“开始获取”批量抓取，计算互动率，存入SQLite；展示看板与导出CSV。

import streamlit as st
import pandas as pd
from io import StringIO
from fetchers import fetch_metrics
from db import init_db, save_result, Result, SessionLocal
from sqlalchemy import select
import math
from fetchers import fetch_metrics, extract_youtube_id, fetch_youtube_batch_stats
from datetime import datetime


st.set_page_config(page_title="KOL 数据抓取看板", layout="wide")

# 初始化数据库（若不存在则建表）
init_db()

st.title("KOL 跨平台数据抓取 & 看板（MVP）")

with st.expander("使用说明（点此展开）", expanded=False):
    st.markdown("""
**步骤：**
1. 将你每周的KOL链接表导出为 `.xlsx` 或 `.csv`，至少包含 `platform` 和 `url` 两列（平台值：`youtube` / `instagram` / `tiktok`）。
2. （可选）填写 YouTube API Key（更稳定合规，若不填也可用 `yt-dlp` 直接抓取）。
3. 上传文件后，点击 **“开始获取”** 按钮，即可抓取 Views/Likes/Comments 并计算互动率。
4. 结果自动入库（SQLite），下方看板可 **筛选/导出CSV**。
    """)

# 可选：YouTube API Key
youtube_api_key = st.text_input("YouTube API Key", type="password", help="不填也可以运行，默认使用 yt-dlp。")




uploaded = st.file_uploader("上传 KOL 链接表（.xlsx 或 .csv）", type=["xlsx", "csv"])

# 简单的输入模板下载
with st.popover("没有模板？点击获取CSV模板"):
    st.caption("最少只需要 platform, url 两列；其他列可按需添加。")
    example = pd.DataFrame({
        "platform": ["youtube", "instagram", "tiktok"],
        "url": [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://www.instagram.com/reel/xxxxxx/",
            "https://www.tiktok.com/@user/video/1234567890"
        ],
        "creator": ["Rick", "IG_CREATOR", "TT_CREATOR"],
        "campaign_id": ["W37-Launch", "W37-Launch", "W37-Launch"],
        "posted_at": ["2025-09-10", "2025-09-11", "2025-09-12"],
        "notes": ["示例", "示例", "示例"],
    })
    st.download_button("下载模板 CSV", data=example.to_csv(index=False), file_name="kol_template.csv", mime="text/csv")

# 解析上传文件为 DataFrame
def read_df(file) -> pd.DataFrame:
    if file is None:
        return pd.DataFrame()
    if file.name.endswith(".csv"):
        return pd.read_csv(file)
    elif file.name.endswith(".xlsx"):
        return pd.read_excel(file)
    else:
        return pd.DataFrame()

df = read_df(uploaded)

if not df.empty:
    st.subheader("上传预览")
    st.dataframe(df.head(20), use_container_width=True)
    st.info("确保至少包含 `platform` 与 `url` 列；可选列：creator, campaign_id, posted_at, notes。")

# 运行按钮
run = st.button("▶️ 开始获取", type="primary", disabled=df.empty)

if run and not df.empty:
    st.write("开始抓取中，请稍等……（每周一次，通常几分钟内完成）")
    progress = st.progress(0, text="准备中...")
    total = len(df)
    results = []

    # 遍历表格行，逐条抓取
    for idx, row in df.iterrows():
        platform = str(row.get("platform", "")).strip()
        url = str(row.get("url", "")).strip()

        if not platform or not url:
            # 必填校验
            continue
 

        try:
            metrics = fetch_metrics(platform, url, youtube_api_key if youtube_api_key else None)
            views = int(metrics.get("views", 0))
            likes = int(metrics.get("likes", 0))
            comments = int(metrics.get("comments", 0))

            # 额外取出 creator 和 posted_at
            creator = metrics.get("creator", "")              # fetch_youtube_batch_stats 里返回的 channelTitle
            published = metrics.get("posted_at", "")          # fetch_youtube_batch_stats 里返回的 publishedAt
            posted_dt = None
            if published:
                try:
                    posted_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                except Exception:
                    posted_dt = None

            engagement_rate = round(((likes + comments) / views * 100.0), 2) if views > 0 else 0.0

            row_dict = {
                "platform": platform.lower(),
                "url": url,
                "creator": creator,          # 来自 API，不再从 CSV 读
                "posted_at": posted_dt,      # 转成 datetime 存数据库
                "views": views,
                "likes": likes,
                "comments": comments,
                "engagement_rate": engagement_rate,
            }
            save_result(row_dict)
            results.append(row_dict)

        except Exception as e:
            # 某一条失败不影响整体
            st.warning(f"抓取失败（第 {idx+1} 行）：{url}，原因：{e}")

        progress.progress(min((idx + 1) / total, 1.0), text=f"进度：{idx+1}/{total}")

    st.success(f"抓取完成！成功写入 {len(results)} 条记录。")

st.divider()
st.subheader("📊 历史抓取结果看板（来自 SQLite）")

# 简单筛选
with st.container():
    with SessionLocal() as s:
        stmt = select(Result).order_by(Result.id.asc())
        rows = s.execute(stmt).scalars().all()
        

    if rows:
        import pandas as pd
        data = pd.DataFrame([{
            "id": r.id,
            "platform": r.platform,
            "url": r.url,
            "creator": r.creator,
            "posted_at": r.posted_at,
            "views": r.views,
            "likes": r.likes,
            "comments": r.comments,
            "engagement_rate(%)": round(r.engagement_rate, 2),
            "fetched_at(UTC)": r.fetched_at,
        } for r in rows])
            # 读库后展示前
        data = data.sort_values("id", ascending=True)      # id 升序
        st.dataframe(data.set_index("id"), use_container_width=True, height=420)
            
     # —— 安全筛选区（根据实际列动态渲染）——
    cols = st.columns(3)

    # 平台筛选（一般都会有）
    with cols[0]:
        platform_filter = []
        if "platform" in data.columns:
            platform_filter = st.multiselect(
                "平台筛选",
                options=sorted(data["platform"].dropna().unique().tolist())
            )

    # 活动ID筛选：列不存在就不渲染
    with cols[1]:
        campaign_filter = []
        if "campaign_id" in data.columns:
            campaign_filter = st.multiselect(
                "活动ID筛选",
                options=sorted(data["campaign_id"].dropna().unique().tolist())
            )

    # KOL/作者筛选：列不存在就不渲染
    with cols[2]:
        creator_filter = []
        if "creator" in data.columns:
            creator_filter = st.multiselect(
                "KOL筛选",
                options=sorted(data["creator"].dropna().unique().tolist())
            )

    # 过滤逻辑：只有当列存在且用户选择了值时才应用
    filtered = data.copy()
    if platform_filter and "platform" in filtered.columns:
        filtered = filtered[filtered["platform"].isin(platform_filter)]
    if campaign_filter and "campaign_id" in filtered.columns:
        filtered = filtered[filtered["campaign_id"].isin(campaign_filter)]
    if creator_filter and "creator" in filtered.columns:
        filtered = filtered[filtered["creator"].isin(creator_filter)]

    st.dataframe(filtered.set_index("id"), use_container_width=True, height=420)

    st.download_button(
        "⬇️ 导出当前筛选结果（CSV）",
        data=filtered.to_csv(index=False),
        file_name="kol_results_filtered.csv",
        mime="text/csv"
    )





if run and not df.empty:
    st.write("开始抓取中，请稍等……（每周一次，通常几分钟内完成）")
    progress = st.progress(0, text="准备中...")
    total = len(df)
    results = []
    errors = []

    # 标准化列名
    df.columns = [str(c).strip().lower() for c in df.columns]

    # 自动推断 url 列（如用户没命名为 url）
    if "url" not in df.columns:
        import re as _re
        for c in df.columns:
            s = df[c].astype(str)
            if s.str.contains(r"^https?://", flags=_re.IGNORECASE, na=False).any():
                df = df.rename(columns={c: "url"})
                break

    # 自动推断 platform
    def infer_platform(u: str) -> str:
        ul = (u or "").lower()
        if "youtube.com" in ul or "youtu.be" in ul:
            return "youtube"
        if "instagram.com" in ul:
            return "instagram"
        if "tiktok.com" in ul:
            return "tiktok"
        return ""

    if "platform" not in df.columns:
        df["platform"] = df["url"].apply(infer_platform)

    # --- 分平台处理 ---
    df = df[["platform", "url", "creator", "campaign_id", "posted_at", "notes"] if "creator" in df.columns else ["platform","url"]].copy()

    # 1) YouTube 批量（需要 API Key）
    yt_rows = df[df["platform"].str.lower() == "youtube"]
    if not yt_rows.empty:
        if not youtube_api_key:
            errors.append("YouTube 抓取已禁用：未提供 API Key。")
        else:
            # 收集所有 videoId
            yt_rows = yt_rows.copy()
            yt_rows["video_id"] = yt_rows["url"].apply(extract_youtube_id)
            yt_rows = yt_rows[yt_rows["video_id"].notna()]
            vids = yt_rows["video_id"].tolist()

            # 分块请求（<= 50）
            chunk_size = 50
            stats_map = {}
            for i in range(0, len(vids), chunk_size):
                chunk = vids[i:i+chunk_size]
                try:
                    part = fetch_youtube_batch_stats(chunk, youtube_api_key)
                    stats_map.update(part)
                except Exception as e:
                    errors.append(f"YouTube 批量失败（{i}-{i+len(chunk)-1}）：{e}")

                progress.progress(min((i + chunk_size) / max(len(vids),1), 1.0), text=f"YouTube 批量：{min(i+chunk_size,len(vids))}/{len(vids)}")

            # 写入结果
            for _, r in yt_rows.iterrows():
                s = stats_map.get(r["video_id"], {"views":0,"likes":0,"comments":0})
                views = int(s.get("views",0)); likes = int(s.get("likes",0)); comments = int(s.get("comments",0))
                er = round(((likes+comments)/views*100.0), 2) if views>0 else 0.0
                results.append({
                    "platform": "youtube",
                    "url": r["url"],
                    "creator": r.get("creator"),
                    "campaign_id": r.get("campaign_id"),
                    "posted_at": r.get("posted_at"),
                    "views": views,
                    "likes": likes,
                    "comments": comments,
                    "engagement_rate": er,
                })

    # 2) 其他平台：仍使用 yt-dlp 单条（数量少影响不大）
    other_rows = df[df["platform"].str.lower().isin(["instagram","tiktok"])]
    processed = 0
    for idx, row in other_rows.iterrows():
        url = str(row.get("url","") or "").strip()
        platform = str(row.get("platform","") or "").strip().lower()
        if not url or not platform:
            errors.append(f"第 {idx+1} 行缺少 platform/url，已跳过。"); continue
        try:
            metrics = fetch_metrics(platform, url, None)
            views = int(metrics.get("views", 0))
            likes = int(metrics.get("likes", 0))
            comments = int(metrics.get("comments", 0))
            er = round(((likes+comments)/views*100.0), 2) if views>0 else 0.0
            results.append({
                "platform": platform,
                "url": url,
                "creator": row.get("creator"),
                "campaign_id": row.get("campaign_id"),
                "posted_at": row.get("posted_at"),
                "views": views, "likes": likes, "comments": comments,
                "engagement_rate": er,
            })
        except Exception as e:
            errors.append(f"抓取失败（第 {idx+1} 行）：{url}，原因：{e}")
        processed += 1
        # 适度更新进度
        if processed % 5 == 0 or processed == len(other_rows):
            progress.progress(1.0, text=f"其他平台：{processed}/{len(other_rows)}")

    # 写库（批量一次）
    from db import save_result, SessionLocal
    if results:
        from sqlalchemy.orm import Session
        with SessionLocal() as s:
            from db import Result
            s.bulk_insert_mappings(Result, results)
            s.commit()
        st.success(f"抓取完成！成功写入 {len(results)} 条记录。")
    else:
        st.warning("未写入记录。")

    if errors:
        st.warning("以下记录未写入/失败：\n" + "\n".join(errors))