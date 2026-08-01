-- 已有库升级：移除评论情感分析菜单（仅系统配置）
-- 用法: mysql -u root -p jeecg-boot < sql/patch_remove_sentiment.sql

DELETE FROM `sys_role_permission` WHERE `permission_id` IN ('sa001','sa002','sa003','sa004');
DELETE FROM `sys_permission` WHERE `id` IN ('sa001','sa002','sa003','sa004');

UPDATE `sys_permission`
SET `redirect` = '/system/user', `sort_no` = 1.00
WHERE `id` = 'd7d6e2e4e2934f2c9385a623fd98c6f3';

SELECT 'removed sentiment menus; default home -> /system/user' AS message;
