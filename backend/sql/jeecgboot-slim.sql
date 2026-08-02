-- =============================================================================
-- Sentiment-Plus / JeecgBoot FastAPI 全量数据库初始化（唯一入口）
-- =============================================================================
-- 包含：登录权限、字典、短信缓存、第三方登录、系统配置（用户/角色/菜单/部门/字典）
--
-- 用法:
--   mysql -u root -p < sql/jeecgboot-slim.sql
--   或 python scripts/init_slim_db.py
--
-- 默认账号: admin / 123456
-- =============================================================================

CREATE DATABASE IF NOT EXISTS `jeecg-boot` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `jeecg-boot`;

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- 清理旧表（仅本项目使用的表）
DROP TABLE IF EXISTS `biz_sentiment_query`;
DROP TABLE IF EXISTS `biz_product`;
DROP TABLE IF EXISTS `biz_category`;
DROP TABLE IF EXISTS `sys_cache`;
DROP TABLE IF EXISTS `sys_third_app_config`;
DROP TABLE IF EXISTS `sys_third_account`;
DROP TABLE IF EXISTS `sys_role_permission`;
DROP TABLE IF EXISTS `sys_user_role`;
DROP TABLE IF EXISTS `sys_user_depart`;
DROP TABLE IF EXISTS `sys_dict_item`;
DROP TABLE IF EXISTS `sys_dict`;
DROP TABLE IF EXISTS `sys_permission`;
DROP TABLE IF EXISTS `sys_depart`;
DROP TABLE IF EXISTS `sys_role`;
DROP TABLE IF EXISTS `sys_user`;

