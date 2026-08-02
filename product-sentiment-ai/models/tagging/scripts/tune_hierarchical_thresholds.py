"""
案例:
    不对模型重训，只在验证集上按标签重搜阈值并写回 hier_config.json。

用法:
    python -m models.tagging.scripts.tune_hierarchical_thresholds
    python -m models.tagging.scripts.tune_hierarchical_thresholds --default 0.40
"""

# 导包
import argparse
import json
import os

from sklearn.preprocessing import MultiLabelBinarizer
from torch.utils.data import DataLoader

from models.common.dataset.load_hierarchical_tags import load_hierarchical
from models.tagging.scripts.predict_hierarchical import load_hierarchical_bundle
from models.tagging.scripts.train_hierarchical import (
    HierDataset,
    collect_val_probs,
    eval_model,
    make_collate,
    tune_and_pack_thresholds,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ckpt", default="./models/tagging/model/bert_hierarchical")
    parser.add_argument("--default", type=float, default=0.40)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--max-samples", type=int, default=None)
    args = parser.parse_args()

    bundle = load_hierarchical_bundle(args.ckpt)
    gen_labels = bundle["general_labels"]
    cat_map = bundle["category_tag_map"]
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

    pack = collect_val_probs(
        bundle["model"], loader, bundle["device"], cat_mlbs, use_amp=False
    )
    gen_before, cat_before, _ = eval_model(
        bundle["model"],
        loader,
        bundle["device"],
        mlb_gen,
        cat_mlbs,
        bundle["threshold"],
        False,
        collected=pack,
    )
    print('-' * 50)
    print(f'调前(全局 thr={bundle["threshold"]:.2f})')
    print(
        f'  gen F1={gen_before["f1_micro"]:.4f} '
        f'P={gen_before["precision_micro"]:.4f} R={gen_before["recall_micro"]:.4f}'
    )
    print(f'  cat F1={cat_before.get("f1_micro", 0):.4f}')

    gen_dict, cat_dict, gen_vec, cat_vec = tune_and_pack_thresholds(
        pack, mlb_gen, default=args.default
    )
    gen_after, cat_after, _ = eval_model(
        bundle["model"],
        loader,
        bundle["device"],
        mlb_gen,
        cat_mlbs,
        args.default,
        False,
        gen_thr_vec=gen_vec,
        cat_thr_vec=cat_vec,
        collected=pack,
    )
    print('-' * 50)
    print(f'调后(按标签阈值)')
    print(
        f'  gen F1={gen_after["f1_micro"]:.4f} '
        f'P={gen_after["precision_micro"]:.4f} R={gen_after["recall_micro"]:.4f} '
        f'Acc={gen_after.get("accuracy", 0):.4f}'
    )
    print(
        f'  cat F1={cat_after.get("f1_micro", 0):.4f} '
        f'P={cat_after.get("precision_micro", 0):.4f} '
        f'R={cat_after.get("recall_micro", 0):.4f}'
    )

    cfg_path = os.path.join(args.ckpt, "hier_config.json")
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["thresholds_general"] = gen_dict
    cfg["thresholds_category"] = cat_dict
    cfg["threshold"] = args.default
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print(f'已写回: {cfg_path}')
    print(f'通用标签阈值样例: {list(gen_dict.items())[:6]}')


if __name__ == "__main__":
    main()
