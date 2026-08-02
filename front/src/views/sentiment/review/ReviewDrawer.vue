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
  import { formSchema } from './review.data';
  import { keywordOptions, productOptions, saveOrUpdateReview } from './review.api';

  const emit = defineEmits(['success', 'register']);
  const { adaptiveWidth } = useDrawerAdaptiveWidth();
  const isUpdate = ref(true);
  const showFooter = ref(true);
  const productMap = ref<Recordable>({});

  const [registerForm, { setProps, resetFields, setFieldsValue, getFieldsValue, updateSchema, validate }] = useForm({
    labelCol: { md: { span: 4 }, sm: { span: 6 } },
    wrapperCol: { md: { span: 20 }, sm: { span: 18 } },
    schemas: formSchema,
    showActionButtonGroup: false,
  });

  async function reloadKeywordOptions(categoryId?: string, categoryName?: string) {
    const options = await keywordOptions({
      categoryId: categoryId || undefined,
      categoryName: categoryName || undefined,
    });
    await updateSchema({
      field: 'keywords',
      componentProps: {
        mode: 'multiple',
        allowClear: true,
        showSearch: true,
        optionFilterProp: 'label',
        placeholder: categoryId || categoryName ? '从通用+该类目关键词中多选' : '从关键词表多选（建议先选商品）',
        options: options || [],
        maxTagCount: 6,
      },
    });
  }

  function parseKeywords(record: Recordable): string[] {
    if (Array.isArray(record.keywords)) {
      return record.keywords.map((x) => String(x).trim()).filter(Boolean);
    }
    const raw = record.keywordsText || record.keywords || '';
    if (!raw) return [];
    if (typeof raw === 'string') {
      const text = raw.trim();
      if (text.startsWith('[')) {
        try {
          const arr = JSON.parse(text);
          if (Array.isArray(arr)) return arr.map((x) => String(x).trim()).filter(Boolean);
        } catch {
          /* ignore */
        }
      }
      return text
        .replace(/、/g, ',')
        .split(',')
        .map((x) => x.trim())
        .filter(Boolean);
    }
    return [];
  }

  const [registerDrawer, { setDrawerProps, closeDrawer }] = useDrawerInner(async (data) => {
    await resetFields();
    showFooter.value = data?.showFooter !== false;
    setDrawerProps({ confirmLoading: false, showFooter: showFooter.value });
    isUpdate.value = !!data?.isUpdate;

    const options = await productOptions();
    productMap.value = Object.fromEntries(options.map((o) => [o.value, o]));
    await updateSchema([
      {
        field: 'productId',
        componentProps: {
          options,
          allowClear: true,
          showSearch: true,
          optionFilterProp: 'label',
          placeholder: '请选择商品（可选）',
          onChange: async (val: string) => {
            const hit = productMap.value[val];
            if (hit) {
              await setFieldsValue({
                productName: hit.name,
                categoryId: hit.categoryId || '',
                categoryName: hit.categoryName || '',
              });
              await reloadKeywordOptions(hit.categoryId, hit.categoryName);
            } else {
              await setFieldsValue({ categoryId: '', categoryName: '' });
              await reloadKeywordOptions();
            }
          },
        },
      },
    ]);

    if (typeof data?.record === 'object') {
      const record = { ...data.record };
      const keywords = parseKeywords(record);
      await setFieldsValue({
        ...record,
        keywords,
        sentiment: record.sentiment || 'neutral',
        score: record.score ?? 60,
      });
      await reloadKeywordOptions(record.categoryId, record.categoryName);
    } else {
      await setFieldsValue({ sentiment: 'neutral', score: 60, keywords: [] });
      await reloadKeywordOptions();
    }
    setProps({ disabled: !showFooter.value });
  });

  const getTitle = computed(() => (!unref(isUpdate) ? '新增评价' : '编辑评价'));

  async function handleSubmit() {
    try {
      const values = await validate();
      const form = getFieldsValue();
      const payload = {
        ...values,
        categoryId: values.categoryId || form.categoryId || undefined,
        keywords: Array.isArray(values.keywords) ? values.keywords : [],
      };
      setDrawerProps({ confirmLoading: true });
      await saveOrUpdateReview(payload, unref(isUpdate));
      closeDrawer();
      emit('success');
    } finally {
      setDrawerProps({ confirmLoading: false });
    }
  }
</script>
