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
youtube_api_key = st.text_input("YouTube API Key（可选）", type="password", help="不填也可以运行，默认使用 yt-dlp。")

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

        creator = row.get("creator", None)
        campaign_id = row.get("campaign_id", None)
        posted_at = row.get("posted_at", None)

        try:
            metrics = fetch_metrics(platform, url, youtube_api_key if youtube_api_key else None)
            views = int(metrics.get("views", 0))
            likes = int(metrics.get("likes", 0))
            comments = int(metrics.get("comments", 0))

            # 计算互动率，避免除零
            engagement_rate = round(((likes + comments) / views * 100.0), 2) if views > 0 else 0.0

            row_dict = {
                "platform": platform.lower(),
                "url": url,
                "creator": creator,
                "campaign_id": campaign_id,
                "posted_at": posted_at,
                "views": views,
                "likes": likes,
                "comments": comments,
                "engagement_rate": engagement_rate,
            }
            # 保存入库
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
        stmt = select(Result).order_by(Result.id.desc())
        rows = s.execute(stmt).scalars().all()

    if rows:
        data = pd.DataFrame([{
            "id": r.id,
            "platform": r.platform,
            "url": r.url,
            "creator": r.creator,
            "campaign_id": r.campaign_id,
            "posted_at": r.posted_at,
            "views": r.views,
            "likes": r.likes,
            "comments": r.comments,
            "engagement_rate(%)": round(r.engagement_rate, 2),
            "fetched_at(UTC)": r.fetched_at,
        } for r in rows])
        
        # 侧边筛选
        col1, col2, col3 = st.columns(3)
        with col1:
            platform_filter = st.multiselect("平台筛选", options=sorted(data["platform"].dropna().unique().tolist()))
        with col2:
            campaign_filter = st.multiselect("活动ID筛选", options=sorted(data["campaign_id"].dropna().unique().tolist()))
        with col3:
            creator_filter = st.multiselect("KOL筛选", options=sorted(data["creator"].dropna().unique().tolist()))

        filtered = data.copy()
        if platform_filter:
            filtered = filtered[filtered["platform"].isin(platform_filter)]
        if campaign_filter:
            filtered = filtered[filtered["campaign_id"].isin(campaign_filter)]
        if creator_filter:
            filtered = filtered[filtered["creator"].isin(creator_filter)]

        st.dataframe(filtered, use_container_width=True, height=420)

        # 导出当前筛选结果
        st.download_button(
            "⬇️ 导出当前筛选结果（CSV）",
            data=filtered.to_csv(index=False),
            file_name="kol_results_filtered.csv",
            mime="text/csv"
        )
    else:
        st.info("当前数据库暂无记录。请先上传表格并点击“开始获取”。")
