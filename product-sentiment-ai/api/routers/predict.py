"""
案例:
    情感预测接口（路由层：只转发，不写模型细节）
"""

# 导包
from fastapi import APIRouter, HTTPException

from api.schemas import OkResp, PredictBatchReq, PredictItem, PredictReq
from api.services import predict_service

router = APIRouter(prefix="/api/predict", tags=["预测"])


# 1. 单句预测
@router.post("/one", response_model=PredictItem, summary="单句情感预测")
def predict_one(body: PredictReq):
    try:
        # 参1: text 评论文本  参2: model 模型名
        return predict_service.predict_one(body.text, model=body.model)
    except FileNotFoundError as e:
        raise HTTPException(503, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


# 2. 批量预测
@router.post("/batch", response_model=OkResp, summary="批量情感预测")
def predict_batch(body: PredictBatchReq):
    try:
        items = predict_service.predict_batch(body.texts, model=body.model)
    except FileNotFoundError as e:
        raise HTTPException(503, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    print(f'批量预测完成: {len(items)} 条')
    return OkResp(ok=True, message=f"共 {len(items)} 条", data=items)
