"""
案例:
    请求 / 响应数据结构（Pydantic）。

大白话:
    看字段名就知道前端传什么、接口返回什么。
"""

# 导包
from typing import Any, Optional

from pydantic import BaseModel, Field


# 1. 通用响应
class OkResp(BaseModel):
    ok: bool = True
    message: str = ""
    data: Any = None


class JobResp(BaseModel):
    ok: bool = True
    job_id: str
    status: str
    message: str = ""


class JobStatusResp(BaseModel):
    ok: bool = True
    job_id: str
    status: str  # pending / running / success / failed
    command: list[str] = []
    returncode: Optional[int] = None
    stdout_tail: str = ""
    error: str = ""


# 2. 预测相关
class PredictReq(BaseModel):
    text: str = Field(..., min_length=1, description="评论文本")
    # 参2: 选哪个模型，默认 fasttext 又快又稳
    model: str = Field(
        "fasttext",
        description="baseline | fasttext | bert | distill",
    )


class PredictItem(BaseModel):
    text: str
    pred: int
    label: str
    prob_neg: Optional[float] = None
    prob_pos: Optional[float] = None
    confidence: Optional[float] = None
    model: str


class PredictBatchReq(BaseModel):
    texts: list[str] = Field(..., min_length=1)
    model: str = "fasttext"


# 3. 训练相关
class TrainReq(BaseModel):
    model: str = Field(
        ...,
        description="baseline | fasttext | bert | bert_category | distill | tagging | tagging_bert | tagging_hier | compare",
    )
    # 参2: 小样本调试用；正式训练别传
    max_samples: Optional[int] = Field(None, description="小样本调试")
    epochs: Optional[int] = None
    batch_size: Optional[int] = None


# 4. 打标相关
class TagRunReq(BaseModel):
    min_count: int = 1
    top_k: int = 15
    # rules=标准短标签词表（默认）；open=开放短语聚合
    mode: str = Field("rules", description="rules | open")


class TagPredictReq(BaseModel):
    text: str = Field(..., min_length=1, description="评论文本")
    product_id: str = Field("", description="评论所属商品 ID；草稿可空")
    category: Optional[str] = Field(None, description="类目（无 product_id 时用）")
    product_name: Optional[str] = None
    # model=标准短标签BERT（默认）；rules=规则词表；open=原文短语；hybrid=开放∪模型
    method: str = Field(
        "model",
        description="model | rules | open | hybrid | auto",
    )


class FrontProductDraft(BaseModel):
    name: str = ""
    category: str = ""
    rating: str = ""
    note: str = ""


class FrontPredictReq(BaseModel):
    content: str = Field(..., min_length=1, description="用户反馈原文")
    productId: Optional[str] = None
    product: Optional[FrontProductDraft] = None


class FrontPredictResp(BaseModel):
    sentiment: str  # positive | neutral | negative
    score: int
    summary: str
    keywords: list[str] = []


class TagHit(BaseModel):
    aspect: str
    tag: str
    polarity: str
    score: Optional[float] = None
    source: Optional[str] = None  # open_clause | hier_general | hier_category | rules
    scope: Optional[str] = None  # open | general | category


class TagPredictResp(BaseModel):
    text: str
    product_id: str
    category: Optional[str] = None
    product_name: Optional[str] = None
    tags: list[TagHit]
    tag_names: list[str] = []
    method: str = "model"
    backend: Optional[str] = None  # bert_hierarchical | rules | open_extract | open+model


# 5. 商品标签墙
class ProductTagItem(BaseModel):
    tag: str
    polarity: str
    count: int
    ratio: float
    category: Optional[str] = None
