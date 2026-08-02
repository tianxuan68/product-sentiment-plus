"""
案例:
    分层标签规则：通用属性 + 类目属性。

大白话:
    质量/物流这类大家共用；面料/续航/内容只在对应类目生效。
"""

# 导包
import re
from typing import Optional

# 1. 通用属性（所有类目）
# (aspect, tag, polarity, patterns)
GENERAL_RULES: list[tuple[str, str, str, list[str]]] = [
    ("质量", "质量好", "positive", [
        r"质量好", r"品质好", r"质量不错", r"质量很棒", r"质量很好", r"质量挺好",
        r"质量也很好", r"质量也挺好", r"做工好", r"做工细致", r"做工精致",
    ]),
    ("质量", "质量差", "negative", [r"质量差", r"质量不好", r"品质差", r"做工差", r"做工粗糙", r"太差了", r"垃圾"]),
    ("物流", "发货快", "positive", [
        r"发货快", r"发货很快", r"发货挺快", r"发货也挺快", r"发货也很快",
        r"发货速度快", r"发货速度很快",
        r"物流快", r"物流很快", r"物流挺快", r"物流也挺快", r"物流也很快",
        r"快递快", r"快递很快", r"快递挺快", r"快递也挺快",
        r"送货快", r"送货很快", r"送货挺快", r"很快就到", r"隔天到", r"第二天到",
    ]),
    ("物流", "物流慢", "negative", [
        r"发货慢", r"发货很慢", r"发货挺慢", r"发货也挺慢",
        r"物流慢", r"物流很慢", r"物流挺慢", r"物流也挺慢",
        r"快递慢", r"快递很慢", r"等了好久", r"迟迟不到",
    ]),
    ("包装", "包装好", "positive", [r"包装好", r"包装不错", r"包装严实", r"包装完好", r"包装很好"]),
    ("包装", "包装差", "negative", [
        r"包装差", r"包装简陋", r"包装破", r"包装有点破", r"包装有点破损",
        r"破损", r"压坏", r"包装破损",
    ]),
    ("价格", "性价比高", "positive", [
        r"性价比高", r"性价比很好", r"很划算", r"超值", r"便宜又好", r"物美价廉", r"值得买",
    ]),
    ("价格", "价格贵", "negative", [r"价格贵", r"太贵", r"偏贵", r"不便宜", r"贵了"]),
    ("客服", "客服好", "positive", [r"客服好", r"客服不错", r"服务态度好", r"回复及时"]),
    ("客服", "客服差", "negative", [r"客服差", r"没人管", r"不回消息", r"态度差", r"售后差"]),
    # 忌用单字「放心」——太宽，银标噪声会带偏模型
    ("正品", "正品放心", "positive", [r"是正品", r"正品", r"正版", r"官方旗舰", r"官方店"]),
    ("正品", "疑似假货", "negative", [r"假货", r"假的", r"不是正品", r"盗版", r"山寨"]),
    ("外观", "外观好看", "positive", [r"外观好看", r"颜值高", r"很洋气", r"外形好看", r"样子好看", r"挺漂亮"]),
    ("外观", "外观一般", "negative", [r"外观一般", r"难看", r"不好看", r"外形丑"]),
    ("耐用", "很耐用", "positive", [r"很耐用", r"耐用", r"结实", r"耐用性好"]),
    ("耐用", "容易坏", "negative", [r"容易坏", r"坏了", r"用不了", r"故障", r"死机"]),
    ("推荐", "会回购", "positive", [r"会回购", r"回购", r"还会买", r"推荐购买", r"值得推荐"]),
    ("推荐", "不推荐", "negative", [r"不推荐", r"别买", r"踩坑", r"后悔买"]),
]

# 2. 类目属性：categories 列表决定哪些类目能打这些标签
# (categories, aspect, tag, polarity, patterns)
CATEGORY_RULES: list[tuple[list[str], str, str, str, list[str]]] = [
    # 图书
    (["图书音像"], "内容", "内容不错", "positive", [r"内容好", r"内容不错", r"写得很好", r"很有用", r"干货", r"受益"]),
    (["图书音像"], "内容", "内容一般", "negative", [r"内容空洞", r"没什么内容", r"太浅", r"浪费钱", r"不值"]),
    # 服饰鞋包
    (["服饰服装", "鞋类箱包", "运动户外"], "尺码", "尺码合适", "positive", [r"尺码合适", r"大小合适", r"合身"]),
    (["服饰服装", "鞋类箱包", "运动户外"], "尺码", "尺码不准", "negative", [r"尺码不准", r"偏小", r"偏大", r"建议买大", r"建议买小"]),
    (["服饰服装", "鞋类箱包", "运动户外"], "面料", "面料不错", "positive", [r"面料好", r"面料不错", r"料子好", r"布料好"]),
    (["服饰服装", "鞋类箱包", "运动户外"], "面料", "面料差", "negative", [r"面料差", r"料子差", r"布料差", r"廉价感"]),
    (["服饰服装", "鞋类箱包", "运动户外"], "款式", "款式好看", "positive", [r"款式好", r"款式好看", r"版型好", r"很百搭"]),
    (["服饰服装", "鞋类箱包", "运动户外"], "款式", "款式一般", "negative", [r"款式差", r"款式老气", r"版型差"]),
    # 数码电器
    (["手机/数码", "电脑/办公", "家用电器"], "续航", "续航久", "positive", [r"续航久", r"续航好", r"电池耐用"]),
    (["手机/数码", "电脑/办公", "家用电器"], "续航", "续航差", "negative", [r"续航差", r"不耐用", r"费电"]),
    (["手机/数码", "电脑/办公"], "屏幕", "屏幕清晰", "positive", [r"屏幕清晰", r"屏幕好", r"显示清楚", r"分辨率高"]),
    (["手机/数码", "电脑/办公"], "屏幕", "屏幕差", "negative", [r"屏幕差", r"显示模糊", r"漏光", r"坏点"]),
    # 美妆 / 食品
    (["美妆个护", "食品/保健"], "味道", "味道不错", "positive", [r"味道好", r"味道不错", r"好吃", r"好喝", r"香"]),
    (["美妆个护", "食品/保健"], "味道", "味道一般", "negative", [r"味道差", r"不好吃", r"难喝", r"怪怪的"]),
    (["食品/保健"], "新鲜", "很新鲜", "positive", [r"新鲜", r"很新"]),
]

