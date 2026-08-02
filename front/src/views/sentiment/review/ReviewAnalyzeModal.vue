<template>
  <BasicModal
    v-bind="$attrs"
    @register="registerModal"
    title="评价分析"
    :showOkBtn="false"
    cancelText="关闭"
    width="680px"
    :loading="loading"
  >
    <a-spin :spinning="loading">
      <Description @register="registerDesc" />
      <div v-if="tagNames.length" class="tag-block">
        <div class="tag-label">模型标签</div>
        <div class="tag-list">
          <a-tag v-for="(name, idx) in tagNames" :key="`${name}-${idx}`" color="processing">{{ name }}</a-tag>
        </div>
      </div>
      <a-table
        v-if="tags.length"
        class="tag-table"
        size="small"
        :pagination="false"
        :columns="tagColumns"
        :dataSource="tags"
        rowKey="__key"
      />
      <a-empty v-else-if="!loading && !tagNames.length" description="未识别到标签" />
    </a-spin>
  </BasicModal>
</template>
<script lang="ts" setup>
  import { ref } from 'vue';
  import { BasicModal, useModalInner } from '/@/components/Modal';
  import { Description, useDescription } from '/@/components/Description';
  import { useMessage } from '/@/hooks/web/useMessage';
  import { analyzeReview } from './review.api';

  const emit = defineEmits(['success', 'register']);
  const { createMessage } = useMessage();
  const loading = ref(false);
  const tagNames = ref<string[]>([]);
  const tags = ref<Recordable[]>([]);

  const tagColumns = [
    { title: '方面', dataIndex: 'aspect', width: 100 },
    { title: '标签', dataIndex: 'tag', width: 140 },
    { title: '极性', dataIndex: 'polarity', width: 80 },
    { title: '得分', dataIndex: 'score', width: 80 },
    { title: '来源', dataIndex: 'source', width: 120 },
  ];

  const [registerDesc, { setDescProps }] = useDescription({
    column: 1,
    schema: [
      { field: 'productName', label: '商品' },
      { field: 'categoryName', label: '类目' },
      { field: 'sentiment_dictText', label: '情绪' },
      { field: 'score', label: '置信分' },
      { field: 'backend', label: '模型后端' },
      { field: 'summary', label: '分析摘要' },
      { field: 'content', label: '评价内容' },
    ],
  });

  const [registerModal, { setModalProps }] = useModalInner(async (data) => {
    const record = data?.record || {};
    tagNames.value = [];
    tags.value = [];
    setDescProps({ data: { ...record, backend: '-' } });
    if (!record.id) return;

    loading.value = true;
    setModalProps({ loading: true, confirmLoading: true });
    try {
      const result = await analyzeReview(record.id);
      const next = { ...record, ...result };
      setDescProps({ data: next });
      tagNames.value = Array.isArray(result?.tagNames) ? result.tagNames : [];
      const rawTags = Array.isArray(result?.tags) ? result.tags : [];
      tags.value = rawTags.map((t, i) => ({
        ...t,
        __key: `${t?.tag || 't'}-${i}`,
        score: t?.score != null ? Number(t.score).toFixed(3) : '-',
      }));
      emit('success');
    } catch (e: any) {
      createMessage.error(e?.message || '评价分析失败');
    } finally {
      loading.value = false;
      setModalProps({ loading: false, confirmLoading: false });
    }
  });
</script>
<style scoped>
  .tag-block {
    margin: 12px 0 8px;
  }
  .tag-label {
    margin-bottom: 8px;
    color: rgba(0, 0, 0, 0.65);
    font-size: 13px;
  }
  .tag-list {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .tag-table {
    margin-top: 12px;
  }
</style>
