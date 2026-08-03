import { defHttp } from '/@/utils/http/axios';
import { Modal } from 'ant-design-vue';

enum Api {
  list = '/biz/category/list',
  tree = '/biz/category/tree',
  save = '/biz/category/add',
  edit = '/biz/category/edit',
  delete = '/biz/category/delete',
  deleteBatch = '/biz/category/deleteBatch',
}

export const list = (params?) => defHttp.get({ url: Api.list, params });

export const treeList = () => defHttp.get({ url: Api.tree });

export const deleteCategory = (params, handleSuccess) => {
  return defHttp.delete({ url: Api.delete, params }, { joinParamsToUrl: true }).then(() => {
    handleSuccess();
  });
};

export const batchDeleteCategory = (params, handleSuccess) => {
  Modal.confirm({
    title: '确认删除',
    content: '是否删除选中类目？若含下级类目将一并删除。',
    okText: '确认',
    cancelText: '取消',
    onOk: () => {
      return defHttp.delete({ url: Api.deleteBatch, data: params }, { joinParamsToUrl: true }).then(() => {
        handleSuccess();
      });
    },
  });
};

export const saveOrUpdateCategory = (params, isUpdate) => {
  const url = isUpdate ? Api.edit : Api.save;
  return defHttp.post({ url, params });
};
