# product-sentiment-ai

拼多多风格的「按商品动态多标签」+ 评论情感分类模型链路。

核心目标有两条，别混：

1. **商品动态多分类（标签墙）**：从评论抽出方面/观点标签，再按商品聚合，得到「128 人说质量好」这种动态标签。
2. **情感分类模型阶梯**：用同一份评论数据，训练 **基线 → FastText → BERT → 蒸馏学生**，给评论打好评/差评，并可对比效果。

---

## 用到了哪些技术、怎么用的

| 技术 | 在本项目里干什么 | 对应代码 |
|------|------------------|----------|
| **数据清洗 / 特征拼接** | 读 `sources`（只读），拼商品名/品类，标题+正文组成 `sentence`，评分≥4 标为好评 | `data/scripts/preprocess/prepare_reviews.py` |
| **规则 + 正则（方面抽取）** | 拼多多式动态打标：评论命中规则 → `review_tags` → 按商品计数聚合 → `product_tags` | `data/scripts/annotate/dynamic_tagging.py` |
| **jieba 分词** | 基线模型把中文切成词，再喂给 TF-IDF | `models/baseline/scripts/train.py` |
| **TF-IDF + LogisticRegression（ML 基线）** | 经典机器学习垫底：词袋特征 + 线性分类 | 同上 |
| **字符 n-gram + SGD（FastText 风格）** | 模拟 FastText 的 char-ngram 思想；Windows 难装官方 C++ 库时用等价线性模型 | `models/fasttext/scripts/train.py` |
| **BERT 微调（Teacher）** | `bert-base-chinese` 做全品类情感二分类，效果上限通常最高 | `models/bert/common/scripts/train.py` |
| **类目 BERT** | 在样本最多的几个品类上继续微调，做分品类加强 | `models/bert/category/scripts/train.py` |
| **知识蒸馏（Distillation）** | 冻结教师 BERT，用软标签教更小的 4 层学生 BERT，换速度/体积 | `models/bert/distill/scripts/train.py` |
| **评测指标** | accuracy / precision / recall / F1（二分类） | `models/common/metrics/evaluate.py` |

### 蒸馏公式（实现里就是这样算的）

\[
L = \alpha \cdot CE(y_{hard}, p_{student}) + (1-\alpha)\cdot T^{2}\cdot KL\!\left(\mathrm{softmax}(z_t/T)\,\|\,\mathrm{softmax}(z_s/T)\right)
\]

- \(z_t, z_s\)：教师 / 学生 logits  
- \(T\)：温度（默认 4，越大软标签越「平」）  
- \(\alpha\)：硬标签权重（默认 0.3，更相信教师软标签）

学生结构：`hidden=312, layers=4`，参数量远小于 12 层教师，适合部署。

---

## 数据怎么处理的（你先跑这一步）

`data/sources/` **只读**，脚本只往 `data/processed/` 写。

```text
sources/训练集.csv + 商品信息.csv + 商品类别列表.csv
        │
        ▼  prepare_reviews.py
processed/reviews.csv          # 全量：sentence / sentiment / category / product_id
processed/reviews_train.csv    # 90%
processed/reviews_val.csv      # 10%
processed/reviews_test.csv     # 官方测试集（无评分）
        │
        ▼  dynamic_tagging.py
processed/review_tags.csv      # 评论级标签明细
processed/product_tags.csv     # 商品级标签墙（动态多标签结果）
vocab/category_tag_vocab.csv   # 标签词表
```

情感标签与清洗规则（`prepare_reviews.py`）：

| 规则 | 说明 |
|------|------|
| 好评 | `评分 >= 4` → `sentiment=1` |
| 差评 | `评分 <= 2` → `sentiment=0` |
| **丢掉中性分** | `评分 == 3` 不进训练集 |
| 文本清洗 | 去 HTML/URL/邮箱、压空白、压缩叠字叠标点 |
| 合法性 | 长度≥6、至少 2 个汉字、非纯符号 |
| 去重 | 按 `sentence` 去重 |

### FastText 测试

```bash
# 训练
python -m models.fasttext.scripts.train

# 验证集评测
python -m models.fasttext.scripts.predict --eval-val

# 单句预测
python -m models.fasttext.scripts.predict --text "质量很好，发货也快，下次还买"

# 批量预测官方测试集（写出 csv）
python -m models.fasttext.scripts.predict --predict-test
```

---

## 环境

```bash
# 推荐已有 conda 环境
conda activate product-sentiment-plus
cd product-sentiment-ai

# 若缺包
pip install pandas scikit-learn jieba joblib torch transformers tqdm modelscope
```

首次训 BERT 若本机没有权重：

```bash
python -m models.common.scripts.download_bert
```

---

## 你怎么训练（按顺序）

### 1）只处理数据（已可单独跑）

```bash
python data/scripts/preprocess/prepare_reviews.py
python data/scripts/preprocess/verify_processed.py
python data/scripts/annotate/dynamic_tagging.py
```

看商品标签墙：打开 `data/processed/product_tags.csv`。

### 2）机器学习基线

```bash
python -m models.baseline.scripts.train
# 小样本调试：
python -m models.baseline.scripts.train --max-samples 3000
```

产出：`models/baseline/model/baseline.joblib` + `results/metrics.json`

### 3）FastText 风格

```bash
python -m models.fasttext.scripts.train
```

产出：`models/fasttext/model/fasttext_style.joblib`

