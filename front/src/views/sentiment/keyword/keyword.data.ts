import { BasicColumn, FormSchema } from '/@/components/Table';
import { h } from 'vue';
import { Tag } from 'ant-design-vue';
import { categoryOptions } from './keyword.api';

/** 与后端约定：通用关键词的 categoryId 哨兵值 */
export const GENERAL_CATEGORY_ID = '__general__';

export const columns: BasicColumn[] = [
  { title: '关键词', dataIndex: 'word', width: 140, align: 'left', resizable: true },
  { title: '方面', dataIndex: 'aspect', width: 110, resizable: true },
  {
    title: '类目',
    dataIndex: 'categoryLabel',
    width: 140,
    customRender: ({ text, record }) => {
      const label = text || record.categoryName || '通用';
      const general = !record.categoryId || record.categoryId === GENERAL_CATEGORY_ID || label === '通用';
      return h(Tag, { color: general ? 'default' : 'processing' }, () => label);
    },
  },
  { title: '同义词', dataIndex: 'alias', width: 180, align: 'left' },
  { title: '权重', dataIndex: 'weight', width: 70 },
  { title: '排序', dataIndex: 'sortNo', width: 70 },
  {
    title: '状态',
    dataIndex: 'status',
    width: 80,
    customRender: ({ text }) => {
      const on = text === 1 || text === '1';
      return h(Tag, { color: on ? 'success' : 'default' }, () => (on ? '启用' : '停用'));
    },
  },
  { title: '创建时间', dataIndex: 'createTime', width: 160 },
];

export const searchFormSchema: FormSchema[] = [
  { field: 'word', label: '关键词', component: 'Input', colProps: { span: 6 } },
  { field: 'aspect', label: '方面', component: 'Input', colProps: { span: 6 } },
  {
    field: 'categoryId',
    label: '类目',
    component: 'ApiSelect',
    colProps: { span: 6 },
    componentProps: {
      api: categoryOptions,
      allowClear: true,
      showSearch: true,
      optionFilterProp: 'label',
      placeholder: '全部',
      labelField: 'label',
      valueField: 'value',
      immediate: true,
    },
  },
  {
    field: 'status',
    label: '状态',
    component: 'Select',
    colProps: { span: 6 },
    componentProps: {
      allowClear: true,
      options: [
        { label: '启用', value: 1 },
        { label: '停用', value: 0 },
      ],
    },
  },
];

export const formSchema: FormSchema[] = [
  { field: 'id', label: 'id', component: 'Input', show: false },
  { field: 'word', label: '关键词', component: 'Input', required: true },
  {
    field: 'categoryId',
    label: '类目',
    component: 'ApiSelect',
    required: true,
    defaultValue: GENERAL_CATEGORY_ID,
    componentProps: {
      api: categoryOptions,
      showSearch: true,
      optionFilterProp: 'label',
      placeholder: '选择通用或具体类目',
      labelField: 'label',
      valueField: 'value',
      immediate: true,
    },
  },
  { field: 'categoryName', label: '类目名', component: 'Input', show: false },
  {
    field: 'aspect',
    label: '方面',
    component: 'Select',
    componentProps: {
      allowClear: true,
      showSearch: true,
      options: [
        { label: '质量', value: '质量' },
        { label: '物流', value: '物流' },
        { label: '价格', value: '价格' },
        { label: '外观', value: '外观' },
        { label: '服务', value: '服务' },
        { label: '体验', value: '体验' },
        { label: '性能', value: '性能' },
        { label: '其他', value: '其他' },
      ],
    },
  },
  {
    field: 'polarity',
    label: '极性',
    component: 'RadioButtonGroup',
    defaultValue: 'any',
    componentProps: {
      options: [
        { label: '不限', value: 'any' },
        { label: '正向', value: 'positive' },
        { label: '中性', value: 'neutral' },
        { label: '负向', value: 'negative' },
      ],
    },
  },
  { field: 'alias', label: '同义词', component: 'Input', componentProps: { placeholder: '逗号分隔，如：快递,配送' } },
  { field: 'weight', label: '权重', component: 'InputNumber', defaultValue: 1, componentProps: { min: 1, max: 100, style: { width: '100%' } } },
  { field: 'sortNo', label: '排序', component: 'InputNumber', defaultValue: 0, componentProps: { min: 0, style: { width: '100%' } } },
  {
    field: 'status',
    label: '状态',
    component: 'RadioButtonGroup',
    defaultValue: 1,
    componentProps: {
      options: [
        { label: '启用', value: 1 },
        { label: '停用', value: 0 },
      ],
    },
  },
  { field: 'remark', label: '备注', component: 'InputTextArea', componentProps: { rows: 2 } },
];
