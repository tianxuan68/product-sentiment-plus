import { BasicColumn, FormSchema } from '/@/components/Table';

export const columns: BasicColumn[] = [
  { title: '类目', dataIndex: 'categoryName', width: 140, align: 'left', resizable: true },
  { title: '评价条数', dataIndex: 'sampleSize', width: 90 },
  {
    title: '提到服务占比',
    dataIndex: 'treatmentRate',
    width: 120,
    customRender: ({ text }) => {
      if (text == null || text === '') return '-';
      return `${Math.round(Number(text) * 1000) / 10}%`;
    },
  },
  {
    title: '好评占比',
    dataIndex: 'outcomeRate',
    width: 100,
    customRender: ({ text }) => {
      if (text == null || text === '') return '-';
      return `${Math.round(Number(text) * 1000) / 10}%`;
    },
  },
  {
    title: '结论（白话）',
    dataIndex: 'conclusion',
    align: 'left',
    minWidth: 320,
    resizable: true,
    customRender: ({ text, record }) => text || record.ateText || '-',
  },
  { title: '更新时间', dataIndex: 'updateTime', width: 160 },
];

export const searchFormSchema: FormSchema[] = [
  { field: 'categoryName', label: '类目', component: 'Input', colProps: { span: 6 } },
];
