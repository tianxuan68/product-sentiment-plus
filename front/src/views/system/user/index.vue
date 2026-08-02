<template>
  <div ref="pageRoot" class="user-page">
    <div class="user-page__atmosphere" aria-hidden="true"></div>
    <section class="user-page__intro">
      <div>
        <p class="user-page__eyebrow">PEOPLE · ACCESS · CARE</p>
        <h1>用户工作台</h1>
        <p class="user-page__subtitle">管理团队成员、访问权限与组织信息，让每一次协作都保持清晰。</p>
      </div>
      <div class="user-page__status" aria-label="系统状态正常">
        <span class="user-page__status-dot"></span>
        <span>系统运行正常</span>
      </div>
    </section>
    <section class="user-page__table">
      <!--引用表格-->
      <BasicTable @register="registerTable" :rowSelection="rowSelection">
        <!--插槽:table标题-->
        <template #tableTitle>
          <a-button type="primary" preIcon="ant-design:plus-outlined" @click="handleCreate"> 新增</a-button>
          <a-button type="primary" preIcon="ant-design:export-outlined" @click="onExportXls"> 导出</a-button>
          <!--        <j-upload-button type="primary" preIcon="ant-design:import-outlined" @click="onImportXls" v-auth="'system:user:import'">导入</j-upload-button>-->
          <import-excel-progress :upload-url="getImportUrl" @success="reload"></import-excel-progress>
          <a-button type="primary" @click="openModal(true, {})" preIcon="ant-design:hdd-outlined"> 回收站</a-button>
          <a-dropdown v-if="selectedRowKeys.length > 0">
            <template #overlay>
              <a-menu>
                <a-menu-item key="1" @click="batchHandleDelete">
                  <Icon icon="ant-design:delete-outlined"></Icon>
                  删除
                </a-menu-item>
                <a-menu-item key="2" @click="batchFrozen(2)">
                  <Icon icon="ant-design:lock-outlined"></Icon>
                  冻结
                </a-menu-item>
                <a-menu-item key="3" @click="batchFrozen(1)">
                  <Icon icon="ant-design:unlock-outlined"></Icon>
                  解冻
                </a-menu-item>
                <a-menu-item v-if="hasPermission('system:user:resetPassword')" key="4" @click="batchResetPassword()">
                  <Icon icon="ant-design:reload-outlined"></Icon>
                  重置密码
                </a-menu-item>
              </a-menu>
            </template>
            <a-button
              >批量操作
              <Icon icon="mdi:chevron-down"></Icon>
            </a-button>
          </a-dropdown>
        </template>
        <!--操作栏-->
        <template #action="{ record }">
          <TableAction :actions="getTableAction(record)" :dropDownActions="getDropDownAction(record)" />
        </template>
      </BasicTable>
    </section>
    <!--用户抽屉-->
    <UserDrawer @register="registerDrawer" @success="handleSuccess" />
    <!--修改密码-->
    <PasswordModal @register="registerPasswordModal" @success="reload" />
    <!--回收站-->
    <UserRecycleBinModal @register="registerModal" @success="reload" />
    <!-- 离职人员列弹窗 -->
    <UserQuitModal @register="registerQuitModal" @success="reload" />
  </div>
</template>

