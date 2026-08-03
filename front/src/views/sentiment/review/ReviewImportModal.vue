<template>
  <BasicModal
    v-bind="$attrs"
    @register="registerModal"
    title="导入评价数据"
    :okText="'开始导入'"
    :okButtonProps="{ disabled: !fileList.length }"
    @ok="handleOk"
    width="560px"
  >
    <a-alert type="info" show-icon class="mb-3">
      <template #message>
        请先下载模板，按模板表头填写后再上传。仅支持 <b>.csv</b> 文件（可用 Excel 打开编辑后另存为 CSV）。
      </template>
    </a-alert>

    <div class="mb-3">
      <a-button type="link" preIcon="ant-design:download-outlined" @click="handleDownloadTemplate"> 下载导入模板 </a-button>
    </div>

    <a-upload-dragger
      v-model:fileList="fileList"
      :beforeUpload="beforeUpload"
      :maxCount="1"
      accept=".csv,.txt"
      :multiple="false"
    >
      <p class="ant-upload-drag-icon">
        <InboxOutlined />
      </p>
      <p class="ant-upload-text">点击或拖拽 CSV 文件到此处</p>
      <p class="ant-upload-hint">上传前会校验扩展名与模板表头是否一致</p>
    </a-upload-dragger>
  </BasicModal>
</template>
<script lang="ts" setup>
  import { ref } from 'vue';
  import { InboxOutlined } from '@ant-design/icons-vue';
  import type { UploadProps } from 'ant-design-vue';
  import { BasicModal, useModalInner } from '/@/components/Modal';
  import { useMessage } from '/@/hooks/web/useMessage';
  import { downloadImportTemplate, importReviews } from './review.api';

  const emit = defineEmits(['success', 'register']);
  const { createMessage, createConfirm } = useMessage();
  const fileList = ref<UploadProps['fileList']>([]);
  const pendingFile = ref<File | null>(null);

  const [registerModal, { setModalProps, closeModal }] = useModalInner(async () => {
    fileList.value = [];
    pendingFile.value = null;
    setModalProps({ confirmLoading: false });
    createConfirm({
      iconType: 'info',
      title: '导入前请先下载模板',
      content: '请使用官方模板填写评价数据。表头必须与模板完全一致，否则无法解析。',
      okText: '下载模板',
      cancelText: '我已知晓',
      onOk: async () => {
        await handleDownloadTemplate();
      },
    });
  });

  async function handleDownloadTemplate() {
    try {
      await downloadImportTemplate();
      createMessage.success('模板已开始下载');
    } catch (e: any) {
      createMessage.error(e?.message || '模板下载失败');
    }
  }

  const beforeUpload: UploadProps['beforeUpload'] = (file) => {
    const name = String(file.name || '').toLowerCase();
    if (!(name.endsWith('.csv') || name.endsWith('.txt'))) {
      createMessage.error('文件格式不正确，请上传 CSV 模板文件（.csv）');
      return false;
    }
    pendingFile.value = file as File;
    fileList.value = [
      {
        uid: String(file.uid || Date.now()),
        name: file.name,
        status: 'done',
        originFileObj: file as any,
      },
    ];
    return false;
  };

  async function handleOk() {
    if (!pendingFile.value) {
      createMessage.warning('请先选择要上传的 CSV 文件');
      return;
    }
    try {
      setModalProps({ confirmLoading: true });
      const data = await importReviews(pendingFile.value);
      const fail = data?.failCount || 0;
      if (fail) {
        const errs = (data?.errors || []).slice(0, 3).join('；');
        createMessage.warning(`导入完成：成功 ${data?.successCount || 0} 条，失败 ${fail} 条。${errs}`);
      } else {
        createMessage.success(`成功导入 ${data?.successCount || 0} 条评价`);
      }
      closeModal();
      emit('success');
    } catch (e: any) {
      createMessage.error(e?.message || '导入失败，请确认文件为模板格式');
    } finally {
      setModalProps({ confirmLoading: false });
    }
  }
</script>
<style lang="less" scoped>
  .mb-3 {
    margin-bottom: 12px;
  }
</style>
