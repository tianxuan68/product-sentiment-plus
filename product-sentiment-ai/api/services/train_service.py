"""
案例:
    训练业务：把「选哪个模型」翻译成「跑哪个模块」。
"""

# 导包
from api.services.job_runner import python_module, start_job


# 1. 定义函数, 拼训练命令参数
def _build_cmd(module, max_samples=None, epochs=None, batch_size=None):
    cmd = python_module(module)
    if max_samples is not None:
        cmd += ["--max-samples", str(max_samples)]
    if epochs is not None:
        cmd += ["--epochs", str(epochs)]
    if batch_size is not None:
        cmd += ["--batch-size", str(batch_size)]
    return cmd


# 2. 定义函数, 启动训练
def start_train(model, max_samples=None, epochs=None, batch_size=None):
    model = model.strip().lower()
    mapping = {
        "baseline": "models.baseline.scripts.train",
        "fasttext": "models.fasttext.scripts.train",
        "bert": "models.bert.common.scripts.train",
        "bert_category": "models.bert.category.scripts.train",
        "distill": "models.bert.distill.scripts.train",
        "compare": "models.common.scripts.compare_results",
    }
    if model == "all":
        raise ValueError(
            "请分步训练更清晰：baseline → fasttext → bert → bert_category → distill → compare"
        )
    if model not in mapping:
        raise ValueError(
            f"未知模型: {model}，可选: {', '.join(sorted(mapping))}"
        )

    module = mapping[model]
    print(f'准备训练: {model} → python -m {module}')
    if model == "compare":
        return start_job(python_module(module))
    return start_job(
        _build_cmd(module, max_samples=max_samples, epochs=epochs, batch_size=batch_size)
    )
