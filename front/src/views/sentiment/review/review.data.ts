import { BasicColumn, FormSchema } from '/@/components/Table';
import { h } from 'vue';
import { Tag } from 'ant-design-vue';

const sentimentColor = {
  positive: 'success',
  neutral: 'processing',
  negative: 'error',
};

export const columns: BasicColumn[] = [
  { title: '商品', dataIndex: 'productName', width: 140, align: 'left', resizable: true },
  { title: '类目', dataIndex: 'categoryName', width: 110, resizable: true },
  {
    title: '评价内容',
    dataIndex: 'content',
    align: 'left',
    width: 260,
    resizable: true,
  },
  {
    title: '情绪',
    dataIndex: 'sentiment',
    width: 90,
    customRender: ({ text, record }) => {
      const label = record.sentiment_dictText || text || '-';
      const color = sentimentColor[String(text || '').toLowerCase()] || 'default';
      return h(Tag, { color }, () => label);
    },
  },
  { title: '置信分', dataIndex: 'score', width: 80 },
  { title: '关键词', dataIndex: 'keywordsText', width: 160, align: 'left' },
  { title: '用户', dataIndex: 'username', width: 100 },
  { title: '时间', dataIndex: 'createTime', width: 160 },
];

export const searchFormSchema: FormSchema[] = [
  { field: 'content', label: '评价内容', component: 'Input', colProps: { span: 6 } },
  { field: 'productName', label: '商品名称', component: 'Input', colProps: { span: 6 } },
  {
    field: 'sentiment',
    label: '情绪',
    component: 'Select',
    colProps: { span: 6 },
    componentProps: {
      allowClear: true,
      options: [
        { label: '正向', value: 'positive' },
        { label: '中性', value: 'neutral' },
        { label: '负向', value: 'negative' },
      ],
    },
  },
];

export const formSchema: FormSchema[] = [
  { field: 'id', label: 'id', component: 'Input', show: false },
  { field: 'categoryId', label: '类目ID', component: 'Input', show: false },
  {
    field: 'productId',
    label: '所属商品',
    component: 'Select',
    componentProps: {
      allowClear: true,
      showSearch: true,
      optionFilterProp: 'label',
      placeholder: '请选择商品（可选）',
      options: [],
    },
  },
  {
    field: 'productName',
    label: '商品名称',
    component: 'Input',
    componentProps: { placeholder: '不选商品时可手填名称' },
  },
  {
    field: 'categoryName',
    label: '类目',
    component: 'Input',
    componentProps: { placeholder: '选商品后自动带出', disabled: true },
  },
  {
    field: 'content',
    label: '评价内容',
    component: 'InputTextArea',
    required: true,
    helpMessage: '填写用户对商品的评价原文，例如：物流很快，包装完好，会回购。',
    componentProps: {
      rows: 4,
      placeholder: '例：物流很快，包装完好，质量不错，会回购',
      maxlength: 800,
      showCount: true,
    },
  },
  {
    field: 'keywords',
    label: '关键词',
    component: 'Select',
    helpMessage: '从关键词表选择（含通用 + 当前类目）；也可保存后用「评价分析」自动识别。',
    componentProps: {
      mode: 'multiple',
      allowClear: true,
      showSearch: true,
      optionFilterProp: 'label',
      placeholder: '从关键词表多选',
      options: [],
      maxTagCount: 6,
    },
  },
  {
    field: 'sentiment',
    label: '情绪',
    component: 'RadioButtonGroup',
    defaultValue: 'neutral',
    helpMessage: '评价整体倾向：正向 / 中性 / 负向。可不改，保存后点「更多 → 评价分析」由模型自动识别。',
    componentProps: {
      options: [
        { label: '正向', value: 'positive' },
        { label: '中性', value: 'neutral' },
        { label: '负向', value: 'negative' },
      ],
    },
  },
  {
    field: 'score',
    label: '置信分',
    component: 'InputNumber',
    defaultValue: 60,
    helpMessage: '0–100，表示情绪判断的把握程度（越高越确定）。可不填，评价分析后会自动写入。',
    componentProps: { min: 0, max: 100, style: { width: '100%' }, placeholder: '0-100' },
  },
  {
    field: 'summary',
    label: '分析摘要',
    component: 'InputTextArea',
    helpMessage: '可选。评价分析后会自动生成一句话摘要。',
    componentProps: { rows: 2, placeholder: '可选，分析后自动生成' },
  },
];
