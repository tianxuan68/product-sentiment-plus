<template>
  <div>
    <BasicTable @register="registerTable" :rowSelection="rowSelection">
      <template #tableTitle>
        <a-button type="primary" preIcon="ant-design:plus-outlined" @click="handleCreate"> 新增</a-button>
        <a-button type="primary" preIcon="ant-design:upload-outlined" @click="handleImport"> 导入</a-button>
        <a-button type="primary" danger preIcon="ant-design:delete-outlined" :disabled="!selectedRowKeys.length" @click="batchHandleDelete">
          删除
        </a-button>
      </template>
      <template #action="{ record }">
        <TableAction :actions="getTableAction(record)" :dropDownActions="getDropDownAction(record)" />
      </template>
    </BasicTable>
    <ReviewDrawer @register="registerDrawer" @success="handleSuccess" />
    <ReviewDetailModal @register="registerModal" />
    <ReviewAnalyzeModal @register="registerAnalyzeModal" @success="handleSuccess" />
    <ReviewImportModal @register="registerImportModal" @success="handleSuccess" />
  </div>
</template>
<script lang="ts" name="sentiment-review" setup>
  import { BasicTable, TableAction, ActionItem } from '/@/components/Table';
  import { useModal } from '/@/components/Modal';
  import { useDrawer } from '/@/components/Drawer';
  import { useListPage } from '/@/hooks/system/useListPage';
  import ReviewDrawer from './ReviewDrawer.vue';
  import ReviewDetailModal from './ReviewDetailModal.vue';
  import ReviewAnalyzeModal from './ReviewAnalyzeModal.vue';
  import ReviewImportModal from './ReviewImportModal.vue';
  import { columns, searchFormSchema } from './review.data';
  import { list, deleteReview, batchDeleteReview } from './review.api';

  const [registerModal, { openModal }] = useModal();
  const [registerAnalyzeModal, { openModal: openAnalyzeModal }] = useModal();
  const [registerImportModal, { openModal: openImportModal }] = useModal();
  const [registerDrawer, { openDrawer }] = useDrawer();

  const { tableContext } = useListPage({
    designScope: 'review-list',
    tableProps: {
      title: '评价列表',
      api: list,
      columns,
      formConfig: {
        schemas: searchFormSchema,
      },
      actionColumn: { width: 160 },
      beforeFetch: (params) => Object.assign({ column: 'createTime', order: 'desc' }, params),
    },
  });

  const [registerTable, { reload }, { rowSelection, selectedRowKeys }] = tableContext;

  function handleCreate() {
    openDrawer(true, { isUpdate: false, showFooter: true });
  }
  function handleImport() {
    openImportModal(true, {});
  }
  function handleEdit(record: Recordable) {
    openDrawer(true, { record, isUpdate: true, showFooter: true });
  }
  function handleDetail(record: Recordable) {
    openModal(true, { record });
  }
  function handleAnalyze(record: Recordable) {
    openAnalyzeModal(true, { record });
  }
  async function handleDelete(record) {
    await deleteReview({ id: record.id }, reload);
  }
  async function batchHandleDelete() {
    if (!selectedRowKeys.value.length) return;
    await batchDeleteReview({ ids: selectedRowKeys.value.join(',') }, () => {
      selectedRowKeys.value = [];
      reload();
    });
  }
  function handleSuccess() {
    reload();
  }
  function getTableAction(record): ActionItem[] {
    return [
      { label: '编辑', onClick: handleEdit.bind(null, record) },
      {
        label: '删除',
        color: 'error',
        popConfirm: { title: '是否确认删除', confirm: handleDelete.bind(null, record) },
      },
    ];
  }
  function getDropDownAction(record): ActionItem[] {
    return [
      { label: '详情', onClick: handleDetail.bind(null, record) },
      { label: '评价分析', onClick: handleAnalyze.bind(null, record) },
    ];
  }
</script>
