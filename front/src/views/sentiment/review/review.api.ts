import { defHttp } from '/@/utils/http/axios';
import { Modal } from 'ant-design-vue';
import { downloadByData } from '/@/utils/file/download';

enum Api {
  list = '/biz/review/list',
  save = '/biz/review/add',
  edit = '/biz/review/edit',
  delete = '/biz/review/delete',
  deleteBatch = '/biz/review/deleteBatch',
  analyze = '/biz/review/analyze',
  productList = '/biz/product/list',
  keywordOptions = '/biz/keyword/options',
  importTemplate = '/biz/review/importTemplate',
  importExcel = '/biz/review/importExcel',
}

export const list = (params) => defHttp.get({ url: Api.list, params });

export const productOptions = () =>
  defHttp.get({ url: Api.productList, params: { pageNo: 1, pageSize: 200 } }).then((res) => {
    const records = res?.records || [];
    return records.map((r) => ({
      label: r.name,
      value: r.id,
      categoryId: r.categoryId,
      categoryName: r.categoryName,
      name: r.name,
    }));
  });

/** 关键词下拉：通用 + 指定类目（来自 biz_keyword） */
export const keywordOptions = (params?: { categoryId?: string; categoryName?: string }) =>
  defHttp.get({ url: Api.keywordOptions, params: params || {} });

export const deleteReview = (params, handleSuccess) => {
  return defHttp.delete({ url: Api.delete, params }, { joinParamsToUrl: true }).then(() => handleSuccess());
};

export const batchDeleteReview = (params, handleSuccess) => {
  Modal.confirm({
    title: '确认删除',
    content: '是否删除选中评价记录？',
    okText: '确认',
    cancelText: '取消',
    onOk: () => {
      return defHttp.delete({ url: Api.deleteBatch, data: params }, { joinParamsToUrl: true }).then(() => handleSuccess());
    },
  });
};

export const saveOrUpdateReview = (params, isUpdate) => {
  return defHttp.post({ url: isUpdate ? Api.edit : Api.save, params });
};

/** 对单条评价调用 BERT 多标签 + 情感分析 */
export const analyzeReview = (id: string) => {
  return defHttp.post(
    { url: Api.analyze, params: { id }, timeout: 120000 },
    { joinParamsToUrl: true },
  );
};

/** 下载评价导入 CSV 模板 */
export const downloadImportTemplate = async () => {
  const response = await defHttp.get(
    { url: Api.importTemplate, responseType: 'blob', timeout: 60000 },
    { isTransformResponse: false, isReturnNativeResponse: true },
  );
  downloadByData(response.data, '评价导入模板.csv', 'text/csv;charset=utf-8');
};

/** 上传并解析评价 CSV */
export const importReviews = (file: File) => {
  return defHttp
    .uploadFile<any>({ url: Api.importExcel, timeout: 120000 }, { file }, { isReturnResponse: true })
    .then((body) => {
      if (body && body.success === false) {
        return Promise.reject(new Error(body.message || '导入失败'));
      }
      return body?.result ?? body;
    });
};
