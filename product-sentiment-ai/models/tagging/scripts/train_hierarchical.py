"""
案例:
    分层多标签训练：共享 BERT + 通用头 + 类目头。

用法（在 product-sentiment-ai 目录下）:
    python -m models.tagging.scripts.train_hierarchical --refresh-silver --epochs 3
    python -m models.tagging.scripts.train_hierarchical --epochs 2 --batch-size 24
    python -m models.tagging.scripts.train_hierarchical --max-samples 8000 --epochs 1
"""

# 导包
import argparse
import json
import os
import sys

import numpy as np
import torch
import torch.nn as nn
from sklearn.preprocessing import MultiLabelBinarizer
from torch.utils.data import DataLoader, Dataset
from transformers import AutoTokenizer, get_linear_schedule_with_warmup

from models.common.dataset.load_hierarchical_tags import load_hierarchical
from models.common.metrics.evaluate import save_metrics
from models.common.metrics.evaluate_multilabel import compute_multilabel_metrics
from models.common.metrics.tune_thresholds import (
    apply_thresholds,
    score_with_thresholds,
    thresholds_to_dict,
    tune_label_thresholds,
)
from models.common.pretrained_path import resolve_bert_model
from models.tagging.hierarchical_model import HierarchicalTagBERT

_ANNOTATE_DIR = os.path.abspath("./data/scripts/annotate")
if _ANNOTATE_DIR not in sys.path:
    sys.path.insert(0, _ANNOTATE_DIR)

from tag_rules import category_tag_map, general_tag_names, tag_meta_map  # noqa: E402


class HierDataset(Dataset):
    def __init__(self, texts, categories, y_gen, y_cat):
        self.texts = texts
        self.categories = categories
        self.y_gen = y_gen
        self.y_cat = y_cat

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        return self.texts[idx], self.categories[idx], self.y_gen[idx], self.y_cat[idx]


def make_collate(tokenizer, max_len, mlb_gen, cat_mlbs):
    def collate(batch):
        texts, cats, gens, cates = zip(*batch)
        enc = tokenizer(
            list(texts),
            truncation=True,
            padding=True,
            max_length=max_len,
            return_tensors="pt",
        )
        y_gen = torch.tensor(mlb_gen.transform(gens), dtype=torch.float32)
        # 各类目标签：按样本各自 binarize
        y_cat_bin = []
        for cat, labs in zip(cats, cates):
            mlb = cat_mlbs.get(cat)
            if mlb is None:
                y_cat_bin.append(None)
            else:
                y_cat_bin.append(torch.tensor(mlb.transform([labs])[0], dtype=torch.float32))
        enc["categories"] = list(cats)
        enc["y_gen"] = y_gen
        enc["y_cat"] = y_cat_bin
        return enc

    return collate


def _all_category_names(cat_mlbs):
    names = []
    for mlb in cat_mlbs.values():
        for n in mlb.classes_:
            if n not in names:
                names.append(n)
    return names


@torch.no_grad()
def collect_val_probs(model, loader, device, cat_mlbs, use_amp):
    """收集验证集概率，供评测 / 按标签搜阈值。"""
    model.eval()
    gen_probs, gen_golds = [], []
    cat_prob_rows, cat_gold_rows = [], []
    all_cat_names = _all_category_names(cat_mlbs)
    name_to_idx = {n: i for i, n in enumerate(all_cat_names)}
    amp_device = "cuda" if device.type == "cuda" else "cpu"

    for batch in loader:
        cats = batch.pop("categories")
        y_gen = batch.pop("y_gen")
        y_cat = batch.pop("y_cat")
        batch = {k: v.to(device) for k, v in batch.items()}
        with torch.amp.autocast(amp_device, enabled=use_amp):
            gen_logits, cat_logits = model.forward_both(
                batch["input_ids"], batch["attention_mask"], cats
            )
        gen_probs.append(torch.sigmoid(gen_logits.float()).cpu().numpy())
        gen_golds.append(y_gen.numpy())

        for i, cat in enumerate(cats):
            gold = y_cat[i]
            logits = cat_logits[i]
            mlb = cat_mlbs.get(cat)
            if mlb is None or logits is None or gold is None:
                continue
            p = torch.sigmoid(logits.float()).cpu().numpy()[0]
            row_p = np.zeros(len(all_cat_names), dtype=np.float64)
            row_g = np.zeros(len(all_cat_names), dtype=np.int32)
            for j, name in enumerate(mlb.classes_):
                idx = name_to_idx[name]
                row_p[idx] = float(p[j])
                row_g[idx] = int(gold[j] >= 0.5)
            cat_prob_rows.append(row_p)
            cat_gold_rows.append(row_g)

    out = {
        "gen_probs": np.concatenate(gen_probs, axis=0),
        "gen_golds": np.concatenate(gen_golds, axis=0),
        "cat_names": all_cat_names,
    }
    if cat_prob_rows:
        out["cat_probs"] = np.stack(cat_prob_rows, axis=0)
        out["cat_golds"] = np.stack(cat_gold_rows, axis=0)
    else:
        out["cat_probs"] = np.zeros((0, len(all_cat_names)))
        out["cat_golds"] = np.zeros((0, len(all_cat_names)), dtype=np.int32)
    return out


