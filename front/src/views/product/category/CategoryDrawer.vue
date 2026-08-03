<template>
  <BasicDrawer v-bind="$attrs" @register="registerDrawer" showFooter :width="adaptiveWidth" :title="getTitle" @ok="handleSubmit">
    <BasicForm @register="registerForm" />
  </BasicDrawer>
</template>
<script lang="ts" setup>
  import { computed, ref, unref, useAttrs } from 'vue';
  import { BasicForm, useForm } from '/@/components/Form/index';
  import { BasicDrawer, useDrawerInner } from '/@/components/Drawer';
  import { useDrawerAdaptiveWidth } from '/@/hooks/jeecg/useAdaptiveWidth';
  import { formSchema } from './category.data';
  import { saveOrUpdateCategory, treeList } from './category.api';

  const emit = defineEmits(['success', 'register']);
  const { adaptiveWidth } = useDrawerAdaptiveWidth();
  const attrs = useAttrs();
  const isUpdate = ref(true);

  const [registerForm, { setProps, resetFields, setFieldsValue, updateSchema, validate }] = useForm({
    labelCol: {
      md: { span: 4 },
      sm: { span: 6 },
    },
    wrapperCol: {
      md: { span: 20 },
      sm: { span: 18 },
    },
    schemas: formSchema,
    showActionButtonGroup: false,
  });

  const [registerDrawer, { setDrawerProps, closeDrawer }] = useDrawerInner(async (data) => {
    await resetFields();
    setDrawerProps({ confirmLoading: false });
    isUpdate.value = !!data?.isUpdate;

    const treeData = await treeList();
    updateSchema([
      {
        field: 'parentId',
        componentProps: {
          treeData: filterSelf(treeData, data?.record?.id),
          allowClear: true,
          placeholder: '不选则为一级类目',
          fieldNames: { label: 'name', key: 'id', value: 'id' },
        },
      },
    ]);

    if (typeof data?.record === 'object') {
      await setFieldsValue({
        ...data.record,
        parentId: data.record.parentId || undefined,
        status: data.record.status ?? 1,
      });
    }
    setProps({ disabled: !attrs.showFooter });
  });

  const getTitle = computed(() => (!unref(isUpdate) ? '新增类目' : '编辑类目'));

  /** 编辑时不可选自己及子孙为上级 */
  function filterSelf(tree: any[], selfId?: string) {
    if (!selfId || !tree?.length) return tree || [];
    return tree
      .filter((item) => item.id !== selfId)
      .map((item) => ({
        ...item,
        children: item.children?.length ? filterSelf(item.children, selfId) : undefined,
      }));
  }

  async function handleSubmit() {
    try {
      const values = await validate();
      setDrawerProps({ confirmLoading: true });
      if (!values.parentId) {
        values.parentId = '';
      }
      await saveOrUpdateCategory(values, unref(isUpdate));
      closeDrawer();
      emit('success');
    } finally {
      setDrawerProps({ confirmLoading: false });
    }
  }
</script>
