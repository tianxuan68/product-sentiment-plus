<template>
  <BasicModal v-bind="$attrs" @register="registerModal" title="分析详情" :showOkBtn="false" cancelText="关闭" width="680px">
    <Description @register="registerDesc" />
    <a-divider />
    <div class="detail-title">对比明细（更容易对照）</div>
    <a-descriptions bordered size="small" :column="1">
      <a-descriptions-item label="提到服务，且是好评">{{ table.t1_y1 ?? 0 }} 条</a-descriptions-item>
      <a-descriptions-item label="提到服务，但不是好评">{{ table.t1_y0 ?? 0 }} 条</a-descriptions-item>
      <a-descriptions-item label="没提服务，但是好评">{{ table.t0_y1 ?? 0 }} 条</a-descriptions-item>
      <a-descriptions-item label="没提服务，也不是好评">{{ table.t0_y0 ?? 0 }} 条</a-descriptions-item>
    </a-descriptions>
    <p class="detail-note">{{ record.explanation || '' }}</p>
  </BasicModal>
</template>
<script lang="ts" setup>
  import { reactive, ref } from 'vue';
  import { BasicModal, useModalInner } from '/@/components/Modal';
  import { Description, useDescription } from '/@/components/Description';

  const record = ref<Recordable>({});
  const table = reactive<Recordable>({ t1_y1: 0, t1_y0: 0, t0_y1: 0, t0_y0: 0 });

  const [registerDesc, { setDescProps }] = useDescription({
    column: 1,
    schema: [
      { field: 'categoryName', label: '类目' },
      { field: 'sampleSize', label: '评价条数' },
      { field: 'treatmentRateText', label: '提到服务占比' },
      { field: 'outcomeRateText', label: '好评占比' },
      { field: 'conclusion', label: '结论（白话）' },
      { field: 'updateTime', label: '更新时间' },
    ],
  });

  const [registerModal] = useModalInner(async (data) => {
    const r = data?.record || {};
    record.value = r;
    Object.assign(table, r.table || {});
    setDescProps({
      data: {
        ...r,
        treatmentRateText:
          r.treatmentRate == null ? '-' : `${Math.round(Number(r.treatmentRate) * 1000) / 10}%`,
        outcomeRateText: r.outcomeRate == null ? '-' : `${Math.round(Number(r.outcomeRate) * 1000) / 10}%`,
        conclusion: r.conclusion || r.ateText || '-',
      },
    });
  });
</script>
<style lang="less" scoped>
  .detail-title {
    margin-bottom: 8px;
    color: #214d58;
    font-weight: 650;
  }

  .detail-note {
    margin-top: 12px;
    color: #75979b;
    font-size: 13px;
    line-height: 1.6;
  }
</style>
