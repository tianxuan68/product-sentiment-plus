<template>
  <div>
    <BasicTable @register="registerTable" :rowSelection="rowSelection">
      <template #tableTitle>
        <a-button type="primary" preIcon="ant-design:plus-outlined" @click="handleCreate"> 新增类目</a-button>
        <a-button type="primary" preIcon="ic:round-expand" @click="expandAll">展开全部</a-button>
        <a-button type="primary" preIcon="ic:round-compress" @click="collapseAll">折叠全部</a-button>

        <a-dropdown v-if="checkedKeys.length > 0">
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
            <Icon icon="ant-design:down-outlined" />
          </a-button>
        </a-dropdown>
      </template>
      <template #action="{ record }">
        <TableAction :actions="getTableAction(record)" :dropDownActions="getDropDownAction(record)" />
      </template>
    </BasicTable>
    <CategoryDrawer @register="registerDrawer" @success="handleSuccess" :showFooter="showFooter" />
  </div>
</template>
<script lang="ts" name="product-category" setup>
  import { nextTick, ref } from 'vue';
  import { BasicTable, TableAction } from '/@/components/Table';
  import { useListPage } from '/@/hooks/system/useListPage';
  import { useDrawer } from '/@/components/Drawer';
  import { Icon } from '/@/components/Icon';
  import CategoryDrawer from './CategoryDrawer.vue';
  import { columns, searchFormSchema } from './category.data';
  import { list, deleteCategory, batchDeleteCategory } from './category.api';

  const checkedKeys = ref<Array<string | number>>([]);
  const showFooter = ref(true);
  const [registerDrawer, { openDrawer }] = useDrawer();

  const { tableContext } = useListPage({
    tableProps: {
      title: '类目列表',
      api: list,
      columns,
      pagination: false,
      isTreeTable: true,
      formConfig: {
        schemas: searchFormSchema,
      },
      actionColumn: {
        width: 120,
      },
      afterFetch: (data) => {
        nextTick(() => expandAll());
        return data;
      },
    },
  });

  const [registerTable, { reload, expandAll, collapseAll }] = tableContext;

  const rowSelection = {
    type: 'checkbox',
    columnWidth: 30,
    selectedRowKeys: checkedKeys,
    onChange: onSelectChange,
  };

  function onSelectChange(selectedRowKeys: (string | number)[]) {
    checkedKeys.value = selectedRowKeys;
  }

  function handleCreate() {
    showFooter.value = true;
    openDrawer(true, { isUpdate: false });
  }

  function handleEdit(record) {
    showFooter.value = true;
    openDrawer(true, { record, isUpdate: true });
  }

  function handleAddSub(record) {
    showFooter.value = true;
    openDrawer(true, {
      record: { parentId: record.id, status: 1, sortNo: 0 },
      isUpdate: false,
    });
  }

  async function handleDelete(record) {
    await deleteCategory({ id: record.id }, reload);
  }

  async function batchHandleDelete() {
    await batchDeleteCategory({ ids: checkedKeys.value.join(',') }, () => {
      reload();
      checkedKeys.value = [];
    });
  }

  function handleSuccess() {
    reload();
  }

  function getTableAction(record) {
    return [
      {
        label: '编辑',
        onClick: handleEdit.bind(null, record),
      },
    ];
  }

  function getDropDownAction(record) {
    return [
      {
        label: '添加下级',
        onClick: handleAddSub.bind(null, record),
      },
      {
        label: '删除',
        color: 'error',
        popConfirm: {
          title: '是否确认删除（含下级）',
          confirm: handleDelete.bind(null, record),
        },
      },
    ];
  }
</script>