# 兼容旧代码：扁平成 TAG_RULES
TAG_RULES: list[tuple[str, str, str, list[str]]] = [
    (aspect, tag, polarity, patterns) for aspect, tag, polarity, patterns in GENERAL_RULES
] + [
    (aspect, tag, polarity, patterns)
    for _, aspect, tag, polarity, patterns in CATEGORY_RULES
]


def general_tag_names() -> list[str]:
    return [tag for _, tag, _, _ in GENERAL_RULES]


def all_tag_names() -> list[str]:
    """全部标签名（通用 + 类目），供扁平多标签训练兼容。"""
    names = general_tag_names()
    for tags in category_tag_map().values():
        for t in tags:
            if t not in names:
                names.append(t)
    return names


def category_tag_map() -> dict[str, list[str]]:
    """类目 → 该类目专属标签列表（有序去重）。"""
    out: dict[str, list[str]] = {}
    for cats, _, tag, _, _ in CATEGORY_RULES:
        for c in cats:
            out.setdefault(c, [])
            if tag not in out[c]:
                out[c].append(tag)
    return out


def all_category_names_with_tags() -> list[str]:
    return sorted(category_tag_map().keys())


def tag_meta_map() -> dict[str, dict]:
    meta = {}
    for aspect, tag, polarity, _ in GENERAL_RULES:
        meta[tag] = {"aspect": aspect, "polarity": polarity, "scope": "general"}
    for cats, aspect, tag, polarity, _ in CATEGORY_RULES:
        meta[tag] = {
            "aspect": aspect,
            "polarity": polarity,
            "scope": "category",
            "categories": cats,
        }
    return meta


def compile_general_rules():
    return [
        (aspect, tag, polarity, [re.compile(p) for p in patterns])
        for aspect, tag, polarity, patterns in GENERAL_RULES
    ]


def compile_category_rules():
    return [
        (set(cats), aspect, tag, polarity, [re.compile(p) for p in patterns])
        for cats, aspect, tag, polarity, patterns in CATEGORY_RULES
    ]


def compile_rules():
    """兼容旧接口：编译全部规则（不做类目过滤）。"""
    return [
        (aspect, tag, polarity, [re.compile(p) for p in patterns])
        for aspect, tag, polarity, patterns in TAG_RULES
    ]


def extract_tags(
    text: str,
    compiled=None,
    category: Optional[str] = None,
) -> list[tuple[str, str, str]]:
    """
    抽标签。
    - 通用规则始终生效
    - 类目规则：传了 category 才按类目过滤；没传则全开（兼容旧批量脚本）
    """
    hits = []
    seen = set()

    for aspect, tag, polarity, regs in compile_general_rules():
        if any(r.search(text) for r in regs) and tag not in seen:
            seen.add(tag)
            hits.append((aspect, tag, polarity))

    for cats, aspect, tag, polarity, regs in compile_category_rules():
        if category is not None and category not in cats:
            continue
        if any(r.search(text) for r in regs) and tag not in seen:
            seen.add(tag)
            hits.append((aspect, tag, polarity))

    # 兼容：若外部传了旧版 compiled，仍可用（不推荐）
    if compiled is not None and category is None and not hits:
        for aspect, tag, polarity, regs in compiled:
            if any(r.search(text) for r in regs) and tag not in seen:
                seen.add(tag)
                hits.append((aspect, tag, polarity))
    return hits


def build_vocab_rows() -> list[dict]:
    rows = []
    for aspect, tag, polarity, _ in GENERAL_RULES:
        rows.append(
            {"category": "*", "aspect": aspect, "tag": tag, "polarity": polarity, "scope": "general"}
        )
    for cats, aspect, tag, polarity, _ in CATEGORY_RULES:
        for c in cats:
            rows.append(
                {
                    "category": c,
                    "aspect": aspect,
                    "tag": tag,
                    "polarity": polarity,
                    "scope": "category",
                }
            )
    return rows


def _evidence_pattern_map() -> dict[str, list[re.Pattern]]:
    """标签 → 文本证据正则（模型预测落地用，防空穴来风）。"""
    out: dict[str, list[re.Pattern]] = {}
    for _, tag, _, patterns in GENERAL_RULES:
        out[tag] = [re.compile(p) for p in patterns]
    for _, _, tag, _, patterns in CATEGORY_RULES:
        out.setdefault(tag, [])
        out[tag].extend(re.compile(p) for p in patterns)
    return out


_EVIDENCE_MAP: dict[str, list[re.Pattern]] | None = None


def tag_has_text_evidence(text: str, tag: str) -> bool:
    """
    原文是否能撑住该固定标签。
    大白话: 模型说「会回购」但评论压根没提回购 → 扔掉。
    """
    global _EVIDENCE_MAP
    if _EVIDENCE_MAP is None:
        _EVIDENCE_MAP = _evidence_pattern_map()
    regs = _EVIDENCE_MAP.get(tag)
    if not regs:
        # 无规则的标签：至少标签名或前两字出现在原文
        return tag in text or (len(tag) >= 2 and tag[:2] in text)
    return any(r.search(text or "") for r in regs)
