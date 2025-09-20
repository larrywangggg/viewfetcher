# db.py
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
    platform = Column(String, nullable=False)
    url = Column(String, nullable=False, index=True, unique=True)
    creator = Column(String)                 # ← 只是列定义
    posted_at = Column(DateTime)             # ← 建议存成 DateTime（也可用 String）
    views = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    engagement_rate = Column(Float, default=0.0)
    fetched_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)

from datetime import datetime

def save_result(row_dict: dict):
    """根据 url 做 UPSERT：若已存在则更新；否则插入。"""
    with SessionLocal() as s:
        # 先查现有记录
        existing = s.query(Result).filter_by(url=row_dict["url"]).first()
        if existing:
            # 只更新数值类与 fetched_at；creator/posted_at 只有在新值非空时才覆盖
            existing.platform = row_dict.get("platform", existing.platform)
            existing.views = row_dict.get("views", existing.views)
            existing.likes = row_dict.get("likes", existing.likes)
            existing.comments = row_dict.get("comments", existing.comments)
            existing.engagement_rate = row_dict.get("engagement_rate", existing.engagement_rate)

            new_creator = row_dict.get("creator")
            if new_creator:  # 只有有值才覆盖，避免把已有值改成 None/空
                existing.creator = new_creator

            new_posted_at = row_dict.get("posted_at")
            if new_posted_at:  # 同上
                existing.posted_at = new_posted_at

            existing.fetched_at = datetime.utcnow()
        else:
            # 新记录：直接插入
            s.add(Result(**row_dict))
        s.commit()

