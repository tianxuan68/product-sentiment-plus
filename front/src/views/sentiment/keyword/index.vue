<template>
  <div>
    <BasicTable @register="registerTable" :rowSelection="rowSelection">
      <template #tableTitle>
        <a-button type="primary" preIcon="ant-design:plus-outlined" @click="handleCreate"> 新增</a-button>
        <a-dropdown v-if="selectedRowKeys.length > 0">
          <template #overlay>
            <a-menu>
              <a-menu-item key="1" @click="batchHandleDelete">
                <Icon icon="ant-design:delete-outlined" />
                删除
              </a-menu-item>
            </a-menu>
          </template>
          <a-button>
            批量操作
            <Icon icon="mdi:chevron-down" />
          </a-button>
        </a-dropdown>
      </template>
      <template #action="{ record }">
        <TableAction :actions="getTableAction(record)" :dropDownActions="getDropDownAction(record)" />
      </template>
    </BasicTable>
    <KeywordDrawer @register="registerDrawer" @success="handleSuccess" />
  </div>
</template>
<script lang="ts" name="sentiment-keyword" setup>
  import { BasicTable, TableAction, ActionItem } from '/@/components/Table';
  import { useDrawer } from '/@/components/Drawer';
  import { useListPage } from '/@/hooks/system/useListPage';
  import { Icon } from '/@/components/Icon';
  import KeywordDrawer from './KeywordDrawer.vue';
  import { columns, searchFormSchema } from './keyword.data';
  import { list, deleteKeyword, batchDeleteKeyword } from './keyword.api';

  const [registerDrawer, { openDrawer }] = useDrawer();

  const { tableContext } = useListPage({
    designScope: 'keyword-list',
    tableProps: {
      title: '关键词列表',
      api: list,
      columns,
      formConfig: {
        schemas: searchFormSchema,
      },
      actionColumn: { width: 120 },
      beforeFetch: (params) => Object.assign({ column: 'sortNo', order: 'asc' }, params),
    },
  });

  const [registerTable, { reload }, { rowSelection, selectedRowKeys }] = tableContext;

  function handleCreate() {
    openDrawer(true, { isUpdate: false, showFooter: true });
  }
  function handleEdit(record: Recordable) {
    openDrawer(true, { record, isUpdate: true, showFooter: true });
  }
  function handleDetail(record: Recordable) {
    openDrawer(true, { record, isUpdate: true, showFooter: false });
  }
  async function handleDelete(record) {
    await deleteKeyword({ id: record.id }, reload);
  }
  async function batchHandleDelete() {
    await batchDeleteKeyword({ ids: selectedRowKeys.value.join(',') }, () => {
      selectedRowKeys.value = [];
      reload();
    });
  }
  function handleSuccess() {
    reload();
  }
  function getTableAction(record): ActionItem[] {
    return [{ label: '编辑', onClick: handleEdit.bind(null, record) }];
  }
  function getDropDownAction(record): ActionItem[] {
    return [
      { label: '详情', onClick: handleDetail.bind(null, record) },
      {
        label: '删除',
        popConfirm: { title: '是否确认删除', confirm: handleDelete.bind(null, record) },
      },
    ];
  }
</script>
