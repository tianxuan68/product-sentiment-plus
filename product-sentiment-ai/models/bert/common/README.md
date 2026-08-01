# BERT 商品评论情感多标签分类

基于 `bert-base-chinese` 的商品评论**多标签（multi-label）情感分类**项目。

**任务定义**：输入一条商品评论文本，输出其包含的多个「方面-情感」标签。例如：

```
输入文本：客服推荐的尺码合适，发货也很快，下次还会光顾的
预测标签：尺码合适，发货快
```

一条评论可以同时命中多个标签（如「尺码合适」「发货快」同时存在），
因此本项目按 **multi-label 多标签分类**建模：BERT 编码后接一个与标签数量等长的分类头，
每个维度用 `sigmoid` 二分类判定该标签是否命中（`BCEWithLogitsLoss` 训练）。

---

## 1. 目录结构

```
common/
├── bert-base-chinese/          # 预训练 BERT 权重（本地，无需联网）
├── data/
│   └── synthetic/              # 合成测试数据（真实标注数据就绪前用于跑通流程）
├── checkpoints/                # 模型保存目录（最佳模型 / 最终模型）
├── results/                    # 指标、日志、标签列表
├── scripts/                    # 项目代码（全部代码都写在这里）
│   ├── config.py               # 全局配置字典（超参数与路径集中管理）
│   ├── data_utils.py           # 标签词表加载 / 合成数据生成 / 标注数据读取
│   ├── dataset.py              # 多标签 Dataset 与 multi-hot 标签编码
│   ├── model.py                # BERT + 分类头多标签模型
│   ├── train.py                # 训练主程序
│   └── predict.py              # 推理主程序
└── README.md                   # 本文档
```

## 2. 环境依赖

使用项目根目录 `requirements.txt` 中已有的虚拟环境即可，关键依赖：

```
torch>=2.0
transformers>=4.30
pandas
scikit-learn
tqdm
numpy
```

本项目无需额外安装。运行前确认能导入 torch 与 transformers：

```bash
python -c "import torch, transformers; print(torch.__version__, transformers.__version__)"
```

## 3. 数据说明

### 3.1 标签词表

多标签分类的「类别」来自品类标签字典 `data/examples/category_tag_vocab.csv`
（每行为 `category,aspect,tag,polarity`）。程序会读取其中全部 `tag` 去重作为标签集合。

### 3.2 标注数据格式（真实数据）

训练/验证/测试数据支持两种格式，程序自动识别：

- **扁平格式（推荐）**：每行一条评论，`tags` 用 `|` 分隔

  | review_id | sentence | tags |
  |-----------|----------|------|
  | r001 | 质量很好，发货快 | 质量好\|发货快 |

- **长表格式**（与 `data/examples/review_tags.csv` 一致）：每行一个标签明细，
  程序按 `review_id` 自动聚合

  | review_id | category | aspect | opinion | polarity | tag |
  |-----------|----------|--------|---------|----------|-----|
  | r001 | 女装 | 质量 | 很好 | positive | 质量好 |

真实数据就绪后，把标注好的数据放到 `data/` 下，并修改 `config.py` 中的
`train_file / val_file / test_file` 路径即可直接训练。

### 3.3 合成数据（测试用）

由于正式训练数据尚未准备好，项目内置了**合成数据生成器**：
根据标签词表为每个标签预置若干句同义模板句，随机抽取 1~3 个标签拼接成一条评论，
生成带标注的训练/验证/测试数据，用于跑通全流程。

```bash
python scripts/data_utils.py
```

默认生成 训练 600 条 / 验证 100 条 / 测试 100 条，输出到 `data/synthetic/`。

## 4. 快速开始

### 4.1 训练

```bash
# 使用默认配置训练（自动选择 GPU，无 GPU 自动回退 CPU）
python scripts/train.py

# 覆盖部分超参数
python scripts/train.py --epochs 5 --batch_size 32 --lr 3e-5
python scripts/train.py --device cpu   # 强制 CPU
```

训练过程中：

- 每轮在验证集上评估，打印 Macro-F1 / Exact-ACC 等指标；
- 验证集指标最优的模型自动保存到 `checkpoints/best_model.pt`；
- 全部训练结束后保存最终模型到 `checkpoints/final_model.pt`；
- 训练日志写入 `results/train_log.csv`，测试集指标写入 `results/test_metrics.json`，
  标签列表备份到 `results/tags.txt`。

### 4.2 推理

```bash
# 单条文本预测（默认加载最佳模型）
python scripts/predict.py --text "客服推荐的尺码合适，发货也很快"

# 指定模型 / 设备
python scripts/predict.py --checkpoint checkpoints/final_model.pt --device cpu --text "质量很差，客服也没人管"

# 批量预测：文件每行一条文本，结果输出为 CSV
python scripts/predict.py --input_file data/synthetic/sample_texts.txt --output_file data/synthetic/predict_result.csv
```

