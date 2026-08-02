# 预训练模型放置说明

类目 BERT 使用 **1.0 中文预训练**：

```text
models/pretrained/bert-base-chinese/
```

## 从哪里拷

1.0 项目常见路径：

```text
D:\heima\goods_category\sentiment-ai\artifacts\pretrained\bert-base-chinese\
```

把该目录**整包内容**拷到上面的 `bert-base-chinese/` 下（不要多套一层）。

## 目录内应有

- `config.json`
- `pytorch_model.bin` 或 `model.safetensors`
- `vocab.txt`
- tokenizer 相关文件

配置键：`model_name: models/pretrained/bert-base-chinese`
