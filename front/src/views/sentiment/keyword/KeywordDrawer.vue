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
  import { formSchema, GENERAL_CATEGORY_ID } from './keyword.data';
  import { categoryOptions, saveOrUpdateKeyword } from './keyword.api';

  const emit = defineEmits(['success', 'register']);
  const { adaptiveWidth } = useDrawerAdaptiveWidth();
  const isUpdate = ref(true);
  const showFooter = ref(true);
  const categoryMap = ref<Record<string, string>>({});

  const [registerForm, { setProps, resetFields, setFieldsValue, validate }] = useForm({
    labelCol: { md: { span: 4 }, sm: { span: 6 } },
    wrapperCol: { md: { span: 20 }, sm: { span: 18 } },
    schemas: formSchema,
    showActionButtonGroup: false,
  });

  async function loadCategoryMap() {
    const options = await categoryOptions();
    const map: Record<string, string> = {};
    options.forEach((o) => {
      map[o.value] = o.name || o.label;
    });
    categoryMap.value = map;
  }

  const [registerDrawer, { setDrawerProps, closeDrawer }] = useDrawerInner(async (data) => {
    await resetFields();
    await loadCategoryMap();
    showFooter.value = data?.showFooter !== false;
    setDrawerProps({ confirmLoading: false, showFooter: showFooter.value });
    isUpdate.value = !!data?.isUpdate;
    if (typeof data?.record === 'object') {
      const rec = data.record;
      const categoryId =
        !rec.categoryId || rec.categoryId === GENERAL_CATEGORY_ID ? GENERAL_CATEGORY_ID : rec.categoryId;
      await setFieldsValue({
        ...rec,
        categoryId,
        polarity: rec.polarity || 'any',
        status: rec.status ?? 1,
      });
    } else {
      await setFieldsValue({ categoryId: GENERAL_CATEGORY_ID, polarity: 'any', status: 1 });
    }
    setProps({ disabled: !showFooter.value });
  });

  const getTitle = computed(() => (!unref(isUpdate) ? '新增关键词' : '编辑关键词'));

  async function handleSubmit() {
    try {
      const values = await validate();
      const categoryId = values.categoryId || GENERAL_CATEGORY_ID;
      values.categoryName =
        categoryId === GENERAL_CATEGORY_ID ? '' : categoryMap.value[categoryId] || values.categoryName || '';
      setDrawerProps({ confirmLoading: true });
      await saveOrUpdateKeyword(values, unref(isUpdate));
      closeDrawer();
      emit('success');
    } finally {
      setDrawerProps({ confirmLoading: false });
    }
  }
</script>