### 4）BERT 教师

```bash
# 推荐：FP16 + 动态padding + 较大 batch（本地权重，不联网）
python -m models.bert.common.scripts.train --epochs 3 --batch-size 48 --threshold-tune

# 更看重精确率时：
python -m models.bert.common.scripts.train --epochs 3 --batch-size 48 --threshold-tune --metric precision

# 可选：分品类加强
python -m models.bert.category.scripts.train --epochs 2 --top-n-categories 3
```

产出：`models/bert/common/model/bert_all/`

### 5）模型蒸馏

```bash
# 必须先有教师 bert_all
python -m models.bert.distill.scripts.train --epochs 3
```

产出：`models/bert/distill/model/bert_student/`

### 6）一键流水线 / 对比

```bash
python run_pipeline.py --smoke          # 冒烟
python run_pipeline.py --full           # 全量
python -m models.common.scripts.compare_results
```

对比表：`models/common/results/model_compare.csv`

---

## 实现思路（用大白话串起来）

```text
评论原文
  ├─① 规则抽标签 ──► 按商品聚合 ──► 拼多多式「动态标签墙」
  └─② 情感二分类
        ├─ 基线：分词 + TF-IDF + LR     （快、可解释、垫底）
        ├─ FastText风格：char-ngram     （不用分词，抓局部字串）
        ├─ BERT：上下文语义             （效果最好，当教师）
        └─ 蒸馏：小模型学教师软标签     （接近教师效果，更轻）
```

「动态多分类」指的是：**标签集合不写死在某个商品上**，而是评论来了才抽、再按商品统计；不同商品、不同时间窗口，墙上的标签分布都会变。

监督模型学的是「这句话整体好评还是差评」；标签墙学的是「这句话提到了哪些方面」。两条线共用处理后的 `sentence`。

---

## API（解耦分层）

```text
api/
├── main.py          # 只组装路由，不写业务
├── config.py        # 只放路径
├── schemas.py       # 请求/响应长什么样
├── routers/         # 接口层：收参数 → 调 service → 返回
└── services/        # 业务层：真正干活（跑脚本/读模型/查 CSV）
```

谁干什么，一句话：

| 层 | 干什么 | 别在这里干啥 |
|----|--------|--------------|
| `routers/` | URL 和 HTTP | 别写训练/读模型细节 |
| `services/` | 业务逻辑 | 别写 FastAPI 装饰器 |
| `models/*/scripts/` | 原训练脚本 | 被 service 用子进程调用 |
| `config.py` | 路径常量 | 别写算法 |

### 启动

```bash
cd product-sentiment-ai
python -m uvicorn api.main:app --reload --port 8001
```

### 导包说明（红线 / ModuleNotFoundError）

用包导包；路径写在函数里，不要模块顶层静态变量：

```python
from models.common.dataset.load_reviews import load_xy

def main():
    ckpt = "./models/baseline/model/baseline.joblib"
    result = "./models/baseline/results/metrics.json"
    ...
```

训练请在 `product-sentiment-ai` 目录下用模块方式运行：

```bash
python -m models.baseline.scripts.train
python -m models.fasttext.scripts.train
python -m models.bert.common.scripts.train
```

IDE 已配置 `extraPaths`。若仍报红：重启 IDE，并确认 conda 环境。

浏览器打开：http://127.0.0.1:8001/docs

### 常用接口

| 方法 | 路径 | 作用 |
|------|------|------|
| GET | `/health` | 健康检查、模型是否存在 |
| POST | `/api/data/prepare` | 后台清洗数据 |
| POST | `/api/tag/run` | 后台动态打标 |
| POST | `/api/train/start` | 后台训练（body: `{"model":"fasttext"}`） |
| GET | `/api/jobs/{job_id}` | 查后台任务进度 |
| POST | `/api/predict/one` | 单句预测（`{"text":"...","model":"fasttext"}`） |
| GET | `/api/products/{product_id}/tags` | 商品标签墙 |
| POST | `/api/train/reload` | 训练完刷新预测缓存 |

`model` 可选：`baseline` / `fasttext` / `bert` / `distill` / `bert_category` / `compare`

---

## 目录

```text
product-sentiment-ai/
├── README.md
├── run_pipeline.py
├── api/                         # FastAPI（解耦入口）
├── data/
│   ├── sources/                 # 原始数据（只读）
│   ├── processed/               # 处理后的训练/标签数据
│   ├── vocab/
│   └── scripts/
│       ├── preprocess/          # prepare_reviews / verify
│       └── annotate/            # dynamic_tagging
└── models/
    ├── common/                  # 读数据、评测、下权重
    ├── baseline/model/          # 基线权重
    ├── fasttext/model/
    └── bert/
        ├── common/model/        # 总 BERT
        ├── category/model/      # 类目 BERT
        └── distill/model/       # 蒸馏学生
```

---

## 注意

- **不要改** `data/sources/` 下的原始 CSV。
- Windows 上官方 `fasttext` 常装不上，本仓库用 **char-ngram 线性模型** 复现同一思想；若 Linux 可装官方库，可自行替换训练脚本，输入输出接口保持一致即可。
- 蒸馏脚本默认读取 `models/bert/common/model/bert_all`；没有教师时会退回预训练权重，但效果会差一截，建议先训教师。
- GPU 可用时 BERT/蒸馏会自动用 CUDA。
