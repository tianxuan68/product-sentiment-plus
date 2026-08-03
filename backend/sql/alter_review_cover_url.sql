-- 评价配图：手机端评论列表主图
ALTER TABLE `biz_sentiment_query`
  ADD COLUMN `cover_url` varchar(500) DEFAULT NULL COMMENT '评价配图' AFTER `content`;
