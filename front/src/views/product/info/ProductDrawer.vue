<template>
  <BasicDrawer v-bind="$attrs" @register="registerDrawer" showFooter :width="adaptiveWidth" :title="getTitle" @ok="handleSubmit">
    <BasicForm @register="registerForm" />
  </BasicDrawer>
</template>
<script lang="ts" setup>
  import { computed, ref, unref } from 'vue';
  import { BasicForm, useForm } from '/@/components/Form/index';
  import { BasicDrawer, useDrawerInner } from '/@/components/Drawer';
  import { useDrawerAdaptiveWidth } from '/@/hooks/jeecg/useAdaptiveWidth';
  import { formSchema } from './product.data';
  import { categoryTree, saveOrUpdateProduct } from './product.api';

  const emit = defineEmits(['success', 'register']);
  const { adaptiveWidth } = useDrawerAdaptiveWidth();
  const isUpdate = ref(true);
  const showFooter = ref(true);

  const [registerForm, { setProps, resetFields, setFieldsValue, updateSchema, validate }] = useForm({
    labelCol: { md: { span: 4 }, sm: { span: 6 } },
    wrapperCol: { md: { span: 20 }, sm: { span: 18 } },
    schemas: formSchema,
    showActionButtonGroup: false,
  });

  const [registerDrawer, { setDrawerProps, closeDrawer }] = useDrawerInner(async (data) => {
    await resetFields();
    showFooter.value = data?.showFooter !== false;
    setDrawerProps({ confirmLoading: false, showFooter: showFooter.value });
    isUpdate.value = !!data?.isUpdate;

    const treeData = await categoryTree();
    updateSchema([{ field: 'categoryId', componentProps: { treeData } }]);

    if (typeof data?.record === 'object') {
      await setFieldsValue({ ...data.record, status: data.record.status ?? 1 });
    }
    setProps({ disabled: !showFooter.value });
  });

  const getTitle = computed(() => (!unref(isUpdate) ? '新增商品' : '编辑商品'));

  async function handleSubmit() {
    try {
      const values = await validate();
      setDrawerProps({ confirmLoading: true });
      await saveOrUpdateProduct(values, unref(isUpdate));
      closeDrawer();
      emit('success');
    } finally {
      setDrawerProps({ confirmLoading: false });
    }
  }
</script>
