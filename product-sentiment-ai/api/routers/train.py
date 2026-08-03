"""
案例:
    训练接口：后台启动 train.py，不阻塞 HTTP。
"""

# 导包
from fastapi import APIRouter, HTTPException

from api.schemas import JobResp, OkResp, TrainReq
from api.services import predict_service, tag_service, train_service

router = APIRouter(prefix="/api/train", tags=["训练"])


# 1. 启动训练
@router.post("/start", response_model=JobResp, summary="启动某个模型训练")
def start_train(body: TrainReq):
    try:
        job_id = train_service.start_train(
            model=body.model,
            max_samples=body.max_samples,
            epochs=body.epochs,
            batch_size=body.batch_size,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    print(f'训练任务已创建: model={body.model} job_id={job_id}')
    return JobResp(
        ok=True,
        job_id=job_id,
        status="pending",
        message=f"已启动训练: {body.model}，用 /api/jobs/{job_id} 查进度",
    )


# 2. 训练完刷新预测缓存
@router.post("/reload", response_model=OkResp, summary="训练完成后刷新预测模型缓存")
def reload_models():
    predict_service.clear_model_cache()
    tag_service.clear_tag_model_cache()
    return OkResp(ok=True, message="预测/打标模型缓存已清空，下次请求会重新加载")
