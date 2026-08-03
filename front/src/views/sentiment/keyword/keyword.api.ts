import { defHttp } from '/@/utils/http/axios';
import { Modal } from 'ant-design-vue';

enum Api {
  list = '/biz/keyword/list',
  save = '/biz/keyword/add',
  edit = '/biz/keyword/edit',
  delete = '/biz/keyword/delete',
  deleteBatch = '/biz/keyword/deleteBatch',
  categoryTree = '/biz/category/tree',
}

export const GENERAL_CATEGORY_ID = '__general__';

/** 类目下拉：通用 + 全部业务类目 */
export const categoryOptions = () =>
  defHttp.get({ url: Api.categoryTree }).then((tree) => {
    const options: { label: string; value: string; name?: string }[] = [
      { label: '通用', value: GENERAL_CATEGORY_ID, name: '通用' },
    ];
    const walk = (nodes: any[]) => {
      (nodes || []).forEach((n) => {
        if (n?.id && n?.name) {
          options.push({ label: n.name, value: n.id, name: n.name });
        }
        if (n?.children?.length) walk(n.children);
      });
    };
    walk(Array.isArray(tree) ? tree : []);
    return options;
  });

export const list = (params) => defHttp.get({ url: Api.list, params });

export const deleteKeyword = (params, handleSuccess) => {
  return defHttp.delete({ url: Api.delete, params }, { joinParamsToUrl: true }).then(() => handleSuccess());
};

export const batchDeleteKeyword = (params, handleSuccess) => {
  Modal.confirm({
    title: '确认删除',
    content: '是否删除选中关键词？',
    okText: '确认',
    cancelText: '取消',
    onOk: () => {
      return defHttp.delete({ url: Api.deleteBatch, data: params }, { joinParamsToUrl: true }).then(() => handleSuccess());
    },
  });
};

export const saveOrUpdateKeyword = (params, isUpdate) => {
  const payload = { ...params };
  if (payload.categoryId === GENERAL_CATEGORY_ID) {
    payload.categoryId = '';
    payload.categoryName = '';
  }
  return defHttp.post({ url: isUpdate ? Api.edit : Api.save, params: payload });
};
