---
license: CC0
technical_domain:
  - Emotion Recognition
  - 自然语言处理
---

<div>数据说明<br/>本数据集包括52 万件商品，1100 多个类目，142 万用户，720 万条评论/评分数据<br/>本次练习赛所使用数据集基于JD的电商数据，来自WWW的JD.com E-Commerce Data，并且针对部分字段做出了一定的调整，所有的字段信息请以本练习赛提供的字段信息为准<br/>字段信息内容参考如下：</div>
<div>
<div>1 . 商品信息.csv</div>
<div><br/>商品ID<br/>string<br/>产品 id (PRODUCT_0)<br/>商品名称<br/>string<br/>商品的具体名称，例如&ldquo;新编家常菜谱(名厨指导版)&rdquo;<br/>所属类别<br/>string<br/>商品所属类别（从 0 开始，连续编号，从左到右依次表示一级类目、二级类目、三级类目）</div>
<div>&nbsp;</div>
</div>
<div>
<div>2 . 商品类别列表.csv</div>
<div>&nbsp;</div>
<div><br/>类别ID<br/>string<br/>类别 id (从 0 开始，连续编号)<br/>类别名称<br/>string<br/>类别名称</div>
</div>
<div>&nbsp;</div>
<div>
<div>3 . 训练集</div>
<div><br/>数据ID<br/>string<br/>每条数据的唯一id，例如TRAIN_0<br/>用户ID<br/>int<br/>用户 id (从 0 开始，连续编号)<br/>商品ID<br/>string<br/>即 products.csv 中的 productId<br/>评论时间戳<br/>int<br/>评分的时间戳<br/>评论标题<br/>string<br/>评论的标题<br/>评论内容<br/>string<br/>评论的内容<br/>评分<br/>int<br/>评分，[1,5] 之间的整数</div>
</div>
<div>&nbsp;</div>
<div>
<div>4 .测试集</div>
<div><br/>每条数据的唯一id，例如TRAIN_0<br/>用户ID<br/>用户 id (从 0 开始，连续编号)<br/>商品ID<br/>即 products.csv 中的 productId<br/>评论时间戳<br/>评分的时间戳<br/>评论标题<br/>评论的标题<br/>评论内容<br/>评论的内容</div>
</div>