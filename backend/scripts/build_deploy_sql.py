"""
从 AI 处理后的 reviews.csv 抽样，生成/刷新唯一部署 SQL：sql/jeecgboot-slim.sql

用法（在 backend 目录）:
  python -m scripts.build_deploy_sql
  python -m scripts.build_deploy_sql --per-category 25
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "sql" / "jeecgboot-slim.sql"
REVIEWS_CSV = ROOT.parent / "product-sentiment-ai" / "data" / "processed" / "reviews.csv"
VOCAB_CSV = ROOT.parent / "product-sentiment-ai" / "data" / "vocab" / "category_tag_vocab.csv"

ADMIN_ID = "e9ca23d68d884d4ebb19d07889727dae"
ADMIN_HASH = "cb362cfeefbf3d8d"  # admin / 123456
ADMIN_SALT = "RCGTeGiH"

CATEGORY_MAP = {
    "图书音像": ("cat001", "books", 1),
    "电脑/办公": ("cat002", "computer", 2),
    "手机/数码": ("cat003", "digital", 3),
    "美妆个护": ("cat004", "beauty", 4),
    "家用电器": ("cat005", "appliance", 5),
    "家居生活": ("cat006", "home", 6),
    "其他": ("cat007", "other", 7),
    "母婴/玩具": ("cat008", "baby", 8),
    "家具/家装/建材": ("cat009", "furnish", 9),
    "钟表/首饰/眼镜/礼品": ("cat010", "jewelry", 10),
    "食品/保健": ("cat011", "food", 11),
    "鞋类箱包": ("cat012", "shoes", 12),
    "运动户外": ("cat013", "sports", 13),
    "服饰服装": ("cat014", "apparel", 14),
    "机票/充值/票务/虚拟": ("cat015", "virtual", 15),
}

SERVICE_WORDS = ["物流", "发货", "快递", "配送", "包装", "客服", "售后", "退货", "换货", "送货"]


def sql_str(value: object) -> str:
    if value is None:
        return "NULL"
    text = str(value).replace("\\", "\\\\").replace("'", "''")
    text = text.replace("\r", " ").replace("\n", " ").strip()
    return f"'{text}'"


def sql_num(value: object, default: str = "NULL") -> str:
    if value is None or value == "":
        return default
    try:
        return str(float(value) if "." in str(value) else int(float(value)))
    except Exception:
        return default


def clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:800]


def product_id_of(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return "prod_unknown"
    digest = hashlib.md5(raw.encode("utf-8")).hexdigest()[:16]
    return f"p_{digest}"


def review_id_of(raw: str, idx: int, content: str = "") -> str:
    # 带序号，避免同源 review_id 冲突
    seed = f"{raw or 'row'}|{idx}|{(content or '')[:40]}"
    digest = hashlib.md5(seed.encode("utf-8")).hexdigest()[:16]
    return f"r_{digest}"


def ts_to_dt(ts: str) -> str:
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "2026-01-01 12:00:00"


def pick_keywords(text: str, vocab_tags: list[str]) -> list[str]:
    hits = [w for w in SERVICE_WORDS if w in text]
    for tag in vocab_tags:
        if tag and tag in text and tag not in hits:
            hits.append(tag)
        if len(hits) >= 5:
            break
    return hits[:5]


def load_vocab_tags() -> list[str]:
    if not VOCAB_CSV.exists():
        return []
    tags = []
    with VOCAB_CSV.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            tag = (row.get("tag") or "").strip()
            if tag:
                tags.append(tag)
    return tags


def load_reviews(per_category: int = 0) -> tuple[list[dict], dict[str, dict]]:
    """
    从 reviews.csv 加载评价。
    per_category <= 0：全量；>0：每类目最多 N 条。
    """
    if not REVIEWS_CSV.exists():
        raise FileNotFoundError(f"找不到数据集: {REVIEWS_CSV}")

    take_all = per_category <= 0
    buckets: dict[str, int] = defaultdict(int)
    vocab_tags = load_vocab_tags()
    reviews: list[dict] = []
    products: dict[str, dict] = {}
    seen_review_ids: set[str] = set()

    with REVIEWS_CSV.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cat = (row.get("category") or "").strip()
            if cat not in CATEGORY_MAP:
                continue
            if not take_all and buckets[cat] >= per_category:
                continue
            content = clean_text(row.get("sentence") or row.get("content") or "")
            if len(content) < 6:
                continue

            cat_id, _, _ = CATEGORY_MAP[cat]
            pid_raw = (row.get("product_id") or "").strip()
            pname = clean_text(row.get("product_name") or pid_raw or "未命名商品")[:120]
            pid = product_id_of(pid_raw or pname)
            if pid not in products:
                products[pid] = {
                    "id": pid,
                    "name": pname,
                    "category_id": cat_id,
                    "sku": (pid_raw or pid)[:64],
                }

            sent_raw = str(row.get("sentiment") or "").strip()
            try:
                rating = float(row.get("rating") or 0)
            except Exception:
                rating = 0
            if sent_raw in {"1", "positive"}:
                sentiment = "positive"
            elif sent_raw in {"0", "negative"}:
                sentiment = "negative"
            elif rating >= 4:
                sentiment = "positive"
            elif 0 < rating <= 2:
                sentiment = "negative"
            else:
                sentiment = "neutral"
            score = int(min(99, max(50, round((rating or 3) * 18))))
            rid = review_id_of(row.get("review_id") or "", len(reviews), content)
            if rid in seen_review_ids:
                rid = review_id_of(row.get("review_id") or "", len(reviews), content + str(len(reviews)))
            seen_review_ids.add(rid)
            reviews.append(
                {
                    "id": rid,
                    "product_id": pid,
                    "product_name": pname,
                    "category_id": cat_id,
                    "category_name": cat,
                    "content": content,
                    "sentiment": sentiment,
                    "score": score,
                    "keywords": pick_keywords(content, vocab_tags),
                    "create_time": ts_to_dt(row.get("timestamp") or ""),
                    "username": f"user_{(row.get('user_id') or '0').split('.')[0][-6:]}",
                }
            )
            buckets[cat] += 1

    return reviews, products


def keyword_rows() -> list[tuple]:
    """返回 (id, word, aspect, polarity, sort_no, category_id, category_name)。空类目=通用。"""
    rows = []
    seen = set()  # (word, category_id or "")
    for i, word in enumerate(SERVICE_WORDS, start=1):
        aspect = "服务" if word in {"客服", "售后"} else "物流"
        rows.append((f"kw_{i:03d}", word, aspect, "any", i, None, None))
        seen.add((word, ""))
    if VOCAB_CSV.exists():
        # utf-8-sig：去掉 Excel/导出常见的 BOM，避免首列变成 \ufeffcategory
        with VOCAB_CSV.open(encoding="utf-8-sig") as f:
            for j, row in enumerate(csv.DictReader(f), start=1):
                word = (row.get("tag") or "").strip()
                aspect = (row.get("aspect") or "其他").strip()
                polarity = (row.get("polarity") or "any").strip() or "any"
                cat_raw = (row.get("category") or "*").strip() or "*"
                if not word:
                    continue
                if cat_raw in ("*", "general", "通用"):
                    cid, cname = None, None
                else:
                    meta = CATEGORY_MAP.get(cat_raw)
                    if not meta:
                        continue
                    cid, cname = meta[0], cat_raw
                key = (word, cid or "")
                if key in seen:
                    continue
                seen.add(key)
                rows.append((f"kw_v{j:03d}", word, aspect, polarity, 100 + j, cid, cname))
    return rows


def _chunked(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def write_sql(out: Path, per_category: int = 0, batch_size: int = 200) -> dict:
    """流式写出唯一部署 SQL（默认全量数据集）。"""
    print("loading reviews.csv ...")
    reviews, products = load_reviews(per_category)
    keywords = keyword_rows()
    mode = "全量" if per_category <= 0 else f"每类目≤{per_category}"
    print(f"loaded reviews={len(reviews)} products={len(products)} keywords={len(keywords)} ({mode})")

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as fp:
        def w(*parts: str):
            fp.write("\n".join(parts))
            fp.write("\n")

        w(
            "-- =============================================================================",
            "-- Sentiment-Plus 全量数据库初始化（唯一部署入口）",
            "-- =============================================================================",
            "-- 包含：系统权限 + 业务表 + reviews.csv 数据集",
            "--",
            "-- 用法:",
            "--   mysql -u root -p --max-allowed-packet=512M < sql/jeecgboot-slim.sql",
            "--   或 python -m scripts.init_slim_db",
            "--",
            "-- 默认账号: admin / 123456",
            f"-- 评价: {len(reviews)} 条（{mode}） / 商品 {len(products)} 个 / 关键词 {len(keywords)}",
            "-- =============================================================================",
            "",
            "CREATE DATABASE IF NOT EXISTS `jeecg-boot` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;",
            "USE `jeecg-boot`;",
            "",
            "SET NAMES utf8mb4;",
            "SET FOREIGN_KEY_CHECKS = 0;",
            "",
            "DROP TABLE IF EXISTS `biz_causal_result`;",
            "DROP TABLE IF EXISTS `biz_sentiment_query`;",
            "DROP TABLE IF EXISTS `biz_keyword`;",
            "DROP TABLE IF EXISTS `biz_product`;",
            "DROP TABLE IF EXISTS `biz_category`;",
            "DROP TABLE IF EXISTS `sys_cache`;",
            "DROP TABLE IF EXISTS `sys_third_app_config`;",
            "DROP TABLE IF EXISTS `sys_third_account`;",
            "DROP TABLE IF EXISTS `sys_role_permission`;",
            "DROP TABLE IF EXISTS `sys_user_role`;",
            "DROP TABLE IF EXISTS `sys_user_depart`;",
            "DROP TABLE IF EXISTS `sys_dict_item`;",
            "DROP TABLE IF EXISTS `sys_dict`;",
            "DROP TABLE IF EXISTS `sys_permission`;",
            "DROP TABLE IF EXISTS `sys_depart`;",
            "DROP TABLE IF EXISTS `sys_role`;",
            "DROP TABLE IF EXISTS `sys_user`;",
            "",
            SCHEMA_SQL.strip(),
            "",
            "-- =============================================================================",
            "-- 初始数据",
            "-- =============================================================================",
            "",
            "INSERT INTO `sys_user` (`id`,`username`,`realname`,`password`,`salt`,`status`,`del_flag`,`org_code`,`create_time`) VALUES",
            f"('{ADMIN_ID}','admin','管理员','{ADMIN_HASH}','{ADMIN_SALT}',1,0,'A01A03','2019-06-21 17:54:10');",
            "",
            "INSERT INTO `sys_role` (`id`,`role_name`,`role_code`,`description`,`create_time`) VALUES",
            "('f6817f48af4fb3af11b9e8bf182f618b','管理员','admin','系统管理员','2020-12-21 18:03:39');",
            "",
            "INSERT INTO `sys_user_role` (`id`,`user_id`,`role_id`) VALUES",
            f"('1996175712356261890','{ADMIN_ID}','f6817f48af4fb3af11b9e8bf182f618b');",
            "",
            "INSERT INTO `sys_depart` (`id`,`parent_id`,`depart_name`,`depart_order`,`org_category`,`org_type`,`org_code`,`status`,`del_flag`,`tenant_id`,`iz_leaf`,`create_time`) VALUES",
            "('c6d7cb4deeac411cb3384b1b31278596','','系统根组织',0,'1','1','A01','1','0',0,0,'2019-02-11 14:21:51'),",
            "('4f1765520d6346f9bd9c79e2479e5b12','c6d7cb4deeac411cb3384b1b31278596','研发部',1,'2','2','A01A03','1','0',0,1,'2019-02-20 17:15:34');",
            "",
            "INSERT INTO `sys_user_depart` (`id`,`user_id`,`dep_id`) VALUES",
            f"('1996175712356261891','{ADMIN_ID}','4f1765520d6346f9bd9c79e2479e5b12');",
            "",
            MENU_SQL.strip(),
            "",
            DICT_SQL.strip(),
            "",
        )

        cat_values = [
            f"({sql_str(cid)},'',{sql_str(name)},{sql_str(code)},{sql_str('/' + cid + '/')},1,{sort_no},1,1,0,'admin','2026-08-03 00:00:00')"
            for name, (cid, code, sort_no) in CATEGORY_MAP.items()
        ]
        w(
            "INSERT INTO `biz_category` (`id`,`parent_id`,`name`,`code`,`path`,`level`,`sort_no`,`is_leaf`,`status`,`del_flag`,`create_by`,`create_time`) VALUES",
            ",\n".join(cat_values) + ";",
            "",
        )

        prod_header = (
            "INSERT INTO `biz_product` (`id`,`name`,`category_id`,`brand`,`sku`,`price`,`original_price`,`currency`,"
            "`rating`,`stock`,`unit`,`status`,`description`,`del_flag`,`create_by`,`create_time`) VALUES"
        )
        prod_list = list(products.values())
        for chunk in _chunked(prod_list, batch_size):
            values = []
            for p in chunk:
                values.append(
                    "("
                    + ",".join(
                        [
                            sql_str(p["id"]),
                            sql_str(p["name"]),
                            sql_str(p["category_id"]),
                            sql_str("Dataset"),
                            sql_str(p["sku"]),
                            "99.00",
                            "129.00",
                            sql_str("CNY"),
                            "4.2",
                            "100",
                            sql_str("件"),
                            "1",
                            sql_str("来自评论数据集"),
                            "0",
                            sql_str("admin"),
                            sql_str("2026-08-03 10:00:00"),
                        ]
                    )
                    + ")"
                )
            w(prod_header, ",\n".join(values) + ";", "")

        rev_header = (
            "INSERT INTO `biz_sentiment_query` (`id`,`user_id`,`username`,`product_id`,`product_name`,"
            "`category_id`,`category_name`,`content`,`sentiment`,`score`,`summary`,`keywords`,`create_time`) VALUES"
        )
        done = 0
        for chunk in _chunked(reviews, batch_size):
            values = []
            for r in chunk:
                kw = json.dumps(r["keywords"], ensure_ascii=False)
                values.append(
                    "("
                    + ",".join(
                        [
                            sql_str(r["id"]),
                            sql_str(ADMIN_ID),
                            sql_str(r["username"]),
                            sql_str(r["product_id"]),
                            sql_str(r["product_name"]),
                            sql_str(r["category_id"]),
                            sql_str(r["category_name"]),
                            sql_str(r["content"]),
                            sql_str(r["sentiment"]),
                            str(r["score"]),
                            sql_str(f"数据集导入·{r['category_name']}"),
                            sql_str(kw),
                            sql_str(r["create_time"]),
                        ]
                    )
                    + ")"
                )
            w(rev_header, ",\n".join(values) + ";", "")
            done += len(chunk)
            if done % 5000 == 0 or done == len(reviews):
                print(f"  wrote reviews {done}/{len(reviews)}")

        kw_values = [
            f"({sql_str(kid)},{sql_str(word)},{sql_str(aspect)},{sql_str(cid)},{sql_str(cname)},{sql_str(polarity)},NULL,2,1,{sort_no},NULL,0,'admin','2026-08-03 12:00:00')"
            for kid, word, aspect, polarity, sort_no, cid, cname in keywords
        ]
        if kw_values:
            w(
                "INSERT INTO `biz_keyword` (`id`,`word`,`aspect`,`category_id`,`category_name`,`polarity`,`alias`,`weight`,`status`,`sort_no`,`remark`,`del_flag`,`create_by`,`create_time`) VALUES",
                ",\n".join(kw_values) + ";",
                "",
            )

        w(
            "SET FOREIGN_KEY_CHECKS = 1;",
            "",
            f"SELECT 'jeecgboot-slim 初始化完成' AS message, {len(reviews)} AS reviews, {len(products)} AS products, {len(CATEGORY_MAP)} AS categories;",
            "",
        )

    return {"reviews": len(reviews), "products": len(products), "keywords": len(keywords), "bytes": out.stat().st_size}


SCHEMA_SQL = r"""
CREATE TABLE `sys_cache` (
  `cache_key` varchar(128) NOT NULL,
  `cache_value` varchar(512) DEFAULT NULL,
  `expire_time` datetime DEFAULT NULL,
  PRIMARY KEY (`cache_key`),
  KEY `idx_expire` (`expire_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='临时缓存（短信验证码/扫码登录）';

CREATE TABLE `sys_user` (
  `id` varchar(32) NOT NULL,
  `username` varchar(100) DEFAULT NULL,
  `realname` varchar(100) DEFAULT NULL,
  `password` varchar(255) DEFAULT NULL,
  `salt` varchar(45) DEFAULT NULL,
  `avatar` varchar(255) DEFAULT NULL,
  `birthday` date DEFAULT NULL,
  `sex` tinyint(1) DEFAULT NULL,
  `email` varchar(45) DEFAULT NULL,
  `phone` varchar(45) DEFAULT NULL,
  `org_code` varchar(64) DEFAULT NULL,
  `status` tinyint(1) DEFAULT NULL,
  `del_flag` tinyint(1) DEFAULT NULL,
  `work_no` varchar(100) DEFAULT NULL,
  `login_tenant_id` int DEFAULT NULL,
  `create_by` varchar(32) DEFAULT NULL,
  `create_time` datetime DEFAULT NULL,
  `update_by` varchar(32) DEFAULT NULL,
  `update_time` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_user_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户';

CREATE TABLE `sys_role` (
  `id` varchar(32) NOT NULL,
  `role_name` varchar(200) DEFAULT NULL,
  `role_code` varchar(100) NOT NULL,
  `description` varchar(255) DEFAULT NULL,
  `tenant_id` int DEFAULT 0,
  `create_by` varchar(32) DEFAULT NULL,
  `create_time` datetime DEFAULT NULL,
  `update_by` varchar(32) DEFAULT NULL,
  `update_time` datetime DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色';

CREATE TABLE `sys_user_role` (
  `id` varchar(32) NOT NULL,
  `user_id` varchar(32) DEFAULT NULL,
  `role_id` varchar(32) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_sur_user` (`user_id`),
  KEY `idx_sur_role` (`role_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户角色';

CREATE TABLE `sys_permission` (
  `id` varchar(32) NOT NULL,
  `parent_id` varchar(32) DEFAULT NULL,
  `name` varchar(100) DEFAULT NULL,
  `url` varchar(255) DEFAULT NULL,
  `component` varchar(255) DEFAULT NULL,
  `is_route` tinyint(1) DEFAULT 1,
  `component_name` varchar(100) DEFAULT NULL,
  `redirect` varchar(255) DEFAULT NULL,
  `menu_type` int DEFAULT NULL,
  `perms` varchar(255) DEFAULT NULL,
  `perms_type` varchar(10) DEFAULT '0',
  `sort_no` double(8,2) DEFAULT NULL,
  `always_show` tinyint(1) DEFAULT NULL,
  `icon` varchar(100) DEFAULT NULL,
  `is_leaf` tinyint(1) DEFAULT NULL,
  `keep_alive` tinyint(1) DEFAULT NULL,
  `hidden` tinyint(1) DEFAULT 0,
  `hide_tab` tinyint(1) DEFAULT NULL,
  `description` varchar(255) DEFAULT NULL,
  `create_by` varchar(32) DEFAULT NULL,
  `create_time` datetime DEFAULT NULL,
  `update_by` varchar(32) DEFAULT NULL,
  `update_time` datetime DEFAULT NULL,
  `del_flag` tinyint(1) DEFAULT 0,
  `rule_flag` tinyint(1) DEFAULT 0,
  `status` varchar(2) DEFAULT NULL,
  `internal_or_external` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='菜单权限';

CREATE TABLE `sys_role_permission` (
  `id` varchar(32) NOT NULL,
  `role_id` varchar(32) DEFAULT NULL,
  `permission_id` varchar(32) DEFAULT NULL,
  `data_rule_ids` varchar(1000) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色菜单';

CREATE TABLE `sys_depart` (
  `id` varchar(32) NOT NULL,
  `parent_id` varchar(32) DEFAULT NULL,
  `depart_name` varchar(100) NOT NULL,
  `depart_order` int DEFAULT 0,
  `org_category` varchar(10) DEFAULT NULL,
  `org_type` varchar(10) DEFAULT NULL,
  `org_code` varchar(64) DEFAULT NULL,
  `status` varchar(1) DEFAULT NULL,
  `del_flag` varchar(1) DEFAULT NULL,
  `tenant_id` int DEFAULT 0,
  `iz_leaf` tinyint(1) DEFAULT 1,
  `create_by` varchar(32) DEFAULT NULL,
  `create_time` datetime DEFAULT NULL,
  `update_by` varchar(32) DEFAULT NULL,
  `update_time` datetime DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='组织机构';

CREATE TABLE `sys_user_depart` (
  `id` varchar(32) NOT NULL,
  `user_id` varchar(32) DEFAULT NULL,
  `dep_id` varchar(32) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户部门';

CREATE TABLE `sys_dict` (
  `id` varchar(32) NOT NULL,
  `dict_name` varchar(100) NOT NULL,
  `dict_code` varchar(100) NOT NULL,
  `description` varchar(255) DEFAULT NULL,
  `del_flag` int DEFAULT NULL,
  `create_by` varchar(32) DEFAULT NULL,
  `create_time` datetime DEFAULT NULL,
  `update_by` varchar(32) DEFAULT NULL,
  `update_time` datetime DEFAULT NULL,
  `type` int(1) unsigned DEFAULT 0,
  `tenant_id` int DEFAULT 0,
  `low_app_id` varchar(32) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_sd_dict_code` (`dict_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='字典';

CREATE TABLE `sys_dict_item` (
  `id` varchar(32) NOT NULL,
  `dict_id` varchar(32) DEFAULT NULL,
  `item_text` varchar(100) NOT NULL,
  `item_value` varchar(100) NOT NULL,
  `item_color` varchar(10) DEFAULT NULL,
  `description` varchar(255) DEFAULT NULL,
  `sort_order` int DEFAULT NULL,
  `status` int DEFAULT NULL,
  `create_by` varchar(32) DEFAULT NULL,
  `create_time` datetime DEFAULT NULL,
  `update_by` varchar(32) DEFAULT NULL,
  `update_time` datetime DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='字典项';

CREATE TABLE `sys_third_account` (
  `id` varchar(32) NOT NULL,
  `sys_user_id` varchar(32) DEFAULT NULL,
  `avatar` varchar(255) DEFAULT NULL,
  `status` tinyint(1) DEFAULT NULL,
  `del_flag` tinyint(1) DEFAULT NULL,
  `realname` varchar(100) DEFAULT NULL,
  `third_user_uuid` varchar(100) DEFAULT NULL,
  `third_user_id` varchar(100) DEFAULT NULL,
  `third_type` varchar(50) DEFAULT NULL,
  `create_by` varchar(32) DEFAULT NULL,
  `create_time` datetime DEFAULT NULL,
  `update_by` varchar(32) DEFAULT NULL,
  `update_time` datetime DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='第三方账号';

CREATE TABLE `sys_third_app_config` (
  `id` varchar(32) NOT NULL,
  `tenant_id` int DEFAULT NULL,
  `agent_id` varchar(100) DEFAULT NULL,
  `client_id` varchar(200) DEFAULT NULL,
  `client_secret` varchar(255) DEFAULT NULL,
  `third_type` varchar(50) DEFAULT NULL,
  `status` int DEFAULT 1,
  `create_by` varchar(32) DEFAULT NULL,
  `create_time` datetime DEFAULT NULL,
  `update_by` varchar(32) DEFAULT NULL,
  `update_time` datetime DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='第三方应用配置';

CREATE TABLE `biz_category` (
  `id` varchar(32) NOT NULL,
  `parent_id` varchar(32) DEFAULT '' COMMENT '父类目ID，空串为根',
  `name` varchar(100) NOT NULL COMMENT '类目名称',
  `code` varchar(64) DEFAULT NULL COMMENT '类目编码',
  `path` varchar(512) DEFAULT NULL COMMENT '物化路径',
  `level` int DEFAULT 1,
  `sort_no` int DEFAULT 0,
  `icon` varchar(255) DEFAULT NULL,
  `description` varchar(500) DEFAULT NULL,
  `is_leaf` tinyint(1) DEFAULT 1,
  `status` tinyint(1) DEFAULT 1,
  `del_flag` tinyint(1) DEFAULT 0,
  `create_by` varchar(32) DEFAULT NULL,
  `create_time` datetime DEFAULT NULL,
  `update_by` varchar(32) DEFAULT NULL,
  `update_time` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_biz_cat_parent` (`parent_id`),
  KEY `idx_biz_cat_code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品类目';

CREATE TABLE `biz_product` (
  `id` varchar(32) NOT NULL,
  `name` varchar(200) NOT NULL,
  `category_id` varchar(32) DEFAULT NULL,
  `brand` varchar(100) DEFAULT NULL,
  `sku` varchar(64) DEFAULT NULL,
  `price` decimal(12,2) DEFAULT NULL,
  `original_price` decimal(12,2) DEFAULT NULL,
  `currency` varchar(8) DEFAULT 'CNY',
  `cover_url` varchar(500) DEFAULT NULL,
  `rating` decimal(3,1) DEFAULT NULL,
  `stock` int DEFAULT 0,
  `unit` varchar(20) DEFAULT NULL,
  `status` tinyint(1) DEFAULT 1,
  `description` text,
  `note` varchar(1000) DEFAULT NULL,
  `del_flag` tinyint(1) DEFAULT 0,
  `create_by` varchar(32) DEFAULT NULL,
  `create_time` datetime DEFAULT NULL,
  `update_by` varchar(32) DEFAULT NULL,
  `update_time` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_biz_prod_cat` (`category_id`),
  KEY `idx_biz_prod_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品';

CREATE TABLE `biz_sentiment_query` (
  `id` varchar(32) NOT NULL,
  `user_id` varchar(32) DEFAULT NULL,
  `username` varchar(100) DEFAULT NULL,
  `product_id` varchar(32) DEFAULT NULL,
  `product_name` varchar(200) DEFAULT NULL,
  `category_id` varchar(32) DEFAULT NULL,
  `category_name` varchar(100) DEFAULT NULL,
  `content` text NOT NULL,
  `cover_url` varchar(500) DEFAULT NULL COMMENT '评价配图',
  `sentiment` varchar(20) DEFAULT NULL,
  `score` int DEFAULT NULL,
  `summary` text,
  `keywords` varchar(1000) DEFAULT NULL,
  `create_time` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_biz_sq_user` (`user_id`),
  KEY `idx_biz_sq_product` (`product_id`),
  KEY `idx_biz_sq_time` (`create_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='评价/情感记录';

CREATE TABLE `biz_keyword` (
  `id` varchar(32) NOT NULL,
  `word` varchar(100) NOT NULL,
  `aspect` varchar(64) DEFAULT NULL,
  `category_id` varchar(32) DEFAULT NULL,
  `category_name` varchar(100) DEFAULT NULL,
  `polarity` varchar(20) DEFAULT 'any',
  `alias` varchar(500) DEFAULT NULL,
  `weight` int DEFAULT 1,
  `status` tinyint(1) DEFAULT 1,
  `sort_no` int DEFAULT 0,
  `remark` varchar(500) DEFAULT NULL,
  `del_flag` tinyint(1) DEFAULT 0,
  `create_by` varchar(32) DEFAULT NULL,
  `create_time` datetime DEFAULT NULL,
  `update_by` varchar(32) DEFAULT NULL,
  `update_time` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_biz_kw_word` (`word`),
  KEY `idx_biz_kw_aspect` (`aspect`),
  KEY `idx_biz_kw_category` (`category_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='方面关键词词典（空类目=通用）';

CREATE TABLE `biz_causal_result` (
  `id` varchar(32) NOT NULL,
  `category_id` varchar(32) DEFAULT NULL,
  `category_name` varchar(100) NOT NULL,
  `sample_size` int DEFAULT 0,
  `treatment_rate` decimal(10,4) DEFAULT NULL,
  `outcome_rate` decimal(10,4) DEFAULT NULL,
  `ate` decimal(10,4) DEFAULT NULL,
  `ate_text` varchar(500) DEFAULT NULL,
  `treated_positive_rate` decimal(10,4) DEFAULT NULL,
  `control_positive_rate` decimal(10,4) DEFAULT NULL,
  `table_json` varchar(1000) DEFAULT NULL,
  `explanation` varchar(1000) DEFAULT NULL,
  `source` varchar(20) DEFAULT 'ai',
  `del_flag` tinyint(1) DEFAULT 0,
  `create_by` varchar(32) DEFAULT NULL,
  `create_time` datetime DEFAULT NULL,
  `update_by` varchar(32) DEFAULT NULL,
  `update_time` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_biz_causal_cat` (`category_name`),
  KEY `idx_biz_causal_time` (`update_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='按类目因果分析结果';
"""

MENU_SQL = r"""
INSERT INTO `sys_permission` (`id`,`parent_id`,`name`,`url`,`component`,`is_route`,`redirect`,`menu_type`,`sort_no`,`icon`,`is_leaf`,`keep_alive`,`hidden`,`del_flag`,`status`) VALUES
('d7d6e2e4e2934f2c9385a623fd98c6f3','','系统管理','/isystem','layouts/RouteView',1,'/system/user',0,9.00,'ant-design:setting',0,0,0,0,'1'),
('3f915b2769fc80648e92d04e84ca059d','d7d6e2e4e2934f2c9385a623fd98c6f3','用户管理','/system/user','system/user/index',1,NULL,1,1.00,'ant-design:user',0,1,0,0,'1'),
('190c2b43bec6a5f7a4194a85db67d96a','d7d6e2e4e2934f2c9385a623fd98c6f3','角色管理','/system/role','system/role/index',1,NULL,1,2.00,'ant-design:solution',0,1,0,0,'1'),
('1170592628746878978','d7d6e2e4e2934f2c9385a623fd98c6f3','菜单管理','/system/menu','system/menu/index',1,NULL,1,3.00,'ant-design:menu-fold-outlined',0,0,0,0,'1'),
('45c966826eeff4c99b8f8ebfe74511fc','d7d6e2e4e2934f2c9385a623fd98c6f3','部门管理','/system/depart','system/depart/index',1,NULL,1,4.00,'ant-design:team',0,0,0,0,'1'),
('1438782851980210178','d7d6e2e4e2934f2c9385a623fd98c6f3','数据字典','/system/dict','system/dict/index',1,NULL,1,5.00,'ant-design:hdd-twotone',0,0,0,0,'1'),
('biz_pm','','商品管理','/product','layouts/RouteView',1,'/product/info',0,2.00,'ant-design:shopping',0,0,0,0,'1'),
('biz_pm_info','biz_pm','商品信息','/product/info','product/info/index',1,NULL,1,1.00,'ant-design:profile',1,0,0,0,'1'),
('biz_pm_cat','biz_pm','类目管理','/product/category','product/category/index',1,NULL,1,2.00,'ant-design:apartment',1,0,0,0,'1'),
('biz_sa','','评论分析','/sentiment','layouts/RouteView',1,'/sentiment/review',0,3.00,'ant-design:comment',0,0,0,0,'1'),
('biz_sa_review','biz_sa','评价管理','/sentiment/review','sentiment/review/index',1,NULL,1,1.00,'ant-design:file-text',1,0,0,0,'1'),
('biz_sa_keyword','biz_sa','关键词管理','/sentiment/keyword','sentiment/keyword/index',1,NULL,1,2.00,'ant-design:tags',1,0,0,0,'1'),
('biz_sa_board','biz_sa','评价看板','/sentiment/dashboard','sentiment/dashboard/index',1,NULL,1,3.00,'ant-design:bar-chart',1,0,0,0,'1'),
('biz_sa_causal','biz_sa','因果分析','/sentiment/causal','sentiment/causal/index',1,NULL,1,4.00,'ant-design:node-index',1,0,0,0,'1');

INSERT INTO `sys_permission` (`id`,`parent_id`,`name`,`url`,`component`,`menu_type`,`perms`,`sort_no`,`is_leaf`,`del_flag`,`status`) VALUES
('1214462306546319362','3f915b2769fc80648e92d04e84ca059d','新增用户','','',2,'system:user:add',1.00,1,0,'1'),
('1214376304951664642','3f915b2769fc80648e92d04e84ca059d','用户编辑','','',2,'system:user:edit',2.00,1,0,'1'),
('1214376304951664643','3f915b2769fc80648e92d04e84ca059d','用户删除','','',2,'system:user:delete',3.00,1,0,'1'),
('1214376304951664644','190c2b43bec6a5f7a4194a85db67d96a','角色授权','','',2,'system:role:auth',1.00,1,0,'1');

INSERT INTO `sys_role_permission` (`id`,`role_id`,`permission_id`) VALUES
('rp003','f6817f48af4fb3af11b9e8bf182f618b','d7d6e2e4e2934f2c9385a623fd98c6f3'),
('rp004','f6817f48af4fb3af11b9e8bf182f618b','3f915b2769fc80648e92d04e84ca059d'),
('rp005','f6817f48af4fb3af11b9e8bf182f618b','190c2b43bec6a5f7a4194a85db67d96a'),
('rp006','f6817f48af4fb3af11b9e8bf182f618b','1170592628746878978'),
('rp007','f6817f48af4fb3af11b9e8bf182f618b','45c966826eeff4c99b8f8ebfe74511fc'),
('rp008','f6817f48af4fb3af11b9e8bf182f618b','1438782851980210178'),
('rp009','f6817f48af4fb3af11b9e8bf182f618b','1214462306546319362'),
('rp010','f6817f48af4fb3af11b9e8bf182f618b','1214376304951664642'),
('rp011','f6817f48af4fb3af11b9e8bf182f618b','1214376304951664643'),
('rp012','f6817f48af4fb3af11b9e8bf182f618b','1214376304951664644'),
('rp_biz_pm','f6817f48af4fb3af11b9e8bf182f618b','biz_pm'),
('rp_biz_pm_info','f6817f48af4fb3af11b9e8bf182f618b','biz_pm_info'),
('rp_biz_pm_cat','f6817f48af4fb3af11b9e8bf182f618b','biz_pm_cat'),
('rp_biz_sa','f6817f48af4fb3af11b9e8bf182f618b','biz_sa'),
('rp_biz_sa_review','f6817f48af4fb3af11b9e8bf182f618b','biz_sa_review'),
('rp_biz_sa_keyword','f6817f48af4fb3af11b9e8bf182f618b','biz_sa_keyword'),
('rp_biz_sa_board','f6817f48af4fb3af11b9e8bf182f618b','biz_sa_board'),
('rp_biz_sa_causal','f6817f48af4fb3af11b9e8bf182f618b','biz_sa_causal');
"""

DICT_SQL = r"""
INSERT INTO `sys_dict` (`id`,`dict_name`,`dict_code`,`description`,`del_flag`,`type`,`create_by`,`create_time`) VALUES
('3d9a351be3436fbefb1307d4cfb49bf2','性别','sex','性别',0,1,'admin','2019-01-04 14:56:32'),
('fc6cd58fde2e8481db10d3a1e68ce70c','用户状态','user_status','用户状态',0,1,'admin','2019-03-18 21:57:25'),
('a7adbcd86c37f7dbc9b66945c82ef9e6','1是0否','yn','是否',0,0,'admin','2019-05-22 19:29:29');

INSERT INTO `sys_dict_item` (`id`,`dict_id`,`item_text`,`item_value`,`sort_order`,`status`,`create_by`,`create_time`) VALUES
('di001','3d9a351be3436fbefb1307d4cfb49bf2','男','1',1,1,'admin','2019-01-04 14:56:32'),
('di002','3d9a351be3436fbefb1307d4cfb49bf2','女','2',2,1,'admin','2019-01-04 14:56:32'),
('di007','fc6cd58fde2e8481db10d3a1e68ce70c','正常','1',1,1,'admin','2019-03-18 21:57:25'),
('di008','fc6cd58fde2e8481db10d3a1e68ce70c','冻结','2',2,1,'admin','2019-03-18 21:57:25'),
('di009','a7adbcd86c37f7dbc9b66945c82ef9e6','是','1',1,1,'admin','2019-05-22 19:29:29'),
('di010','a7adbcd86c37f7dbc9b66945c82ef9e6','否','0',2,1,'admin','2019-05-22 19:29:29');
"""


def main():
    parser = argparse.ArgumentParser(description="生成唯一部署 SQL（默认写入全量评论数据集）")
    parser.add_argument(
        "--per-category",
        type=int,
        default=0,
        help="每个类目最多条数；0=全量（默认）",
    )
    parser.add_argument("--batch-size", type=int, default=200, help="每条 INSERT 的行数")
    parser.add_argument("--out", type=str, default=str(SQL_PATH))
    args = parser.parse_args()
    out = Path(args.out)
    stats = write_sql(out, per_category=args.per_category, batch_size=args.batch_size)
    print(
        f"wrote {out} size={stats['bytes']} bytes "
        f"reviews={stats['reviews']} products={stats['products']} keywords={stats['keywords']}"
    )


if __name__ == "__main__":
    main()
