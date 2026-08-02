from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, Integer, Numeric, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BizCategory(Base):
    """商品类目（邻接表 + path 物化路径，支持多层嵌套）。"""

    __tablename__ = "biz_category"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    parent_id: Mapped[Optional[str]] = mapped_column(String(32), default="")
    name: Mapped[str] = mapped_column(String(100))
    code: Mapped[Optional[str]] = mapped_column(String(64))
    path: Mapped[Optional[str]] = mapped_column(String(512))
    level: Mapped[Optional[int]] = mapped_column(Integer, default=1)
    sort_no: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    icon: Mapped[Optional[str]] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(String(500))
    is_leaf: Mapped[Optional[int]] = mapped_column(SmallInteger, default=1)
    status: Mapped[Optional[int]] = mapped_column(SmallInteger, default=1)
    del_flag: Mapped[Optional[int]] = mapped_column(SmallInteger, default=0)
    create_by: Mapped[Optional[str]] = mapped_column(String(32))
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    update_by: Mapped[Optional[str]] = mapped_column(String(32))
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime)


class BizProduct(Base):
    __tablename__ = "biz_product"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    category_id: Mapped[Optional[str]] = mapped_column(String(32))
    brand: Mapped[Optional[str]] = mapped_column(String(100))
    sku: Mapped[Optional[str]] = mapped_column(String(64))
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    original_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    currency: Mapped[Optional[str]] = mapped_column(String(8), default="CNY")
    cover_url: Mapped[Optional[str]] = mapped_column(String(500))
    rating: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 1))
    stock: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    unit: Mapped[Optional[str]] = mapped_column(String(20))
    status: Mapped[Optional[int]] = mapped_column(SmallInteger, default=1)
    description: Mapped[Optional[str]] = mapped_column(Text)
    note: Mapped[Optional[str]] = mapped_column(String(1000))
    del_flag: Mapped[Optional[int]] = mapped_column(SmallInteger, default=0)
    create_by: Mapped[Optional[str]] = mapped_column(String(32))
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    update_by: Mapped[Optional[str]] = mapped_column(String(32))
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime)


class BizSentimentQuery(Base):
    __tablename__ = "biz_sentiment_query"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(32))
    username: Mapped[Optional[str]] = mapped_column(String(100))
    product_id: Mapped[Optional[str]] = mapped_column(String(32))
    product_name: Mapped[Optional[str]] = mapped_column(String(200))
    category_id: Mapped[Optional[str]] = mapped_column(String(32))
    category_name: Mapped[Optional[str]] = mapped_column(String(100))
    content: Mapped[str] = mapped_column(Text)
    sentiment: Mapped[Optional[str]] = mapped_column(String(20))
    score: Mapped[Optional[int]] = mapped_column(Integer)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    keywords: Mapped[Optional[str]] = mapped_column(String(1000))
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime)


class BizCausalResult(Base):
    """按类目因果分析结果。"""

    __tablename__ = "biz_causal_result"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    category_id: Mapped[Optional[str]] = mapped_column(String(32))
    category_name: Mapped[str] = mapped_column(String(100))
    sample_size: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    treatment_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    outcome_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    ate: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    ate_text: Mapped[Optional[str]] = mapped_column(String(500))
    treated_positive_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    control_positive_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    table_json: Mapped[Optional[str]] = mapped_column(String(1000))
    explanation: Mapped[Optional[str]] = mapped_column(String(1000))
    source: Mapped[Optional[str]] = mapped_column(String(20), default="ai")
    del_flag: Mapped[Optional[int]] = mapped_column(SmallInteger, default=0)
    create_by: Mapped[Optional[str]] = mapped_column(String(32))
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    update_by: Mapped[Optional[str]] = mapped_column(String(32))
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime)


class BizKeyword(Base):
    """方面关键词词典：用于评价标签归并与看板分析。"""

    __tablename__ = "biz_keyword"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    word: Mapped[str] = mapped_column(String(100))
    aspect: Mapped[Optional[str]] = mapped_column(String(64))
    # 空 = 通用（跨类目）；有值 = 类目专属
    category_id: Mapped[Optional[str]] = mapped_column(String(32))
    category_name: Mapped[Optional[str]] = mapped_column(String(100))
    polarity: Mapped[Optional[str]] = mapped_column(String(20), default="any")
    alias: Mapped[Optional[str]] = mapped_column(String(500))
    weight: Mapped[Optional[int]] = mapped_column(Integer, default=1)
    status: Mapped[Optional[int]] = mapped_column(SmallInteger, default=1)
    sort_no: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    remark: Mapped[Optional[str]] = mapped_column(String(500))
    del_flag: Mapped[Optional[int]] = mapped_column(SmallInteger, default=0)
    create_by: Mapped[Optional[str]] = mapped_column(String(32))
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    update_by: Mapped[Optional[str]] = mapped_column(String(32))
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
