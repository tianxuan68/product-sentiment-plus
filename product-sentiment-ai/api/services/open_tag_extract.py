"""
案例:
    开放打标：不从固定标签表里选，直接从评论里抽出观点短语。

大白话:
    「质量很好 / 发货也挺快」本身就是标签，不用事先写死词表。
"""

# 导包
import re

import jieba.posseg as pseg

_POS_NEG = {
    "好", "棒", "快", "赞", "值", "香", "新", "清", "稳", "爽", "满意", "推荐",
    "不错", "很好", "挺好", "喜欢", "给力", "惊喜", "靠谱",
}
_NEG_NEG = {
    "差", "慢", "烂", "坏", "假", "丑", "贵", "坑", "后悔", "垃圾", "破损",
    "不好", "不行", "一般", "难受", "失望", "投诉", "别买", "不值",
}


def split_clauses(text: str) -> list[str]:
    parts = re.split(r"[，。！？；、,\.!\?;~\s]+", (text or "").strip())
    return [p.strip() for p in parts if len(p.strip()) >= 2]


def _polarity(phrase: str) -> str:
    if any(w in phrase for w in _NEG_NEG):
        return "negative"
    if any(w in phrase for w in _POS_NEG):
        return "positive"
    return "neutral"


def _aspect_guess(phrase: str) -> str:
    """从短语里捞名词当方面；优先较长实义名词。"""
    cands = []
    for w, flag in pseg.cut(phrase):
        if flag.startswith("n") and len(w) >= 1 and w not in {"有点", "一点", "地方"}:
            cands.append(w)
    if not cands:
        return ""
    return max(cands, key=len)


def _is_weak_clause(phrase: str) -> bool:
    # 太短、纯标点、无汉字
    if len(phrase) < 2:
        return True
    if not re.search(r"[\u4e00-\u9fff]", phrase):
        return True
    # 纯称呼/无信息
    if phrase in {"好的", "收到", "嗯", "哦", "谢谢", "感谢"}:
        return True
    return False


def extract_open_tags(text: str) -> list[dict]:
    """
    开放抽取：
    1) 优先：分句后整句观点当标签（最贴原文，不死标签）
    2) 补充：jieba 抽「名/形」局部短语，避免长句信息糊成一团
    """
    text = (text or "").strip()
    hits = []
    seen = set()

    def add(tag, aspect="", score=1.0, source="open_clause"):
        tag = re.sub(r"\s+", "", tag)
        if not tag or tag in seen or _is_weak_clause(tag):
            return
        seen.add(tag)
        hits.append(
            {
                "aspect": aspect or _aspect_guess(tag),
                "tag": tag,
                "polarity": _polarity(tag),
                "score": float(score),
                "source": source,
                "scope": "open",
            }
        )

    clauses = split_clauses(text)
    for c in clauses:
        add(c, score=1.0, source="open_clause")

    # 局部：连续 名词/动名 + 形容词/副词+形
    words = list(pseg.cut(text))
    i = 0
    while i < len(words):
        w, f = words[i]
        # 名 + 形 / 名 + 副 + 形
        if f.startswith("n") and i + 1 < len(words):
            w2, f2 = words[i + 1]
            if f2.startswith("a") or f2 in {"v"}:
                add(w + w2, aspect=w, score=0.9, source="open_phrase")
                i += 2
                continue
            if f2.startswith("d") and i + 2 < len(words):
                w3, f3 = words[i + 2]
                if f3.startswith("a") or f3.startswith("v"):
                    add(w + w2 + w3, aspect=w, score=0.9, source="open_phrase")
                    i += 3
                    continue
        i += 1

    # 分句已覆盖时，去掉被分句包含的短短语，减少重复
    clause_tags = {h["tag"] for h in hits if h["source"] == "open_clause"}
    filtered = []
    for h in hits:
        if h["source"] == "open_phrase" and any(h["tag"] in c for c in clause_tags):
            continue
        filtered.append(h)

    # 若分句成功，以分句为主（更干净）
    if any(h["source"] == "open_clause" for h in filtered):
        filtered = [h for h in filtered if h["source"] == "open_clause"]

    filtered.sort(key=lambda x: x["score"], reverse=True)
    return filtered