def eval_model(
    model,
    loader,
    device,
    mlb_gen,
    cat_mlbs,
    thr,
    use_amp,
    gen_thr_vec=None,
    cat_thr_vec=None,
    collected=None,
):
    """
    thr: 全局标量阈值（兼容旧逻辑）
    gen_thr_vec / cat_thr_vec: 按标签阈值；有则优先
    """
    pack = collected or collect_val_probs(model, loader, device, cat_mlbs, use_amp)
    gen_probs, gen_golds = pack["gen_probs"], pack["gen_golds"]
    if gen_thr_vec is not None:
        gen_pred = apply_thresholds(gen_probs, gen_thr_vec)
    else:
        gen_pred = apply_thresholds(gen_probs, thr)
    gen_metrics = compute_multilabel_metrics(
        gen_golds, gen_pred, label_names=list(mlb_gen.classes_)
    )

    cat_names = pack["cat_names"]
    if len(pack["cat_golds"]):
        if cat_thr_vec is not None:
            cat_pred = apply_thresholds(pack["cat_probs"], cat_thr_vec)
        else:
            cat_pred = apply_thresholds(pack["cat_probs"], thr)
        cat_metrics = compute_multilabel_metrics(
            pack["cat_golds"], cat_pred, label_names=cat_names
        )
    else:
        cat_metrics = {
            "f1_micro": 0.0,
            "f1_macro": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "accuracy": 0.0,
        }
    return gen_metrics, cat_metrics, pack


def build_category_pos_weights(c_tr, k_tr, cat_mlbs, device, max_w=12.0):
    """各类目头各自算 pos_weight，缓解长尾标签。"""
    losses = {}
    for cat, mlb in cat_mlbs.items():
        rows = [labs for c, labs in zip(c_tr, k_tr) if c == cat]
        if not rows:
            losses[cat] = nn.BCEWithLogitsLoss()
            continue
        mat = mlb.transform(rows)
        pos = mat.sum(axis=0).astype(np.float64)
        neg = mat.shape[0] - pos
        pw = np.clip(np.where(pos > 0, neg / np.maximum(pos, 1.0), 1.0), 1.0, max_w)
        losses[cat] = nn.BCEWithLogitsLoss(
            pos_weight=torch.tensor(pw, dtype=torch.float32, device=device)
        )
    return losses


