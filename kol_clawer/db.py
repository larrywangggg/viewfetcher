# -*- coding: utf-8 -*-
# db.py
# 说明：用 SQLAlchemy 管理一个名为 results 的表，存储每次抓取的标准化结果

from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

DB_URL = "sqlite:///kol_results.sqlite3"

engine = create_engine(DB_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

class Result(Base):
    __tablename__ = "results"
    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String, nullable=False)         # 平台：youtube/instagram/tiktok
    url = Column(String, nullable=False, index=True)  # 视频/帖子链接
    creator = Column(String)                          # KOL 名称（可选）
    campaign_id = Column(String)                      # 活动ID（可选）
    posted_at = Column(String)                        # 上线日期（可选，原样存）
    views = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    engagement_rate = Column(Float, default=0.0)      # (likes + comments) / views * 100
    fetched_at = Column(DateTime, default=datetime.utcnow)  # 抓取时间（UTC）

def init_db():
    Base.metadata.create_all(bind=engine)

def save_result(row_dict):
    """row_dict: {platform, url, creator?, campaign_id?, posted_at?, views, likes, comments, engagement_rate}"""
    with SessionLocal() as s:
        r = Result(**row_dict)
        s.add(r)
        s.commit()