<script lang="ts" name="system-user" setup>
  //ts语法
  import { ref, computed, unref, nextTick, onBeforeUnmount, onMounted } from 'vue';
  import { BasicTable, TableAction, ActionItem } from '/@/components/Table';
  import UserDrawer from './UserDrawer.vue';
  import UserRecycleBinModal from './UserRecycleBinModal.vue';
  import PasswordModal from './PasswordModal.vue';
  import JThirdAppButton from '/@/components/jeecg/thirdApp/JThirdAppButton.vue';
  import UserQuitModal from './UserQuitModal.vue';
  import { useDrawer } from '/@/components/Drawer';
  import { useListPage } from '/@/hooks/system/useListPage';
  import { useModal } from '/@/components/Modal';
  import { useMessage } from '/@/hooks/web/useMessage';
  import { columns, searchFormSchema } from './user.data';
  import { listNoCareTenant, deleteUser, batchDeleteUser, getImportUrl, getExportUrl, frozenBatch, resetPassword } from './user.api';
  import { usePermission } from '/@/hooks/web/usePermission';
  import ImportExcelProgress from './components/ImportExcelProgress.vue';

  const pageRoot = ref<HTMLElement | null>(null);
  let entranceContext: { revert: () => void } | undefined;

  const { createMessage, createConfirm } = useMessage();
  const { isDisabledAuth, hasPermission } = usePermission();

  //注册drawer
  const [registerDrawer, { openDrawer }] = useDrawer();
  //回收站model
  const [registerModal, { openModal }] = useModal();
  //密码model
  const [registerPasswordModal, { openModal: openPasswordModal }] = useModal();
  //代理人model
  const [registerAgentModal, { openModal: openAgentModal }] = useModal();
  //离职代理人model
  const [registerQuitAgentModal, { openModal: openQuitAgentModal }] = useModal();
  //离职用户列表model
  const [registerQuitModal, { openModal: openQuitModal }] = useModal();

  // 列表页面公共参数、方法
  const { prefixCls, tableContext, onExportXls, onImportXls } = useListPage({
    designScope: 'user-list',
    tableProps: {
      title: '用户列表',
      api: listNoCareTenant,
      columns: columns,
      canResize: true,
      size: 'small',
      formConfig: {
        // labelWidth: 200,
        schemas: searchFormSchema,
      },
      actionColumn: {
        width: 120,
      },
      beforeFetch: (params) => {
        return Object.assign({ column: 'createTime', order: 'desc' }, params);
      },
      defSort: {
        column: '',
        order: '',
      },
    },
    exportConfig: {
      name: '用户列表',
      url: getExportUrl,
    },
    importConfig: {
      url: getImportUrl,
    },
  });

  onMounted(async () => {
    document.body.classList.add('user-page-theme');
    await nextTick();
    const engine = window.gsap;
    if (!engine || window.matchMedia('(prefers-reduced-motion: reduce)').matches || !pageRoot.value) return;

    entranceContext = engine.context(() => {
      engine.from('.user-page__intro', { y: 12, autoAlpha: 0, duration: 0.45, ease: 'power2.out' });
      engine.from('.user-page__table', { y: 16, autoAlpha: 0, duration: 0.6, delay: 0.06, ease: 'power2.out' });
    }, pageRoot.value);
  });

  onBeforeUnmount(() => {
    entranceContext?.revert();
    document.body.classList.remove('user-page-theme');
  });

  //注册table数据
  const [registerTable, { reload, updateTableDataRecord, clearSelectedRowKeys }, { rowSelection, selectedRows, selectedRowKeys }] = tableContext;

  /**
   * 新增事件
   */
  function handleCreate() {
    openDrawer(true, {
      isUpdate: false,
      showFooter: true,
      tenantSaas: false,
    });
  }
  /**
   * 编辑事件
   */
  async function handleEdit(record: Recordable) {
    openDrawer(true, {
      record,
      isUpdate: true,
      showFooter: true,
      tenantSaas: false,
    });
  }
  /**
   * 详情
   */
  async function handleDetail(record: Recordable) {
    openDrawer(true, {
      record,
      isUpdate: true,
      showFooter: false,
      tenantSaas: false,
    });
  }
  /**
   * 删除事件
   */
  async function handleDelete(record) {
    if ('admin' == record.username) {
      createMessage.warning('管理员账号不允许此操作！');
      return;
    }
    await deleteUser({ id: record.id }, reload);
  }
  /**
   * 批量删除事件
   */
  async function batchHandleDelete() {
    let hasAdmin = unref(selectedRows).filter((item) => item.username == 'admin');
    if (unref(hasAdmin).length > 0) {
      createMessage.warning('管理员账号不允许此操作！');
      return;
    }
    await batchDeleteUser({ ids: selectedRowKeys.value }, () => {
      selectedRowKeys.value = [];
      reload();
    });
  }
  /**
   * 成功回调
   */
  function handleSuccess() {
    reload();
  }

  /**
   * 打开修改密码弹窗
   */
  function handleChangePassword(username) {
    openPasswordModal(true, { username });
  }
  /**
   * 冻结解冻
   */
  async function handleFrozen(record, status) {
    if ('admin' == record.username) {
      createMessage.warning('管理员账号不允许此操作！');
      return;
    }
    await frozenBatch({ ids: record.id, status: status }, reload);
  }
  /**
   * 批量冻结解冻
   */
  function batchFrozen(status) {
    let hasAdmin = selectedRows.value.filter((item) => item.username == 'admin');
    if (unref(hasAdmin).length > 0) {
      createMessage.warning('管理员账号不允许此操作！');
      return;
    }
    createConfirm({
      iconType: 'warning',
      title: '确认操作',
      content: '是否' + (status == 1 ? '解冻' : '冻结') + '选中账号?',
      onOk: async () => {
        await frozenBatch({ ids: unref(selectedRowKeys).join(','), status: status }, reload);
      },
    });
  }
  /**
   * 批量重置密码
   */
  function batchResetPassword() {
    let hasAdmin = selectedRows.value.filter((item) => item.username == 'admin');
    if (unref(hasAdmin).length > 0) {
      createMessage.warning('所选用户中包含管理员，管理员账号不允许重置密码！！');
      return;
    }
    if (selectedRows.value.length > 0) {
      createConfirm({
        iconType: 'warning',
        title: '确认操作',
        content: '是否重置选中的账号密码?',
        onOk: async () => {
          const usernames = selectedRows.value.map((item) => item.username).join(',');
          await resetPassword({ usernames: usernames }, () => {
            reload();
            clearSelectedRowKeys();
          });
        },
      });
    }
  }

  /**
   *同步钉钉和微信回调
   */
  function onSyncFinally({ isToLocal }) {
    // 同步到本地时刷新下数据
    if (isToLocal) {
      reload();
    }
  }

  /**
   * 操作栏
   */
  function getTableAction(record): ActionItem[] {
    return [
      {
        label: '编辑',
        onClick: handleEdit.bind(null, record),
        // ifShow: () => hasPermission('system:user:edit'),
      },
    ];
  }
  /**
   * 下拉操作栏
   */
  function getDropDownAction(record): ActionItem[] {
    return [
      {
        label: '详情',
        onClick: handleDetail.bind(null, record),
      },
      {
        label: '密码',
        //auth: 'user:changepwd',
        onClick: handleChangePassword.bind(null, record.username),
      },
      {
        label: '删除',
        popConfirm: {
          title: '是否确认删除',
          confirm: handleDelete.bind(null, record),
        },
      },
      {
        label: '冻结',
        ifShow: record.status == 1,
        popConfirm: {
          title: '确定冻结吗?',
          confirm: handleFrozen.bind(null, record, 2),
        },
      },
      {
        label: '解冻',
        ifShow: record.status == 2,
        popConfirm: {
          title: '确定解冻吗?',
          confirm: handleFrozen.bind(null, record, 1),
        },
      },
    ];
  }