def tune_and_pack_thresholds(pack, mlb_gen, default=0.40):
    gen_vec = tune_label_thresholds(
        pack["gen_probs"], pack["gen_golds"], default=default
    )
    gen_dict = thresholds_to_dict(list(mlb_gen.classes_), gen_vec)
    cat_dict = {}
    cat_vec = None
    if len(pack["cat_golds"]):
        cat_vec = tune_label_thresholds(
            pack["cat_probs"], pack["cat_golds"], default=default
        )
        cat_dict = thresholds_to_dict(pack["cat_names"], cat_vec)
    gen_f1 = score_with_thresholds(pack["gen_probs"], pack["gen_golds"], gen_vec)
    cat_f1 = (
        score_with_thresholds(pack["cat_probs"], pack["cat_golds"], cat_vec)
        if cat_vec is not None
        else 0.0
    )
    print(f'按标签搜阈值后: gen_f1={gen_f1:.4f} cat_f1={cat_f1:.4f}')
    return gen_dict, cat_dict, gen_vec, cat_vec


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=24)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--max-len", type=int, default=128)
    parser.add_argument("--max-samples", type=int, default=None)
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.40,
        help="训练过程中粗评用的全局阈值；最终会按标签重搜",
    )
    parser.add_argument("--refresh-silver", action="store_true", help="先重跑规则银标")
    parser.add_argument("--no-fp16", action="store_true")
    parser.add_argument(
        "--no-tune-thresholds",
        action="store_true",
        help="关闭按标签搜阈值（默认开启）",
    )
    args = parser.parse_args()

    if args.refresh_silver:
        import importlib.util

        path = os.path.abspath("./data/scripts/annotate/dynamic_tagging.py")
        spec = importlib.util.spec_from_file_location("dynamic_tagging", path)
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        print(f'刷新分层银标（规则词表，供固定标签训练）...')
        mod.run(min_count=1, top_k=20, mode="rules")

    ckpt_dir = "./models/tagging/model/bert_hierarchical"
    result = "./models/tagging/results/metrics_hierarchical.json"
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    use_amp = (not args.no_fp16) and device.type == "cuda"
    print('-' * 50)
    print(f'分层 BERT 多标签训练')
    print('-' * 50)
    print(f'device={device} fp16={use_amp} tune_thresholds={not args.no_tune_thresholds}')

    gen_labels = general_tag_names()
    cat_map = category_tag_map()
    print(f'通用标签={len(gen_labels)} 有专属头的类目={list(cat_map.keys())}')

    x_tr, c_tr, g_tr, k_tr, _ = load_hierarchical(
        "train", max_samples=args.max_samples, augment=True
    )
    val_max = max(args.max_samples // 5, 400) if args.max_samples else None
    x_va, c_va, g_va, k_va, _ = load_hierarchical(
        "val", max_samples=val_max, augment=False
    )

    mlb_gen = MultiLabelBinarizer(classes=gen_labels)
    mlb_gen.fit([[]])
    cat_mlbs = {}
    for cat, labs in cat_map.items():
        mlb = MultiLabelBinarizer(classes=labs)
        mlb.fit([[]])
        cat_mlbs[cat] = mlb

    model_name = resolve_bert_model()
    tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=True)
    model = HierarchicalTagBERT(
        model_name,
        n_general=len(gen_labels),
        category_dims={c: len(labs) for c, labs in cat_map.items()},
    ).to(device)

    train_loader = DataLoader(
        HierDataset(x_tr, c_tr, g_tr, k_tr),
        batch_size=args.batch_size,
        shuffle=True,
        collate_fn=make_collate(tokenizer, args.max_len, mlb_gen, cat_mlbs),
    )
    val_loader = DataLoader(
        HierDataset(x_va, c_va, g_va, k_va),
        batch_size=args.batch_size,
        shuffle=False,
        collate_fn=make_collate(tokenizer, args.max_len, mlb_gen, cat_mlbs),
    )

    # 通用头 / 类目头 pos_weight（抬长尾召回、压高频误报）
    y_gen_mat = mlb_gen.transform(g_tr)
    pos = y_gen_mat.sum(axis=0)
    neg = y_gen_mat.shape[0] - pos
    pw = np.clip(np.where(pos > 0, neg / np.maximum(pos, 1), 1.0), 1.0, 12.0)
    bce_gen = nn.BCEWithLogitsLoss(
        pos_weight=torch.tensor(pw, dtype=torch.float32, device=device)
    )
    bce_cat_map = build_category_pos_weights(c_tr, k_tr, cat_mlbs, device)

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    total_steps = max(len(train_loader) * args.epochs, 1)
    sched = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=int(0.1 * total_steps), num_training_steps=total_steps
    )
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    amp_device = "cuda" if device.type == "cuda" else "cpu"

    best_score = -1.0
    for epoch in range(1, args.epochs + 1):
        model.train()
        losses = []
        for batch in train_loader:
            cats = batch.pop("categories")
            y_gen = batch.pop("y_gen").to(device)
            y_cat = batch.pop("y_cat")
            batch = {k: v.to(device) for k, v in batch.items()}
            optimizer.zero_grad(set_to_none=True)
            with torch.amp.autocast(amp_device, enabled=use_amp):
                gen_logits, cat_logits = model.forward_both(
                    batch["input_ids"], batch["attention_mask"], cats
                )
                loss = bce_gen(gen_logits, y_gen)
                cat_terms = []
                for i, logits in enumerate(cat_logits):
                    if logits is None or y_cat[i] is None:
                        continue
                    crit = bce_cat_map.get(cats[i]) or nn.BCEWithLogitsLoss()
                    cat_terms.append(crit(logits, y_cat[i].unsqueeze(0).to(device)))
                if cat_terms:
                    loss = loss + 0.8 * torch.stack(cat_terms).mean()
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(optimizer)
            scaler.update()
            sched.step()
            losses.append(float(loss.item()))

        gen_m, cat_m, pack = eval_model(
            model, val_loader, device, mlb_gen, cat_mlbs, args.threshold, use_amp
        )
        score = 0.6 * gen_m["f1_micro"] + 0.4 * cat_m["f1_micro"]
        print(
            f'epoch={epoch} loss={np.mean(losses):.4f} '
            f'gen_f1={gen_m["f1_micro"]:.4f}(P={gen_m["precision_micro"]:.3f}/'
            f'R={gen_m["recall_micro"]:.3f}) '
            f'cat_f1={cat_m["f1_micro"]:.4f} score={score:.4f}'
        )

        if score > best_score:
            best_score = score
            os.makedirs(ckpt_dir, exist_ok=True)
            torch.save(model.state_dict(), os.path.join(ckpt_dir, "pytorch_model.bin"))
            tokenizer.save_pretrained(ckpt_dir)
            model.encoder.config.save_pretrained(ckpt_dir)

            # 选模用全局阈值分；落盘时再按标签搜阈值写进配置
            gen_thr_dict, cat_thr_dict = {}, {}
            metrics_for_save = gen_m
            cat_metrics_for_save = cat_m
            tuned_score = score
            if not args.no_tune_thresholds:
                gen_thr_dict, cat_thr_dict, gen_vec, cat_vec = tune_and_pack_thresholds(
                    pack, mlb_gen, default=args.threshold
                )
                metrics_for_save, cat_metrics_for_save, _ = eval_model(
                    model,
                    val_loader,
                    device,
                    mlb_gen,
                    cat_mlbs,
                    args.threshold,
                    use_amp,
                    gen_thr_vec=gen_vec,
                    cat_thr_vec=cat_vec,
                    collected=pack,
                )
                tuned_score = (
                    0.6 * metrics_for_save["f1_micro"]
                    + 0.4 * cat_metrics_for_save["f1_micro"]
                )
                print(
                    f'  调阈值后 gen_f1={metrics_for_save["f1_micro"]:.4f} '
                    f'(P={metrics_for_save["precision_micro"]:.3f}/'
                    f'R={metrics_for_save["recall_micro"]:.3f}) '
                    f'cat_f1={cat_metrics_for_save["f1_micro"]:.4f} '
                    f'score={tuned_score:.4f}'
                )

            meta = {
                "general_labels": gen_labels,
                "category_tag_map": cat_map,
                "threshold": args.threshold,
                "thresholds_general": gen_thr_dict,
                "thresholds_category": cat_thr_dict,
                # 存相对路径，避免 Windows 绝对路径在 Linux 部署机失效
                "base_model": (
                    os.path.relpath(model_name, start=os.getcwd()).replace("\\", "/")
                    if os.path.isabs(model_name)
                    else str(model_name).replace("\\", "/")
                ),
                "tag_meta": tag_meta_map(),
            }
            with open(os.path.join(ckpt_dir, "hier_config.json"), "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
            save_metrics(
                {
                    **metrics_for_save,
                    "f1": metrics_for_save["f1_micro"],
                    "precision": metrics_for_save["precision_micro"],
                    "recall": metrics_for_save["recall_micro"],
                    "accuracy": metrics_for_save.get("accuracy", 0.0),
                    "report": metrics_for_save.get("report", "")
                    + "\n\n[category]\n"
                    + cat_metrics_for_save.get("report", str(cat_metrics_for_save)),
                },
                result,
                {
                    "model": "tagging_bert_hierarchical",
                    "train_size": len(x_tr),
                    "threshold": args.threshold,
                    "thresholds_general": gen_thr_dict,
                    "thresholds_category": cat_thr_dict,
                    "gen_f1_micro": metrics_for_save["f1_micro"],
                    "cat_f1_micro": cat_metrics_for_save["f1_micro"],
                    "gen_precision": metrics_for_save["precision_micro"],
                    "gen_recall": metrics_for_save["recall_micro"],
                    "score_global_thr": score,
                    "score": tuned_score,
                    "epoch": epoch,
                },
            )
            print(f'已保存: {ckpt_dir}')

    print(f'最佳选模分(全局阈值)={best_score:.4f}')


if __name__ == "__main__":
    main()