-- ========== 短信 / 扫码登录缓存 ==========
CREATE TABLE `sys_cache` (
  `cache_key` varchar(128) NOT NULL,
  `cache_value` varchar(512) DEFAULT NULL,
  `expire_time` datetime DEFAULT NULL,
  PRIMARY KEY (`cache_key`),
  KEY `idx_expire` (`expire_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='临时缓存（短信验证码/扫码登录）';

-- ========== 系统用户与权限 ==========
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
  KEY `idx_sur_user` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户角色';

CREATE TABLE `sys_permission` (
  `id` varchar(32) NOT NULL,
  `parent_id` varchar(32) DEFAULT NULL,
  `name` varchar(255) DEFAULT NULL,
  `url` varchar(255) DEFAULT NULL,
  `component` varchar(255) DEFAULT NULL,
  `is_route` tinyint(1) DEFAULT 1,
  `component_name` varchar(255) DEFAULT NULL,
  `redirect` varchar(255) DEFAULT NULL,
  `menu_type` int DEFAULT NULL,
  `perms` varchar(255) DEFAULT NULL,
  `perms_type` varchar(10) DEFAULT '0',
  `sort_no` double(8,2) DEFAULT NULL,
  `always_show` tinyint(1) DEFAULT NULL,
  `icon` varchar(255) DEFAULT NULL,
  `is_leaf` tinyint(1) DEFAULT NULL,
  `keep_alive` tinyint(1) DEFAULT NULL,
  `hidden` tinyint DEFAULT 0,
  `hide_tab` tinyint DEFAULT NULL,
  `del_flag` int DEFAULT 0,
  `rule_flag` int DEFAULT 0,
  `status` varchar(2) DEFAULT NULL,
  `internal_or_external` tinyint(1) DEFAULT NULL,
  `create_by` varchar(255) DEFAULT NULL,
  `create_time` datetime DEFAULT NULL,
  `update_by` varchar(255) DEFAULT NULL,
  `update_time` datetime DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='菜单权限';

CREATE TABLE `sys_role_permission` (
  `id` varchar(32) NOT NULL,
  `role_id` varchar(32) DEFAULT NULL,
  `permission_id` varchar(32) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_srp_role` (`role_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色权限';

CREATE TABLE `sys_depart` (
  `id` varchar(32) NOT NULL,
  `parent_id` varchar(32) DEFAULT NULL,
  `depart_name` varchar(100) NOT NULL,
  `depart_order` int DEFAULT 0,
  `org_category` varchar(10) DEFAULT '1',
  `org_type` varchar(10) DEFAULT NULL,
  `org_code` varchar(64) NOT NULL,
  `status` varchar(1) DEFAULT NULL,
  `del_flag` varchar(1) DEFAULT '0',
  `tenant_id` int DEFAULT 0,
  `iz_leaf` tinyint(1) DEFAULT 0,
  `create_by` varchar(32) DEFAULT NULL,
  `create_time` datetime DEFAULT NULL,
  `update_by` varchar(32) DEFAULT NULL,
  `update_time` datetime DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='部门';

CREATE TABLE `sys_user_depart` (
  `ID` varchar(32) NOT NULL,
  `user_id` varchar(32) DEFAULT NULL,
  `dep_id` varchar(32) DEFAULT NULL,
  PRIMARY KEY (`ID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户部门';

CREATE TABLE `sys_dict` (
  `id` varchar(32) NOT NULL,
  `dict_name` varchar(100) NOT NULL,
  `dict_code` varchar(100) NOT NULL,
  `description` varchar(255) DEFAULT NULL,
  `del_flag` int DEFAULT 0,
  `type` int DEFAULT 0,
  `tenant_id` int DEFAULT 0,
  `create_by` varchar(32) DEFAULT NULL,
  `create_time` datetime DEFAULT NULL,
  `update_by` varchar(32) DEFAULT NULL,
  `update_time` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_dict_code` (`dict_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='字典';

CREATE TABLE `sys_dict_item` (
  `id` varchar(32) NOT NULL,
  `dict_id` varchar(32) DEFAULT NULL,
  `item_text` varchar(100) NOT NULL,
  `item_value` varchar(100) NOT NULL,
  `description` varchar(255) DEFAULT NULL,
  `sort_order` int DEFAULT NULL,
  `status` int DEFAULT NULL,
  `create_by` varchar(32) DEFAULT NULL,
  `create_time` datetime DEFAULT NULL,
  `update_by` varchar(32) DEFAULT NULL,
  `update_time` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_sdi_dict` (`dict_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='字典项';

-- ========== 第三方登录 ==========
CREATE TABLE `sys_third_account` (
  `id` varchar(32) NOT NULL,
  `sys_user_id` varchar(32) DEFAULT NULL,
  `avatar` varchar(255) DEFAULT NULL,
  `status` tinyint(1) DEFAULT 1,
  `del_flag` tinyint(1) DEFAULT 0,
  `realname` varchar(100) DEFAULT NULL,
  `tenant_id` int DEFAULT 0,
  `third_user_uuid` varchar(100) DEFAULT NULL,
  `third_user_id` varchar(100) DEFAULT NULL,
  `third_type` varchar(50) DEFAULT NULL,
  `create_by` varchar(32) DEFAULT NULL,
  `create_time` datetime DEFAULT NULL,
  `update_by` varchar(32) DEFAULT NULL,
  `update_time` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_sta_user_type` (`sys_user_id`,`third_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='第三方账号';

CREATE TABLE `sys_third_app_config` (
  `id` varchar(32) NOT NULL,
  `tenant_id` int NOT NULL DEFAULT 0,
  `agent_id` varchar(20) DEFAULT NULL,
  `client_id` varchar(50) DEFAULT NULL,
  `client_secret` varchar(100) DEFAULT NULL,
  `corp_id` varchar(100) DEFAULT NULL,
  `third_type` varchar(20) DEFAULT NULL,
  `status` int DEFAULT 1,
  `create_time` datetime DEFAULT NULL,
  `update_time` datetime DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='第三方应用配置';

-- ========== 业务：类目 / 商品 / 情感询问 ==========
CREATE TABLE `biz_category` (
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

CREATE TABLE `biz_product` (
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

CREATE TABLE `biz_sentiment_query` (
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

-- =============================================================================
-- 初始数据
-- =============================================================================

INSERT INTO `sys_user` (`id`,`username`,`realname`,`password`,`salt`,`status`,`del_flag`,`org_code`,`create_time`) VALUES
('e9ca23d68d884d4ebb19d07889727dae','admin','管理员','cb362cfeefbf3d8d','RCGTeGiH',1,0,'A01A03','2019-06-21 17:54:10');

INSERT INTO `sys_role` (`id`,`role_name`,`role_code`,`description`,`create_time`) VALUES
('f6817f48af4fb3af11b9e8bf182f618b','管理员','admin','系统管理员','2020-12-21 18:03:39');

INSERT INTO `sys_user_role` (`id`,`user_id`,`role_id`) VALUES
('1996175712356261890','e9ca23d68d884d4ebb19d07889727dae','f6817f48af4fb3af11b9e8bf182f618b');

INSERT INTO `sys_depart` (`id`,`parent_id`,`depart_name`,`depart_order`,`org_category`,`org_type`,`org_code`,`del_flag`,`create_time`) VALUES
('c6d7cb4deeac411cb3384b1b31278596','','系统根组织',0,'1','1','A01','0','2019-02-11 14:21:51'),
('4f1765520d6346f9bd9c79e2479e5b12','c6d7cb4deeac411cb3384b1b31278596','研发部',1,'2','2','A01A03','0','2019-02-20 17:15:34');

INSERT INTO `sys_user_depart` (`ID`,`user_id`,`dep_id`) VALUES
('1996175712356261891','e9ca23d68d884d4ebb19d07889727dae','4f1765520d6346f9bd9c79e2479e5b12');

-- 菜单（仅系统管理）
INSERT INTO `sys_permission` (`id`,`parent_id`,`name`,`url`,`component`,`is_route`,`redirect`,`menu_type`,`sort_no`,`icon`,`is_leaf`,`keep_alive`,`hidden`,`del_flag`,`status`) VALUES
('d7d6e2e4e2934f2c9385a623fd98c6f3','','系统管理','/isystem','layouts/RouteView',1,'/system/user',0,1.00,'ant-design:setting',0,0,0,0,'1'),
('3f915b2769fc80648e92d04e84ca059d','d7d6e2e4e2934f2c9385a623fd98c6f3','用户管理','/system/user','system/user/index',1,NULL,1,1.00,'ant-design:user',0,1,0,0,'1'),
('190c2b43bec6a5f7a4194a85db67d96a','d7d6e2e4e2934f2c9385a623fd98c6f3','角色管理','/system/role','system/role/index',1,NULL,1,2.00,'ant-design:solution',0,1,0,0,'1'),
('1170592628746878978','d7d6e2e4e2934f2c9385a623fd98c6f3','菜单管理','/system/menu','system/menu/index',1,NULL,1,3.00,'ant-design:menu-fold-outlined',0,0,0,0,'1'),
('45c966826eeff4c99b8f8ebfe74511fc','d7d6e2e4e2934f2c9385a623fd98c6f3','部门管理','/system/depart','system/depart/index',1,NULL,1,4.00,'ant-design:team',0,0,0,0,'1'),
('1438782851980210178','d7d6e2e4e2934f2c9385a623fd98c6f3','数据字典','/system/dict','system/dict/index',1,NULL,1,5.00,'ant-design:hdd-twotone',0,0,0,0,'1');

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
('rp012','f6817f48af4fb3af11b9e8bf182f618b','1214376304951664644');

-- 字典（系统）
INSERT INTO `sys_dict` (`id`,`dict_name`,`dict_code`,`description`,`del_flag`,`type`,`create_by`,`create_time`) VALUES
('3d9a351be3436fbefb1307d4cfb49bf2','性别','sex','性别',0,1,'admin','2019-01-04 14:56:32'),
('fc6cd58fde2e8481db10d3a1e68ce70c','用户状态','user_status','用户状态',0,1,'admin','2019-03-18 21:57:25'),
('a7adbcd86c37f7dbc9b66945c82ef9e6','1是0否','yn','是否',0,0,'admin','2019-05-22 19:29:29'),
('1174511106530525185','机构类型','org_category','机构类型',0,0,'admin','2019-09-19 10:30:43'),
('4c753b5293304e7a445fd2741b46529d','字典状态','dict_item_status','字典项状态',0,1,'admin','2020-06-18 23:18:42'),
('2e02df51611a4b9632828ab7e5338f00','权限策略','perms_type','权限策略',0,0,'admin','2019-04-26 18:26:55');

INSERT INTO `sys_dict_item` (`id`,`dict_id`,`item_text`,`item_value`,`sort_order`,`status`,`create_by`,`create_time`) VALUES
('di001','3d9a351be3436fbefb1307d4cfb49bf2','男','1',1,1,'admin','2019-01-04 14:56:32'),
('di002','3d9a351be3436fbefb1307d4cfb49bf2','女','2',2,1,'admin','2019-01-04 14:56:32'),
('di007','fc6cd58fde2e8481db10d3a1e68ce70c','正常','1',1,1,'admin','2019-03-18 21:57:25'),
('di008','fc6cd58fde2e8481db10d3a1e68ce70c','冻结','2',2,1,'admin','2019-03-18 21:57:25'),
('di009','a7adbcd86c37f7dbc9b66945c82ef9e6','是','1',1,1,'admin','2019-05-22 19:29:29'),
('di010','a7adbcd86c37f7dbc9b66945c82ef9e6','否','0',2,1,'admin','2019-05-22 19:29:29');

-- 业务类目种子（根级 + 示例子树，对齐 Insight 训练类目）
INSERT INTO `biz_category` (`id`,`parent_id`,`name`,`code`,`path`,`level`,`sort_no`,`is_leaf`,`status`,`del_flag`,`create_by`,`create_time`) VALUES
('cat001','','图书音像','books','/cat001/',1,1,0,1,0,'admin','2026-08-03 00:00:00'),
('cat00101','cat001','图书','books_book','/cat001/cat00101/',2,1,1,1,0,'admin','2026-08-03 00:00:00'),
('cat00102','cat001','音像','books_media','/cat001/cat00102/',2,2,1,1,0,'admin','2026-08-03 00:00:00'),
('cat002','','电脑/办公','computer','/cat002/',1,2,0,1,0,'admin','2026-08-03 00:00:00'),
('cat00201','cat002','笔记本','computer_laptop','/cat002/cat00201/',2,1,1,1,0,'admin','2026-08-03 00:00:00'),
('cat00202','cat002','办公设备','computer_office','/cat002/cat00202/',2,2,1,1,0,'admin','2026-08-03 00:00:00'),
('cat003','','手机/数码','digital','/cat003/',1,3,0,1,0,'admin','2026-08-03 00:00:00'),
('cat00301','cat003','手机','digital_phone','/cat003/cat00301/',2,1,1,1,0,'admin','2026-08-03 00:00:00'),
('cat00302','cat003','数码配件','digital_acc','/cat003/cat00302/',2,2,1,1,0,'admin','2026-08-03 00:00:00'),
('cat004','','美妆个护','beauty','/cat004/',1,4,1,1,0,'admin','2026-08-03 00:00:00'),
('cat005','','家用电器','appliance','/cat005/',1,5,1,1,0,'admin','2026-08-03 00:00:00'),
('cat006','','家居生活','home','/cat006/',1,6,1,1,0,'admin','2026-08-03 00:00:00'),
('cat007','','其他','other','/cat007/',1,7,1,1,0,'admin','2026-08-03 00:00:00'),
('cat008','','母婴/玩具','baby','/cat008/',1,8,1,1,0,'admin','2026-08-03 00:00:00'),
('cat009','','家具/家装/建材','furnish','/cat009/',1,9,1,1,0,'admin','2026-08-03 00:00:00'),
('cat010','','钟表/首饰/眼镜/礼品','jewelry','/cat010/',1,10,1,1,0,'admin','2026-08-03 00:00:00'),
('cat011','','食品/保健','food','/cat011/',1,11,1,1,0,'admin','2026-08-03 00:00:00'),
('cat012','','鞋类箱包','shoes','/cat012/',1,12,1,1,0,'admin','2026-08-03 00:00:00'),
('cat013','','运动户外','sports','/cat013/',1,13,1,1,0,'admin','2026-08-03 00:00:00'),
('cat014','','服饰服装','apparel','/cat014/',1,14,1,1,0,'admin','2026-08-03 00:00:00'),
('cat015','','机票/充值/票务/虚拟','virtual','/cat015/',1,15,1,1,0,'admin','2026-08-03 00:00:00');

SET FOREIGN_KEY_CHECKS = 1;

SELECT 'system-config slim sql 初始化完成' AS message;
