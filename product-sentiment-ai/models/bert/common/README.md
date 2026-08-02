# BERT 商品评论属性级情感分类（ABSA）

基于 `bert-base-chinese` 的商品评论**属性级情感分类**（Aspect-Based Sentiment Analysis）项目。
输入「商品类别 + 评论文本」，输出 8 种属性各自的**情感极性**（好 / 坏 / 未提及）。

```
输入：类别=图书音像   评论=纸张很好，印刷清晰，物流也很快
输出：质量:好  做工:好  物流:好  价格:未提及  服务:未提及 ...
```

- 属性：**质量 / 做工 / 价格 / 物流 / 服务 / 包装 / 描述 / 外观**（8 种）
- 极性：**好（正面）/ 坏（负面）/ 未提及**
- 建模：**16 维多标签二分类**（8 属性 × 2 极性），`BCEWithLogitsLoss` 训练
- 模型：BERT 编码 → [CLS] 向量 → Dropout → Linear(16)

---

## 目录

1. [功能特性](#1-功能特性)
2. [目录结构](#2-目录结构)
3. [环境依赖](#3-环境依赖)
4. [数据说明](#4-数据说明)
5. [快速开始](#5-快速开始)
6. [模型方法](#6-模型方法)
7. [配置说明](#7-配置说明)
8. [实验结果](#8-实验结果)
9. [API 服务](#9-api-服务)
10. [常见问题](#10-常见问题)
11. [数据流向](#11-数据流向)

---

## 1. 功能特性

- ✅ **属性级情感识别**：定位每个属性是好是坏，而非整句笼统褒贬
- ✅ **多标签联合建模**：一条评论可同时命中多个属性，不互斥
- ✅ **类别感知输入**：商品类别作为独立的 BERT 段（segment）输入，利用段编码区分
- ✅ **自动正负样本加权**：根据训练集统计自动计算 pos_weight，缓解正样本稀疏
- ✅ **逐属性阈值调优**：训练后在验证集上为每个属性搜索最优判定阈值
- ✅ **GPU/CPU 自适应**：有 GPU 用 GPU，无 GPU 自动回退 CPU
- ✅ **完整检查点**：保存完整 state_dict（含微调 BERT）+ 阈值 + 标签元信息，开箱即推理
- ✅ **API 服务**：内置 FastAPI 接口，供前端/后端调用

---

## 2. 目录结构

```
common/
├── bert-base-chinese/          # 预训练 BERT 权重（本地，无需联网）
├── data/
│   ├── data_pre/               # 原始数据（只读）：数据集最终版.csv、类别ID对照表.csv
│   ├── processed/              # 拆分后的 train/val/test.csv（由 data_utils.py 生成）
│   └── synthetic/              # 历史合成测试数据（早期验证用，可忽略）
├── checkpoints/                # 模型保存目录（best_model.pt / final_model.pt）
├── results/                    # 指标 JSON、日志、标签列表、测试报告
│   └── 测试结果报告.md          # 最近的实验结果报告
├── scripts/                    # 项目代码（全部代码）
│   ├── config.py               # 全局配置字典（超参数与路径集中管理）
│   ├── data_utils.py           # 原始数据读取 / 标签编码 / 分层拆分 / 加载
│   ├── dataset.py              # PyTorch Dataset 与 collate（类别+评论双段编码）
│   ├── model.py                # BERT + 分类头多标签模型
│   ├── train.py                # 训练主程序（含阈值调优与测试评估）
│   ├── predict.py              # 推理（单条 / 批量文件，可 import 复用）
│   └── api_server.py           # FastAPI 预测服务
└── README.md                   # 本文档
```

---

## 3. 环境依赖

推荐使用项目配置的 conda 环境（示例：`sentiment-plus`），关键依赖：

```
torch>=2.0
transformers>=4.30
pandas
scikit-learn
numpy
tqdm
fastapi
uvicorn
pydantic
```

验证环境：

```bash
python -c "import torch, transformers; print(torch.__version__, transformers.__version__)"
```

> **Windows 中文乱码**：仅控制台显示问题，文件均为 UTF-8。
> 运行前执行 `chcp 65001`，或在命令前加 `PYTHONIOENCODING=utf-8`。

---

## 4. 数据说明

### 4.1 原始数据格式（`data/data_pre/数据集最终版.csv`）

真实标注数据，每行一条评论，关键列：

| 列 | 说明 |
|----|------|
| `评论内容_clean` | 清洗后的评论文本（模型输入） |
| `类别` | JSON，如 `[{"类别": "图书音像", "类别ID": 0}]` |
| `attributes` | JSON，标注的属性极性，如 `[{"aspect": "价格", "polarity": 1}]` |
| `tokens_jieba` / `text_clean_jieba` | jieba 词级分词（备选列，未使用） |
| `tokens_char` / `text_clean_char` | 字级分词（保留，便于人工核对） |

> **为什么不用 jieba 分词列？** BERT-base-Chinese 分词器本身按「字」切分，
> 再额外 jieba 分词无增益还可能引入错误切分；故模型直接输入清洗文本。
> 预测新评论时也无需 jieba 依赖。

### 4.2 标签结构

8 属性 × 2 极性 = 16 个标签，`multi-hot` 编码，顺序固定：

- 前 8 位 = 各属性「好」：`质量好 做工好 价格好 物流好 服务好 包装好 描述好 外观好`
- 后 8 位 = 各属性「坏」：`质量坏 做工坏 价格坏 物流坏 服务坏 包装坏 描述坏 外观坏`

### 4.3 数据拆分

数据集只有一份，由程序按「商品类别」**分层抽样**自动拆分
（保证训练/验证/测试三类别的比例一致），比例 8:1:1。

```bash
# 一键拆分原始数据 -> data/processed/{train,val,test}.csv
python scripts/data_utils.py
```

---

## 5. 快速开始

### 5.1 数据准备（首次）

```bash
python scripts/data_utils.py
```

### 5.2 训练

```bash
# 使用默认配置训练（15 轮，早停 3，自动选择 GPU/CPU）
python scripts/train.py

# 覆盖部分超参数
python scripts/train.py --epochs 8 --batch_size 32 --lr 3e-5

# 强制 CPU
python scripts/train.py --device cpu

# 快速冒烟测试：仅用前 N 条样本验证流程
python scripts/train.py --subset 2000 --epochs 4
```

训练完成后自动产出：

- `checkpoints/best_model.pt`：验证集最优模型（完整 state_dict + 阈值 + 元信息）
- `results/test_metrics.json`：测试集指标
- `results/train_log.csv` / `results/train_run.log`：训练过程
- `results/labels.txt`：16 个标签名

### 5.3 推理（单条）

```bash
python scripts/predict.py --category 图书音像 --text "纸张很好，印刷清晰，物流也很快"
```

输出格式：

```
输入类别： 图书音像
输入评论： 纸张很好，印刷清晰，物流也很快
预测标签列表： ['做工好', '质量好', '物流好']

各属性明细：
  质量: 好 (好概率 0.960 / 坏概率 0.003)
  做工: 好 (好概率 0.941 / 坏概率 0.011)
  ...
```

### 5.4 推理（批量文件）

```bash
# CSV：自动识别「类别」列与「评论」列
python scripts/predict.py --input_file data/data_pre/xx.csv --output_file results/xx_result.csv

# TXT：每行一条评论，类别统一用 --category（默认「其他」）
python scripts/predict.py --input_file data/data_pre/sample.txt --output_file results/sample_result.csv
```

---

## 6. 模型方法

### 6.1 输入编码

评论与商品类别作为两个文本段输入，利用 BERT 段编码区分：

```
[CLS] 图书音像 [SEP] 纸张很好，印刷清晰... [SEP]
      段0=类别          段1=评论
```

### 6.2 模型结构

```
类别+评论 ──► BERT ──► [CLS]向量(768) ──► Dropout ──► Linear(16) ──► logits
```

参数量约 102M（BERT 骨干微调 + 16 维分类头）。

### 6.3 损失函数与正负样本平衡

多标签任务中正样本极其稀疏（多数标签正样本仅几十条），若不处理，
负样本梯度会淹没正样本信号，模型退化为「什么都不预测」。
因此程序自动计算 `pos_weight = 负样本数 / 正样本数`（裁剪上限 8.0）传给
`BCEWithLogitsLoss`，放大正样本梯度，是任务能正常收敛的关键。

### 6.4 阈值判定

训练结束后在**验证集**上为每个属性独立搜索「好/坏判定阈值」
（候选 0.30~0.80，共 36 组组合），使该属性好/坏/未提及三类宏平均 F1 最大。
阈值随检查点保存，推理时自动加载。

### 6.5 指标口径

| 指标 | 含义 |
|------|------|
| 整体属性准确率 | 所有「评论×8属性」单元预测正确的比例（含未提及） |
| 提及属性准确率 | 仅在**真实被提及**的属性单元上统计（核心指标） |
| 三类宏平均F1 | 每属性按 好/坏/未提及 三类的宏平均 F1，再对 8 属性平均 |

---

## 7. 配置说明（Config）

所有超参数集中在 `scripts/config.py` 的 `Config` 字典中，常用项：

| 键 | 含义 | 默认 |
|----|------|------|
| `model_name_or_path` | 预训练 BERT 本地目录 | `bert-base-chinese/` |
| `max_len` | 输入文本最大长度 | 64 |
| `epochs` | 训练轮数 | 15 |
| `batch_size` | 批大小 | 16 |
| `lr` | 学习率 | 3e-5 |
| `dropout` | 分类头 Dropout | 0.3 |
| `weight_decay` | AdamW 权重衰减 | 0.01 |
| `warmup_ratio` | 学习率线性预热比例 | 0.1 |
| `pos_weight_clamp` | BCE 正样本权重上限 | 8.0 |
| `early_stop_patience` | 早停轮数（验证指标不提升则提前结束） | 3 |
| `seed` | 随机种子（可复现） | 42 |
| `device` | 计算设备（留空自动选择） | 自动 |
| `split_ratios` | 训练/验证/测试拆分比例 | 8:1:1 |
| `threshold_grid` | 阈值搜索候选 | 0.3~0.8 |
| `default_threshold` | 未调优前的兜底阈值 | 0.50 |
| `api_host` / `api_port` | API 监听地址 / 端口 | 0.0.0.0 / 8010 |

设备选择：`cuda` 可用则用 GPU，否则自动回退 `cpu`。

---

## 8. 实验结果

### 8.1 快速验证实验（2000 条 · 4 轮 · CPU）

详细见 [`results/测试结果报告.md`](results/测试结果报告.md)，要点如下：

**训练过程（验证集）：**

| 轮次 | 训练损失 | 整体ACC | 提及ACC | 三类宏F1 |
|------|---------|---------|---------|----------|
| 1 | 0.5857 | 0.9030 | 0.7333 | 0.5415 |
| 2 | 0.2890 | 0.9298 | 0.8045 | 0.6908 |
| 3 | 0.1970 | 0.9420 | 0.8282 | 0.7399 |
| 4 | 0.1547 | 0.9496 | 0.8282 | **0.7602** |

**测试集最终指标：**

| 指标 | 数值 |
|------|------|
| 整体属性准确率 | 0.9580 |
| 提及属性准确率 | **0.7981** |
| 三类宏平均F1 | **0.7664** |
| 16标签 Micro F1 | 0.8321 |
| 16标签 Macro F1 | 0.6617 |

### 8.2 对比与结论

- 400 条冒烟测试 → 2000 条：三类宏F1 从 **0.44 → 0.77**，提及准确率 **0.48 → 0.80**
- 指标在第 4 轮仍在上升，尚未收敛，**数据量未饱和**
- 建议进行全量训练（11557 条 / 15 轮 / 早停），预计三类宏F1 可达 **0.80 以上**

---

## 9. API 服务

内置 FastAPI 服务，返回格式与后端 JeecgBoot 壳一致：

```json
{"success": true, "message": "操作成功", "code": 200, "result": {...}}
```

### 启动服务

```bash
python scripts/api_server.py                 # 默认 0.0.0.0:8010
python scripts/api_server.py --port 8011     # 覆盖端口
```

> 模型在第一次请求时惰性加载（首次调用慢几秒），后续复用。

### 接口列表

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/meta` | 返回支持的 类别 / 属性 / 标签 元信息 |
| POST | `/api/predict` | 单条预测：`{"category": "图书音像", "text": "…"}` |
| POST | `/api/predict_file` | 批量预测（上传 CSV/TXT），`?fmt=json` 可返回逐条 JSON |

### 调用示例

```bash
# 单条预测
curl -X POST http://localhost:8010/api/predict \
  -H "Content-Type: application/json" \
  -d '{"category": "图书音像", "text": "纸张很好，物流快"}'

# 批量预测（返回结果文件下载）
curl -X POST "http://localhost:8010/api/predict_file?category=%E5%9B%BE%E4%B9%A6%E9%9F%B3%E5%83%8F" \
  -F "file=@data/data_pre/sample.csv"
```

---

## 10. 常见问题

- **找不到数据文件？** 确认 `data/data_pre/数据集最终版.csv` 存在，
  再运行 `python scripts/data_utils.py` 生成拆分文件。
- **加载模型时提示「MLM 头权重未匹配」？** 正常现象：本地权重是 MLM 预训练格式，
  本项目只用其 BERT 编码部分，告警可忽略。
- **训练太慢？** 本机为 CPU。可减小 `epochs`，或用 `--subset` 快速验证流程；
  有条件建议 GPU。
- **Windows 终端中文乱码？** 执行 `chcp 65001` 或设 `PYTHONIOENCODING=utf-8`。
- **预测结果为空？** 该评论所有属性均未过阈值，判定为「未提及」；
  可查看各属性概率，必要时调低阈值。
- **为什么每个属性阈值不同？** 不同属性正负样本分布差异大，单一阈值效果差，
  故在验证集上逐属性搜索最优阈值并随模型保存。

---

## 11. 数据流向

```text
data/data_pre/数据集最终版.csv（真实标注，只读）
        │  data_utils.py 按类别分层拆分
        ▼
data/processed/{train,val,test}.csv（8:1:1）
        │  train.py 训练（BCE + pos_weight + 早停 + 阈值调优）
        ▼
checkpoints/best_model.pt（完整 state_dict + 阈值 + 元信息）
        │
        ├─► predict.py 单条/批量推理
        │
        └─► api_server.py（FastAPI）──► 前端 / 后端 / product_tags
```