</script>

<style lang="less" scoped>
  .user-page {
    --user-page: #e4f3f0;
    --user-surface: #fbfdfc;
    --user-surface-soft: #edf8f5;
    --user-border: rgba(31, 102, 101, 0.12);
    --user-border-strong: rgba(31, 102, 101, 0.22);
    --user-ink: #193c3c;
    --user-ink-soft: #527171;
    --user-accent: #247b7a;
    --user-accent-deep: #185c5d;
    --user-shadow: 0 16px 34px rgba(28, 97, 94, 0.08);
    position: relative;
    min-height: calc(100vh - 112px);
    padding: 26px 28px 34px;
    overflow: hidden;
    color: var(--user-ink);
    background: var(--user-page);
    border: 1px solid rgba(31, 102, 101, 0.08);
    border-radius: 20px;
  }

  .user-page__atmosphere {
    position: absolute;
    inset: 0;
    pointer-events: none;
    background:
      radial-gradient(circle at 92% 4%, rgba(255, 255, 255, 0.78), transparent 28%),
      radial-gradient(circle at 4% 94%, rgba(201, 148, 94, 0.08), transparent 25%);
  }

  .user-page__intro,
  .user-page__table {
    position: relative;
    z-index: 1;
  }

  .user-page__intro {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 24px;
    max-width: 1640px;
    margin: 0 auto 22px;
  }

  .user-page__eyebrow {
    margin: 0 0 8px;
    color: var(--user-accent);
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.16em;
  }

  .user-page__intro h1 {
    margin: 0;
    color: var(--user-ink);
    font-size: 27px;
    font-weight: 700;
    letter-spacing: -0.035em;
    line-height: 1.15;
  }

  .user-page__subtitle {
    margin: 9px 0 0;
    color: var(--user-ink-soft);
    font-size: 14px;
    line-height: 1.6;
  }

  .user-page__status {
    display: inline-flex;
    align-items: center;
    gap: 9px;
    flex: none;
    padding: 9px 13px;
    color: var(--user-accent-deep);
    font-size: 12px;
    font-weight: 600;
    background: rgba(251, 253, 252, 0.78);
    border: 1px solid var(--user-border);
    border-radius: 999px;
    box-shadow: 0 5px 14px rgba(28, 97, 94, 0.05);
  }

  .user-page__status-dot {
    width: 7px;
    height: 7px;
    background: #55a47c;
    border-radius: 50%;
    box-shadow: 0 0 0 4px rgba(85, 164, 124, 0.13);
  }

  .user-page__table {
    max-width: 1640px;
    margin: 0 auto;
    padding: 5px;
    background: rgba(251, 253, 252, 0.68);
    border: 1px solid var(--user-border);
    border-radius: 16px;
    box-shadow: var(--user-shadow);
  }

  .user-page__table :deep(.ant-card),
  .user-page__table :deep(.ant-table-wrapper) {
    color: var(--user-ink);
    background: var(--user-surface);
    border-radius: 12px;
  }

  .user-page__table :deep(.ant-card) {
    border-color: transparent;
    box-shadow: none;
  }

  .user-page__table :deep(.ant-card-head) {
    min-height: 58px;
    padding: 0 18px;
    border-bottom: 1px solid var(--user-border);
  }

  .user-page__table :deep(.ant-card-head-title) {
    color: var(--user-ink);
    font-weight: 700;
  }

  .user-page__table :deep(.ant-form-item-label > label),
  .user-page__table :deep(.ant-table-thead > tr > th) {
    color: var(--user-ink-soft);
    font-size: 12px;
    font-weight: 600;
  }

  .user-page__table :deep(.ant-table-thead > tr > th) {
    background: var(--user-surface-soft);
    border-bottom-color: var(--user-border);
  }

  .user-page__table :deep(.ant-table-tbody > tr > td) {
    color: #315656;
    border-bottom-color: rgba(31, 102, 101, 0.08);
  }

  .user-page__table :deep(.ant-table-tbody > tr:hover > td) {
    background: #f0faf7;
  }

  .user-page__table :deep(.ant-input),
  .user-page__table :deep(.ant-select-selector),
  .user-page__table :deep(.ant-picker) {
    color: var(--user-ink);
    background: #f7fbfa;
    border-color: var(--user-border-strong);
    border-radius: 9px;
  }

  .user-page__table :deep(.ant-input:focus),
  .user-page__table :deep(.ant-input-focused),
  .user-page__table :deep(.ant-select-focused .ant-select-selector) {
    border-color: var(--user-accent);
    box-shadow: 0 0 0 3px rgba(36, 123, 122, 0.12);
  }

  .user-page__table :deep(.ant-btn-primary) {
    color: #f7fffd;
    background: var(--user-accent);
    border-color: var(--user-accent);
    border-radius: 9px;
    box-shadow: 0 5px 12px rgba(36, 123, 122, 0.16);
  }

  .user-page__table :deep(.ant-btn-primary:hover),
  .user-page__table :deep(.ant-btn-primary:focus) {
    background: var(--user-accent-deep);
    border-color: var(--user-accent-deep);
  }

  .user-page__table :deep(.ant-btn:not(.ant-btn-primary)) {
    color: var(--user-accent-deep);
    border-color: var(--user-border-strong);
    border-radius: 9px;
  }

  .user-page__table :deep(.ant-pagination-item-active) {
    border-color: var(--user-accent);
  }

  .user-page__table :deep(.ant-pagination-item-active a) {
    color: var(--user-accent-deep);
  }

  @media (max-width: 768px) {
    .user-page {
      min-height: calc(100vh - 88px);
      padding: 18px 14px 24px;
      border-radius: 14px;
    }

    .user-page__intro {
      align-items: flex-start;
      flex-direction: column;
      gap: 14px;
      margin-bottom: 16px;
    }

    .user-page__intro h1 {
      font-size: 23px;
    }

    .user-page__table {
      padding: 3px;
      overflow-x: auto;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .user-page__intro,
    .user-page__table {
      animation: none !important;
    }
  }

  // The surrounding shell needs to share the page's palette; otherwise the
  // content card reads as an isolated skin over the original blue/white shell.
  :global(body.user-page-theme .ant-layout-header) {
    background: #fbfdfb !important;
    border-bottom: 1px solid rgba(31, 102, 101, 0.12) !important;
  }

  :global(body.user-page-theme .ant-layout-sider) {
    background: #e7f3f0 !important;
    border-right: 1px solid rgba(31, 102, 101, 0.12);
  }

  :global(body.user-page-theme .ant-layout-sider .ant-menu) {
    background: transparent !important;
  }

  :global(body.user-page-theme .ant-layout-sider .ant-menu-item) {
    color: #416667;
  }

  :global(body.user-page-theme .ant-layout-sider .ant-menu-item:hover) {
    color: #1f7473 !important;
    background: #dff1ed !important;
  }

  :global(body.user-page-theme .ant-layout-sider .ant-menu-item-selected) {
    color: #1f7473 !important;
    background: #cfe9e4 !important;
    border-right: 3px solid #247b7a;
  }

  :global(body.user-page-theme .ant-layout-content) {
    background: #e4f3f0 !important;
  }

  :global(body.user-page-theme .ant-tabs-nav) {
    background: #f5fbf9 !important;
    border-bottom: 1px solid rgba(31, 102, 101, 0.12) !important;
  }

  :global(body.user-page-theme .ant-tabs-tab-active .ant-tabs-tab-btn),
  :global(body.user-page-theme .ant-tabs-tab:hover) {
    color: #247b7a !important;
  }

  :global(body.user-page-theme .ant-tabs-ink-bar) {
    background: #247b7a !important;
  }
</style>
