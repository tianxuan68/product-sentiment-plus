# 类目 BERT

- 原表：`data/raw/train.csv`（与队员字段一致）
- 划分：`data/processed/{train,val,test}.csv`（列不变，不另建宽表）
- JSON 属性用**英文 key**；CSV 里中文 aspect 经词表映射
- 依赖用仓库根目录 `requirements.txt`

## 脚本

| 文件 | 作用 |
|------|------|
| `split_data.py` | 拷贝原表并划分 train/val/test |
| `config.py` | 配置与方面词表 |
| `dataset.py` | 读 CSV → 宽表 Dataset |
| `model.py` | BERT + 多属性头 |
| `train.py` | 训练 |
| `evaluate.py` | 评估 |
| `predict_fun.py` | 推理 |
| `../api/app.py` | FastAPI 预测接口（在 `api/` 目录） |

## 准备数据

```powershell
cd models\bert\category\scripts
python split_data.py
```

## 两种训练方式

| 方式 | 命令 | 用途 |
|------|------|------|
| 多类目 | `python train.py` 或 `--category all` | 一次跑完所有品类；小样本冒烟 |
| 单类目 | `python train.py --category 服饰服装` | 专注一个品类；**看准确率用这个 + 全量** |

```powershell
# 多类目冒烟：每类随机 200（见 configs/default.yaml）
python train.py

# 单类目全量（推荐先验证效果）
python train.py --category 图书音像 --max_train_samples null --max_val_samples null

# 多类目全量（耗时长）
python train.py --category all --max_train_samples null --max_val_samples null

# 评估
python evaluate.py
python evaluate.py --category 图书音像

# 预测（text 原样返回；属性英文）
python predict_fun.py --category 服饰服装 --text "这件T恤面料很柔软，但版型偏大，颜色比图片暗"
```

小样本准确率低是正常的。要看真实效果请单类目全量（图书音像样本最多）。

### 格式

```json
{"category":"服饰服装","text":"...","size":null,"fabric":1,"color":0,"fit":0,"comfort":null,"warmth":null,"craftsmanship":null,"thickness":null}
```

预测输入只有 `category` + `text`；输出补全英文属性。只用 **`train.csv`** 即可。

## 预测 API（前端调用）

接口在 `api/`，训练脚本在 `scripts/`。

```powershell
cd models\bert\category\api
# 若缺少 uvicorn：pip install uvicorn
python app.py
# 或: uvicorn app:app --host 0.0.0.0 --port 8101
```

- 文档：http://127.0.0.1:8101/docs  
- `GET /health`  
- `GET /api/category/list` — 品类与属性、是否已有权重  
- `POST /api/category/predict` — 单条  
- `POST /api/category/predict/batch` — 批量  

单条请求 / 响应示例：

```json
// POST /api/category/predict
{"category":"服饰服装","text":"这件T恤面料很柔软，但版型偏大，颜色比图片暗"}

// 200
{"category":"服饰服装","text":"这件T恤面料很柔软，但版型偏大，颜色比图片暗","size":null,"fabric":1,"color":0,"fit":0,"comfort":null,"warmth":null,"craftsmanship":null,"thickness":null}
```

已开 CORS（`*`），前端可直接请求。
