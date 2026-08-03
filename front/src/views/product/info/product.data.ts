import { BasicColumn, FormSchema } from '/@/components/Table';
import { h } from 'vue';
import { Tag } from 'ant-design-vue';

export const columns: BasicColumn[] = [
  { title: '商品名称', dataIndex: 'name', width: 180, align: 'left', resizable: true },
  { title: '类目', dataIndex: 'categoryName', width: 120, resizable: true },
  { title: '品牌', dataIndex: 'brand', width: 100, resizable: true },
  { title: 'SKU', dataIndex: 'sku', width: 120, resizable: true },
  { title: '售价', dataIndex: 'price', width: 90 },
  { title: '库存', dataIndex: 'stock', width: 80 },
  {
    title: '状态',
    dataIndex: 'status',
    width: 80,
    customRender: ({ text }) => {
      const on = text === 1 || text === '1';
      return h(Tag, { color: on ? 'success' : 'default' }, () => (on ? '上架' : '下架'));
    },
  },
  { title: '创建时间', dataIndex: 'createTime', width: 160 },
];

export const searchFormSchema: FormSchema[] = [
  { field: 'name', label: '商品名称', component: 'Input', colProps: { span: 6 } },
  { field: 'brand', label: '品牌', component: 'Input', colProps: { span: 6 } },
  { field: 'sku', label: 'SKU', component: 'Input', colProps: { span: 6 } },
  {
    field: 'status',
    label: '状态',
    component: 'Select',
    colProps: { span: 6 },
    componentProps: {
      allowClear: true,
      options: [
        { label: '上架', value: 1 },
        { label: '下架', value: 0 },
      ],
    },
  },
];

export const formSchema: FormSchema[] = [
  { field: 'id', label: 'id', component: 'Input', show: false },
  { field: 'name', label: '商品名称', component: 'Input', required: true },
  {
    field: 'categoryId',
    label: '所属类目',
    component: 'TreeSelect',
    componentProps: {
      allowClear: true,
      placeholder: '请选择类目',
      fieldNames: { label: 'name', key: 'id', value: 'id' },
      dropdownStyle: { maxHeight: '50vh' },
      getPopupContainer: (node) => node?.parentNode,
    },
  },
  { field: 'brand', label: '品牌', component: 'Input' },
  { field: 'sku', label: 'SKU', component: 'Input' },
  { field: 'price', label: '售价', component: 'InputNumber', componentProps: { min: 0, precision: 2, style: { width: '100%' } } },
  { field: 'originalPrice', label: '原价', component: 'InputNumber', componentProps: { min: 0, precision: 2, style: { width: '100%' } } },
  { field: 'stock', label: '库存', component: 'InputNumber', defaultValue: 0, componentProps: { min: 0, style: { width: '100%' } } },
  { field: 'unit', label: '单位', component: 'Input' },
  {
    field: 'status',
    label: '状态',
    component: 'RadioButtonGroup',
    defaultValue: 1,
    componentProps: {
      options: [
        { label: '上架', value: 1 },
        { label: '下架', value: 0 },
      ],
    },
  },
  { field: 'description', label: '描述', component: 'InputTextArea', componentProps: { rows: 3 } },
  { field: 'note', label: '备注', component: 'InputTextArea', componentProps: { rows: 2 } },
];
