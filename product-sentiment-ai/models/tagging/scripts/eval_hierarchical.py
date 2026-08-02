"""
案例:
    分层 BERT 评测：打印 precision / recall / F1，并抽测难句。

用法:
    python -m models.tagging.scripts.eval_hierarchical
    python -m models.tagging.scripts.eval_hierarchical --threshold 0.35
    python -m models.tagging.scripts.eval_hierarchical --no-per-label
"""

# 导包
import argparse
import json
import os
import sys

from sklearn.preprocessing import MultiLabelBinarizer
from torch.utils.data import DataLoader

from models.common.dataset.load_hierarchical_tags import load_hierarchical
from models.common.metrics.tune_thresholds import dict_to_threshold_array
from models.tagging.scripts.predict_hierarchical import load_hierarchical_bundle, predict_one
from models.tagging.scripts.train_hierarchical import HierDataset, eval_model, make_collate

_ANNOTATE_DIR = os.path.abspath("./data/scripts/annotate")
if _ANNOTATE_DIR not in sys.path:
    sys.path.insert(0, _ANNOTATE_DIR)

from tag_rules import category_tag_map, general_tag_names  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=None, help="全局阈值（无按标签配置时用）")
    parser.add_argument("--max-samples", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument(
        "--no-per-label",
        action="store_true",
        help="强制用全局阈值，忽略 hier_config 里的按标签阈值",
    )
    args = parser.parse_args()

    bundle = load_hierarchical_bundle()
    thr = args.threshold if args.threshold is not None else bundle["threshold"]
    thr = float(thr)

    gen_labels = general_tag_names()
    cat_map = category_tag_map()
    mlb_gen = MultiLabelBinarizer(classes=gen_labels)
    mlb_gen.fit([[]])
    cat_mlbs = {}
    for cat, labs in cat_map.items():
        mlb = MultiLabelBinarizer(classes=labs)
        mlb.fit([[]])
        cat_mlbs[cat] = mlb

    x_va, c_va, g_va, k_va, _ = load_hierarchical(
        "val", max_samples=args.max_samples, augment=False
    )
    loader = DataLoader(
        HierDataset(x_va, c_va, g_va, k_va),
        batch_size=args.batch_size,
        shuffle=False,
        collate_fn=make_collate(bundle["tok"], 128, mlb_gen, cat_mlbs),
    )

    gen_thr_vec = cat_thr_vec = None
    mode = "global"
    if (not args.no_per_label) and bundle.get("thresholds_general"):
        mode = "per-label"
        gen_thr_vec = dict_to_threshold_array(
            list(mlb_gen.classes_), bundle["thresholds_general"], default=thr
        )
        # 类目阈值向量在 eval_model 内按 pack['cat_names'] 对齐；先跑一遍拿 names
        gen_m, cat_m, pack = eval_model(
            bundle["model"],
            loader,
            bundle["device"],
            mlb_gen,
            cat_mlbs,
            thr,
            use_amp=False,
        )
        if pack["cat_names"] and bundle.get("thresholds_category"):
            cat_thr_vec = dict_to_threshold_array(
                pack["cat_names"], bundle["thresholds_category"], default=thr
            )
        gen_m, cat_m, _ = eval_model(
            bundle["model"],
            loader,
            bundle["device"],
            mlb_gen,
            cat_mlbs,
            thr,
            use_amp=False,
            gen_thr_vec=gen_thr_vec,
            cat_thr_vec=cat_thr_vec,
            collected=pack,
        )
    else:
        gen_m, cat_m, _ = eval_model(
            bundle["model"],
            loader,
            bundle["device"],
            mlb_gen,
            cat_mlbs,
            thr,
            use_amp=False,
        )

    print('-' * 50)
    print(f'分层 BERT 验证集指标  mode={mode}  thr={thr:.2f}  n={len(x_va)}')
    print('-' * 50)
    print(
        f'[通用头] Acc={gen_m.get("accuracy", 0):.4f}  '
        f'P={gen_m["precision_micro"]:.4f}  '
        f'R={gen_m["recall_micro"]:.4f}  F1={gen_m["f1_micro"]:.4f}  '
        f'macroF1={gen_m["f1_macro"]:.4f}'
    )
    print(
        f'[类目头] Acc={cat_m.get("accuracy", 0):.4f}  '
        f'P={cat_m.get("precision_micro", cat_m.get("precision", 0)):.4f}  '
        f'R={cat_m.get("recall_micro", cat_m.get("recall", 0)):.4f}  '
        f'F1={cat_m.get("f1_micro", 0):.4f}  '
        f'macroF1={cat_m.get("f1_macro", 0):.4f}'
    )
    score = 0.5 * (gen_m["f1_micro"] + float(cat_m.get("f1_micro") or 0))
    print(f'[综合] score=(gen_F1+cat_F1)/2 = {score:.4f}')

    out = {
        "mode": mode,
        "threshold": thr,
        "val_size": len(x_va),
        "general": {
            "accuracy": gen_m.get("accuracy"),
            "precision_micro": gen_m["precision_micro"],
            "recall_micro": gen_m["recall_micro"],
            "f1_micro": gen_m["f1_micro"],
            "f1_macro": gen_m["f1_macro"],
        },
        "category": {
            "accuracy": cat_m.get("accuracy"),
            "precision_micro": cat_m.get("precision_micro", cat_m.get("precision")),
            "recall_micro": cat_m.get("recall_micro", cat_m.get("recall")),
            "f1_micro": cat_m.get("f1_micro"),
            "f1_macro": cat_m.get("f1_macro"),
        },
        "score": score,
    }
    path = "./models/tagging/results/metrics_hierarchical_eval.json"
    os.makedirs("./models/tagging/results", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'已保存: {path}')

    print('-' * 50)
    print(f'难句抽测')
    print('-' * 50)
    cases = [
        ("质量很好，发货也挺快，包装有点破损", "美妆个护"),
        ("续航很久，屏幕清晰，质量不错", "手机/数码"),
        ("内容不错，很有干货，物流慢", "图书音像"),
        ("面料不错，款式好看，尺码合适", "服饰服装"),
    ]
    for text, cat in cases:
        tags = predict_one(bundle, text, cat)
        print(f'[{cat}] {text}')
        print(f'  -> {[t["tag"] for t in tags]}')


if __name__ == "__main__":
    main()
