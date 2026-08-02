-- 已有库升级：商品类目树 / 商品 / 情感询问记录
-- 用法: mysql -u root -p jeecg-boot < sql/patch_add_biz_tables.sql

USE `jeecg-boot`;
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `biz_category` (
  `id` varchar(32) NOT NULL,
  `parent_id` varchar(32) DEFAULT '' COMMENT '父类目ID，空串为根',
  `name` varchar(100) NOT NULL COMMENT '类目名称',
  `code` varchar(64) DEFAULT NULL COMMENT '类目编码',
  `path` varchar(512) DEFAULT NULL COMMENT '物化路径，如 /根/子/',
  `level` int DEFAULT 1 COMMENT '层级，根为1',
  `sort_no` int DEFAULT 0 COMMENT '同级排序',
  `icon` varchar(255) DEFAULT NULL,
  `description` varchar(500) DEFAULT NULL,
  `is_leaf` tinyint(1) DEFAULT 1 COMMENT '1叶子 0非叶子',
  `status` tinyint(1) DEFAULT 1 COMMENT '1启用 0停用',
  `del_flag` tinyint(1) DEFAULT 0 COMMENT '1删除',
  `create_by` varchar(32) DEFAULT NULL,
  `create_time` datetime DEFAULT NULL,
  `update_by` varchar(32) DEFAULT NULL,
  `update_time` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_biz_cat_parent` (`parent_id`),
  KEY `idx_biz_cat_code` (`code`),
  KEY `idx_biz_cat_path` (`path`(191))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品类目（树）';

CREATE TABLE IF NOT EXISTS `biz_product` (
  `id` varchar(32) NOT NULL,
  `name` varchar(200) NOT NULL COMMENT '商品名称',
  `category_id` varchar(32) DEFAULT NULL COMMENT '类目ID',
  `brand` varchar(100) DEFAULT NULL COMMENT '品牌',
  `sku` varchar(64) DEFAULT NULL COMMENT 'SKU编码',
  `price` decimal(12,2) DEFAULT NULL COMMENT '售价',
  `original_price` decimal(12,2) DEFAULT NULL COMMENT '原价/划线价',
  `currency` varchar(8) DEFAULT 'CNY',
  `cover_url` varchar(500) DEFAULT NULL COMMENT '封面图',
  `rating` decimal(3,1) DEFAULT NULL COMMENT '评分 0-5',
  `stock` int DEFAULT 0 COMMENT '库存',
  `unit` varchar(20) DEFAULT NULL COMMENT '单位',
  `status` tinyint(1) DEFAULT 1 COMMENT '1上架 0下架',
  `description` text COMMENT '商品描述',
  `note` varchar(1000) DEFAULT NULL COMMENT '备注',
  `del_flag` tinyint(1) DEFAULT 0,
  `create_by` varchar(32) DEFAULT NULL,
  `create_time` datetime DEFAULT NULL,
  `update_by` varchar(32) DEFAULT NULL,
  `update_time` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_biz_prod_cat` (`category_id`),
  KEY `idx_biz_prod_name` (`name`),
  KEY `idx_biz_prod_sku` (`sku`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品';

CREATE TABLE IF NOT EXISTS `biz_sentiment_query` (
  `id` varchar(32) NOT NULL,
  `user_id` varchar(32) DEFAULT NULL COMMENT '提问用户',
  `username` varchar(100) DEFAULT NULL,
  `product_id` varchar(32) DEFAULT NULL,
  `product_name` varchar(200) DEFAULT NULL,
  `category_id` varchar(32) DEFAULT NULL,
  `category_name` varchar(100) DEFAULT NULL,
  `content` text NOT NULL COMMENT '用户询问/评价原文',
  `sentiment` varchar(20) DEFAULT NULL COMMENT 'positive/neutral/negative',
  `score` int DEFAULT NULL COMMENT '置信分 0-100',
  `summary` text COMMENT '分析摘要',
  `keywords` varchar(1000) DEFAULT NULL COMMENT '关键词JSON数组',
  `create_time` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_biz_sq_user` (`user_id`),
  KEY `idx_biz_sq_product` (`product_id`),
  KEY `idx_biz_sq_time` (`create_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='情感分析询问记录';

-- 种子类目（与 Insight 页训练类目对齐，根级 + 若干二级示例子树）
INSERT INTO `biz_category` (`id`,`parent_id`,`name`,`code`,`path`,`level`,`sort_no`,`is_leaf`,`status`,`del_flag`,`create_by`,`create_time`)
SELECT * FROM (
  SELECT 'cat001' AS id,'' AS parent_id,'图书音像' AS name,'books' AS code,'/cat001/' AS path,1 AS level,1 AS sort_no,0 AS is_leaf,1 AS status,0 AS del_flag,'admin' AS create_by,'2026-08-03 00:00:00' AS create_time
  UNION ALL SELECT 'cat00101','cat001','图书','books_book','/cat001/cat00101/',2,1,1,1,0,'admin','2026-08-03 00:00:00'
  UNION ALL SELECT 'cat00102','cat001','音像','books_media','/cat001/cat00102/',2,2,1,1,0,'admin','2026-08-03 00:00:00'
  UNION ALL SELECT 'cat002','','电脑/办公','computer','/cat002/',1,2,0,1,0,'admin','2026-08-03 00:00:00'
  UNION ALL SELECT 'cat00201','cat002','笔记本','computer_laptop','/cat002/cat00201/',2,1,1,1,0,'admin','2026-08-03 00:00:00'
  UNION ALL SELECT 'cat00202','cat002','办公设备','computer_office','/cat002/cat00202/',2,2,1,1,0,'admin','2026-08-03 00:00:00'
  UNION ALL SELECT 'cat003','','手机/数码','digital','/cat003/',1,3,0,1,0,'admin','2026-08-03 00:00:00'
  UNION ALL SELECT 'cat00301','cat003','手机','digital_phone','/cat003/cat00301/',2,1,1,1,0,'admin','2026-08-03 00:00:00'
  UNION ALL SELECT 'cat00302','cat003','数码配件','digital_acc','/cat003/cat00302/',2,2,1,1,0,'admin','2026-08-03 00:00:00'
  UNION ALL SELECT 'cat004','','美妆个护','beauty','/cat004/',1,4,1,1,0,'admin','2026-08-03 00:00:00'
  UNION ALL SELECT 'cat005','','家用电器','appliance','/cat005/',1,5,1,1,0,'admin','2026-08-03 00:00:00'
  UNION ALL SELECT 'cat006','','家居生活','home','/cat006/',1,6,1,1,0,'admin','2026-08-03 00:00:00'
  UNION ALL SELECT 'cat007','','其他','other','/cat007/',1,7,1,1,0,'admin','2026-08-03 00:00:00'
  UNION ALL SELECT 'cat008','','母婴/玩具','baby','/cat008/',1,8,1,1,0,'admin','2026-08-03 00:00:00'
  UNION ALL SELECT 'cat009','','家具/家装/建材','furnish','/cat009/',1,9,1,1,0,'admin','2026-08-03 00:00:00'
  UNION ALL SELECT 'cat010','','钟表/首饰/眼镜/礼品','jewelry','/cat010/',1,10,1,1,0,'admin','2026-08-03 00:00:00'
  UNION ALL SELECT 'cat011','','食品/保健','food','/cat011/',1,11,1,1,0,'admin','2026-08-03 00:00:00'
  UNION ALL SELECT 'cat012','','鞋类箱包','shoes','/cat012/',1,12,1,1,0,'admin','2026-08-03 00:00:00'
  UNION ALL SELECT 'cat013','','运动户外','sports','/cat013/',1,13,1,1,0,'admin','2026-08-03 00:00:00'
  UNION ALL SELECT 'cat014','','服饰服装','apparel','/cat014/',1,14,1,1,0,'admin','2026-08-03 00:00:00'
  UNION ALL SELECT 'cat015','','机票/充值/票务/虚拟','virtual','/cat015/',1,15,1,1,0,'admin','2026-08-03 00:00:00'
) AS seed
WHERE NOT EXISTS (SELECT 1 FROM `biz_category` WHERE `id` = seed.id);

SELECT 'biz_category / biz_product / biz_sentiment_query ready' AS message;
