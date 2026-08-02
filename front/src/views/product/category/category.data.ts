import { BasicColumn, FormSchema } from '/@/components/Table';
import { h } from 'vue';
import { Tag } from 'ant-design-vue';

export const columns: BasicColumn[] = [
  {
    title: '类目名称',
    dataIndex: 'name',
    width: 220,
    align: 'left',
  },
  {
    title: '类目编码',
    dataIndex: 'code',
    width: 140,
    align: 'left',
  },
  {
    title: '层级',
    dataIndex: 'level',
    width: 70,
  },
  {
    title: '排序',
    dataIndex: 'sortNo',
    width: 70,
  },
  {
    title: '状态',
    dataIndex: 'status',
    width: 90,
    customRender: ({ text }) => {
      const enabled = text === 1 || text === '1';
      return h(Tag, { color: enabled ? 'success' : 'default' }, () => (enabled ? '启用' : '停用'));
    },
  },
  {
    title: '描述',
    dataIndex: 'description',
    align: 'left',
  },
];

export const searchFormSchema: FormSchema[] = [
  {
    field: 'name',
    label: '类目名称',
    component: 'Input',
    colProps: { span: 8 },
  },
];

export const formSchema: FormSchema[] = [
  {
    label: 'id',
    field: 'id',
    component: 'Input',
    show: false,
  },
  {
    field: 'name',
    label: '类目名称',
    component: 'Input',
    required: true,
  },
  {
    field: 'parentId',
    label: '上级类目',
    component: 'TreeSelect',
    componentProps: {
      allowClear: true,
      placeholder: '不选则为一级类目',
      fieldNames: {
        label: 'name',
        key: 'id',
        value: 'id',
      },
      dropdownStyle: {
        maxHeight: '50vh',
      },
      getPopupContainer: (node) => node?.parentNode,
    },
  },
  {
    field: 'code',
    label: '类目编码',
    component: 'Input',
    componentProps: {
      placeholder: '可选，如 books / digital',
    },
  },
  {
    field: 'sortNo',
    label: '排序',
    component: 'InputNumber',
    defaultValue: 0,
  },
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
  {
    field: 'description',
    label: '描述',
    component: 'InputTextArea',
    componentProps: {
      rows: 3,
      placeholder: '类目说明（可选）',
    },
  },
];
