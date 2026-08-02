<template>
  <BasicModal v-bind="$attrs" @register="registerModal" title="评价详情" :showOkBtn="false" cancelText="关闭" width="640px">
    <Description @register="registerDesc" />
  </BasicModal>
</template>
<script lang="ts" setup>
  import { BasicModal, useModalInner } from '/@/components/Modal';
  import { Description, useDescription } from '/@/components/Description';

  const [registerDesc, { setDescProps }] = useDescription({
    column: 1,
    schema: [
      { field: 'productName', label: '商品' },
      { field: 'categoryName', label: '类目' },
      { field: 'username', label: '用户' },
      { field: 'sentiment_dictText', label: '情绪' },
      { field: 'score', label: '置信分' },
      { field: 'keywordsText', label: '关键词' },
      { field: 'createTime', label: '时间' },
      { field: 'content', label: '评价内容' },
      { field: 'summary', label: '分析摘要' },
    ],
  });

  const [registerModal] = useModalInner(async (data) => {
    setDescProps({ data: data?.record || {} });
  });
</script>
