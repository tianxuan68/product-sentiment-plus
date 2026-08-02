import { defHttp } from '/@/utils/http/axios';
import { Modal } from 'ant-design-vue';

enum Api {
  list = '/biz/product/list',
  save = '/biz/product/add',
  edit = '/biz/product/edit',
  delete = '/biz/product/delete',
  deleteBatch = '/biz/product/deleteBatch',
  categoryTree = '/biz/category/tree',
}

export const list = (params) => defHttp.get({ url: Api.list, params });

export const categoryTree = () => defHttp.get({ url: Api.categoryTree });

export const deleteProduct = (params, handleSuccess) => {
  return defHttp.delete({ url: Api.delete, params }, { joinParamsToUrl: true }).then(() => handleSuccess());
};

export const batchDeleteProduct = (params, handleSuccess) => {
  Modal.confirm({
    title: '确认删除',
    content: '是否删除选中商品？',
    okText: '确认',
    cancelText: '取消',
    onOk: () => {
      return defHttp.delete({ url: Api.deleteBatch, data: params }, { joinParamsToUrl: true }).then(() => handleSuccess());
    },
  });
};

export const saveOrUpdateProduct = (params, isUpdate) => {
  return defHttp.post({ url: isUpdate ? Api.edit : Api.save, params });
};