预测输出为逗号连接命中的标签，例如 `尺码合适，发货快`；
同时打印各标签概率，便于调整判定阈值（`config.py` 中的 `threshold`，默认 0.65，
也可通过 `--threshold` 参数临时覆盖）。

## 5. 配置说明（Config）

所有超参数集中在 `scripts/config.py` 的 `Config` 字典中，常用项：

| 键 | 含义 | 默认 |
|----|------|------|
| `model_name_or_path` | 预训练 BERT 本地目录 | `bert-base-chinese/` |
| `max_len` | 输入文本最大长度 | 64 |
| `epochs` | 训练轮数 | 4 |
| `batch_size` | 批大小 | 16 |
| `lr` | 学习率 | 5e-5 |
| `dropout` | 分类头 Dropout | 0.3 |
| `threshold` | 标签命中概率阈值 | 0.65 |
| `pos_weight_clamp` | BCE 正样本权重上限 | 8.0 |
| `weight_decay` | AdamW 权重衰减 | 0.01 |
| `warmup_ratio` | 学习率预热比例 | 0.1 |
| `seed` | 随机种子（可复现） | 42 |
| `device` | 计算设备（留空自动选择） | 自动 |

设备选择规则：`cuda` 可用则用 GPU，否则自动回退 `cpu`，无需手动配置。

> **关于正负样本平衡（pos_weight）**：多标签任务中，标签数为 28 而一条评论通常只命中
> 1~3 个标签，正样本非常稀疏。若不处理，负样本梯度会淹没正样本信号，模型会退化成
> 「什么都不预测」（所有标签概率都被压到 0.5 阈值以下）。因此程序会根据训练集统计每个
> 标签的正负出现次数，自动计算 `pos_weight = 负样本数 / 正样本数`（裁剪到上限）传给
> `BCEWithLogitsLoss`，放大正样本梯度，这也是本任务能正常收敛的关键。

## 6. 运行结果（合成数据）

> 以下为合成数据上的演示结果（`config.py` 默认参数），
> 真实数据训练后指标以实际为准。

合成数据规模：训练 600 / 验证 100 / 测试 100，每条评论随机包含 1~3 个标签。

**训练过程（每轮验证集指标，阈值 0.65）：**

| 轮次 | 训练损失 | 验证 Macro-F1 | 验证 Exact-ACC |
|------|---------|--------------|---------------|
| 1 | 0.8841 | 0.5862 | 0.3000 |
| 2 | 0.5168 | 0.7688 | 0.4000 |
| 3 | 0.3602 | 0.8629 | 0.5500 |
| 4 | 0.2996 | 0.8788 | 0.6500 |

**测试集最终指标（阈值 0.65，最佳模型）：**

| 指标 | 数值 |
|------|------|
| Macro-F1 | 0.8940 |
| Micro-F1 | 0.9208 |
| Exact-ACC（完全一致） | 0.7400 |
| Precision（宏平均） | 0.8925 |
| Recall（宏平均） | 0.9144 |
| Hamming-Loss | 0.0114 |

**预测示例（真实推理效果）：**

```text
输入文本：客服推荐的尺码合适，发货也很快，下次还会光顾的
预测标签：发货快，尺码合适

输入文本：质量很差，客服也没人管，用几天就坏了
预测标签：客服差，容易坏

输入文本：鞋垫的胶凹凸不平，感觉不是正品
预测标签：疑似非正品，鞋垫不平
```

## 7. 常见问题

- **找不到数据文件？** 先运行 `python scripts/data_utils.py` 生成合成数据；
  或修改 `config.py` 中的 `train_file / val_file / test_file` 指向真实标注数据。
- **找不到标签词表？** 确认 `data/examples/category_tag_vocab.csv` 存在，
  程序还内置了同目录 `04_category_tag_vocab.csv` 作为备用。
- **加载模型时打印「UNEXPECTED」权重提示？** 正常现象：本地权重是 MLM 预训练格式，
  本项目只使用其 BERT 编码部分，提示可忽略。
- **Windows 终端中文乱码？** 仅影响控制台显示，文件均为 UTF-8 编码；
  可先执行 `chcp 65001` 切换到 UTF-8 代码页。
- **如何调整判定阈值？** 修改 `config.py` 的 `threshold`，推理时可查看各标签概率辅助判断。

## 8. 数据流向（与本项目的关系）

```text
data/examples/category_tag_vocab.csv  ──►  标签词表（多标签类别）
        │
        ▼
(真实) 标注数据 review_tags  ──►  训练/验证/测试
        │
        ▼
scripts/train.py 训练 ──►  checkpoints/best_model.pt
        │
        ▼
scripts/predict.py 推理 ──►  输出评论的多标签情感
```
