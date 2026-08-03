import { defHttp } from '/@/utils/http/axios';
import { Modal } from 'ant-design-vue';

enum Api {
  list = '/biz/causal/list',
  run = '/biz/causal/run',
  delete = '/biz/causal/delete',
  deleteBatch = '/biz/causal/deleteBatch',
}

export const list = (params) => defHttp.get({ url: Api.list, params });

export const runCausal = (data?: { categoryId?: string; categoryName?: string }) =>
  defHttp.post({ url: Api.run, data: data || {} });

export const deleteCausal = (params, handleSuccess) => {
  return defHttp.delete({ url: Api.delete, params }, { joinParamsToUrl: true }).then(() => handleSuccess());
};

export const batchDeleteCausal = (params, handleSuccess) => {
  Modal.confirm({
    title: '确认删除',
    content: '是否删除选中分析结果？',
    okText: '确认',
    cancelText: '取消',
    onOk: () => {
      return defHttp
        .delete({ url: Api.deleteBatch, params }, { joinParamsToUrl: true })
        .then(() => handleSuccess());
    },
  });
};
