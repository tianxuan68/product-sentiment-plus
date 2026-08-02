"""
案例:
    动态打标业务
"""

# 导包
from api.services.job_runner import python_cmd, start_job


# 1. 启动打标脚本
def start_tagging(min_count=1, top_k=15):
    script = "./data/scripts/annotate/dynamic_tagging.py"
    print(f'启动打标 min_count={min_count} top_k={top_k}')
    return start_job(
        python_cmd(
            script,
            "--min-count",
            str(min_count),
            "--top-k",
            str(top_k),
        )
    )
