# 数据目录

```text
raw/train.csv                 # 队员原表拷贝（字段完全一致）
processed/train.csv           # 分层划分 80%
processed/val.csv             # 10%
processed/test.csv            # 10%
```

- **不**另存宽表 / 抽字段新表；训练时读原列：`类别`、`评论内容_clean`、`attributes`
- 用 `scripts/split_data.py` 生成
- 主用 `train.csv`；`attribute_labels.csv` 不必放入
