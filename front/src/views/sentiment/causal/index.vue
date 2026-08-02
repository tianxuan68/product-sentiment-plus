<template>
  <div>
    <BasicTable @register="registerTable" :rowSelection="rowSelection">
      <template #tableTitle>
        <a-button type="primary" preIcon="ant-design:play-circle-outlined" :loading="running" @click="handleRun">
          运行分析
        </a-button>
        <a-button type="primary" preIcon="ant-design:plus-outlined" @click="handleCreateReview"> 新增评价 </a-button>
        <a-button type="primary" preIcon="ant-design:upload-outlined" @click="handleImportReview"> 导入评价 </a-button>
        <a-button type="primary" danger preIcon="ant-design:delete-outlined" :disabled="!selectedRowKeys.length" @click="batchHandleDelete">
          删除
        </a-button>
      </template>
      <template #action="{ record }">
        <TableAction :actions="getTableAction(record)" :dropDownActions="getDropDownAction(record)" />
      </template>
    </BasicTable>
    <CausalDetailModal @register="registerModal" />
    <ReviewDrawer @register="registerDrawer" @success="onReviewReady" />
    <ReviewImportModal @register="registerImportModal" @success="onReviewReady" />
  </div>
</template>
<script lang="ts" name="sentiment-causal" setup>
  import { ref } from 'vue';
  import { useMessage } from '/@/hooks/web/useMessage';
  import { BasicTable, TableAction, ActionItem } from '/@/components/Table';
  import { useModal } from '/@/components/Modal';
  import { useDrawer } from '/@/components/Drawer';
  import { useListPage } from '/@/hooks/system/useListPage';
  import CausalDetailModal from './CausalDetailModal.vue';
  import ReviewDrawer from '/@/views/sentiment/review/ReviewDrawer.vue';
  import ReviewImportModal from '/@/views/sentiment/review/ReviewImportModal.vue';
  import { columns, searchFormSchema } from './causal.data';
  import { list, runCausal, deleteCausal, batchDeleteCausal } from './causal.api';

  const { createMessage } = useMessage();
  const running = ref(false);
  const [registerModal, { openModal }] = useModal();
  const [registerImportModal, { openModal: openImportModal }] = useModal();
  const [registerDrawer, { openDrawer }] = useDrawer();

  const { tableContext } = useListPage({
    designScope: 'causal-list',
    tableProps: {
      title: '因果分析结果',
      api: list,
      columns,
      formConfig: {
        schemas: searchFormSchema,
      },
      actionColumn: { width: 140 },
      beforeFetch: (params) => Object.assign({ column: 'updateTime', order: 'desc' }, params),
    },
  });

  const [registerTable, { reload, getForm }, { rowSelection, selectedRowKeys }] = tableContext;

  function handleCreateReview() {
    openDrawer(true, { isUpdate: false, showFooter: true });
  }

  function handleImportReview() {
    openImportModal(true, {});
  }

  function onReviewReady() {
    createMessage.info('评价已保存，可点击「运行分析」基于库内数据做因果预测');
  }

  async function handleRun() {
    running.value = true;
    try {
      const values = (await getForm()?.getFieldsValue?.()) || {};
      const data = await runCausal({ categoryName: values.categoryName || undefined });
      createMessage.success(`分析完成：${data?.categoryCount ?? 0} 个类目，评论 ${data?.reviewCount ?? 0} 条`);
      reload();
    } catch (e: any) {
      createMessage.error(e?.message || '分析失败');
    } finally {
      running.value = false;
    }
  }

  function handleDetail(record: Recordable) {
    openModal(true, { record });
  }

  async function handleDelete(record) {
    await deleteCausal({ id: record.id }, reload);
  }

  async function batchHandleDelete() {
    if (!selectedRowKeys.value.length) return;
    await batchDeleteCausal({ ids: selectedRowKeys.value.join(',') }, () => {
      selectedRowKeys.value = [];
      reload();
    });
  }

  function getTableAction(record): ActionItem[] {
    return [{ label: '详情', onClick: handleDetail.bind(null, record) }];
  }

  function getDropDownAction(record): ActionItem[] {
    return [
      {
        label: '删除',
        popConfirm: { title: '是否确认删除', confirm: handleDelete.bind(null, record) },
      },
    ];
  }
</script>
