# product-sentiment-plus

电商评论情感分析 + 拼多多式商品动态标签墙。

AI 训练与数据处理在子目录 **`product-sentiment-ai/`**，技术说明、训练步骤见：

→ [`product-sentiment-ai/README.md`](product-sentiment-ai/README.md)

## 技术栈一览

| 技术 | 用途 |
|------|------|
| 数据清洗 / 分层切分 | 从 `sources` 生成可训练的 `reviews_*.csv` |
| 规则方面抽取 + 按商品聚合 | 拼多多式动态多标签墙 |
| jieba + TF-IDF + LR | 机器学习基线 |
| 字符 n-gram（FastText 风格） | 轻量 NLP 升级 |
| BERT 微调 | 强效果教师模型 |
| 知识蒸馏 | 小学生模型学习教师软标签 |
| FastAPI / Jeecg 前后端 | 展示与业务系统（`backend/`、`front/`） |

## 快速开始（训练）

```bash
conda activate product-sentiment-plus
cd product-sentiment-ai

# 1. 处理数据 + 动态打标
python data/scripts/preprocess/prepare_reviews.py
python data/scripts/annotate/dynamic_tagging.py

# 2. 训练（或一键）
python run_pipeline.py --smoke
# python run_pipeline.py --full
```

详细原理与每步命令见 `product-sentiment-ai/README.md`。
