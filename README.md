# product-sentiment-plus

# product-sentiment-ai

目录按任务分工划分，命名见名知意（无数字前缀）。

## 目录与人员

| 目录 | 对应分工 | 人员 |
|------|----------|------|
| `data/` | 数据处理 | 刘攀 / 唐海乘 / 江彩亮 |
| `models/baseline/` | 基线 | 人员4 |
| `models/fasttext/` | FastText | 人员5 |
| `models/bert_all/` | 总BERT | 人员6 |
| `models/bert_category/` | 类目BERT | 人员7 / 人员8 |
| `backend/` | 后端+项目部署 | 郑平高 |
| `frontend/` | 前端 | 邓新晓 |

## 结构

```text
product-sentiment-ai/
├── docs/                         # 任务分工、数据说明等
├── data/                         # 数据处理
│   ├── sources/                  # 原始数据（只读）
│   ├── processed/                # 预处理产出（reviews 等）
│   ├── annotated/                # 人工标注产出（review_tags）
│   ├── vocab/                    # 品类标签词表
│   ├── examples/                 # 字段格式示例
│   └── scripts/
│       ├── preprocess/           # 预处理脚本
│       └── annotate/             # 标注辅助脚本
├── models/                       # 模型
│   ├── common/                   # 共用：读数据、评测
│   │   ├── dataset/
│   │   └── metrics/              # 共用的评测代码
│   ├── baseline/                 # 基线
│   ├── fasttext/                 # FastText
│   ├── bert_all/                 # 总BERT
│   └── bert_category/            # 类目BERT
│       ├── scripts/              # 训练/推理
│       ├── checkpoints/          # 权重（不入库）
│       └── results/              # 指标与日志
├── backend/                      # 后端
│   ├── app/                      # 接口
│   └── deploy/                   # 部署
└── frontend/                     # 前端
    └── src/                      # 页面
```

## 数据流向

```text
data/sources
  → data/processed
  → data/annotated + data/vocab
  → models/*/scripts 训练
  → data/processed/product_tags.csv（或入库）
  → backend → frontend
```

## 示例数据文件（无序号）

| 文件 | 含义 |
|------|------|
| `data/examples/reviews.csv` | 评论主表 |
| `data/examples/review_tags.csv` | 评论标签明细 |
| `data/examples/product_tags.csv` | 商品标签墙 |
| `data/examples/category_tag_vocab.csv` | 品类标签字典 |


## 后端启动
'''
.\.venv\Scripts\python.exe backend\run.py
'''
    
## 前端启动

 '''
cd front
pnpm dev
'''
