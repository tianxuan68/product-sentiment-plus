# 类目 BERT 职责说明

## 数据

- 主数据：队员 **`train.csv`**（已够用，不必用 `attribute_labels.csv`）
- 项目内：`models/bert/category/data/raw/train.csv`
- 划分：`data/processed/{train,val,test}.csv`，**列与原表一致**
- 训练时内存转成英文属性 key；不落盘新表，保证和队员同一套表

## 预训练

`models/pretrained/bert-base-chinese/`（1.0 中文）

## 训练习惯

- 默认一次训**全部类目**（每类目各自一套属性头 / checkpoint）
- 小样本：`max_train_samples` = **每个类目随机抽 N 条**（不是文件前 N 行）
- 全量：把 `max_train_samples` / `max_val_samples` 设为 `~`

## 输入输出（英文属性）

预测输入：`{"category","text"}`  
输出：同 text + `size/fabric/color/...` 等英文 key，值为 `1/0/null`

## 前端 API

目录：`models/bert/category/api/app.py`  
启动：`cd api` 后 `python app.py`（端口 8101，文档 `/docs`）  
接口：`POST /api/category/predict`、`POST /api/category/predict/batch`、`GET /api/category/list`
