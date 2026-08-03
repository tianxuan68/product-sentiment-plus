import { defHttp } from '/@/utils/http/axios';

export type OverviewSummary = {
  total?: number;
  positive?: number;
  neutral?: number;
  negative?: number;
  positiveRate?: number;
  negativeRate?: number;
};

export type TagTopItem = {
  name: string;
  count: number;
  rate?: number;
  tone?: string;
};

export const fetchProducts = (params: Recordable) =>
  defHttp.get({ url: '/biz/product/list', params });

export const fetchBrands = (params?: Recordable) =>
  defHttp.get({ url: '/biz/product/brands', params });

export const fetchCategoryTree = () => defHttp.get({ url: '/biz/category/tree' });

export const fetchKeywords = (params?: Recordable) =>
  defHttp.get({ url: '/biz/keyword/list', params: { pageNo: 1, pageSize: 40, ...params } });

export const fetchDashboardOverview = (params?: Recordable) =>
  defHttp.get({ url: '/biz/dashboard/overview', params });

export const fetchDashboardSummary = (params?: Recordable) =>
  defHttp.get({ url: '/biz/dashboard/summary', params });

export const fetchCausalList = (params?: Recordable) =>
  defHttp.get({ url: '/biz/causal/list', params: { pageNo: 1, pageSize: 8, ...params } });

export const fetchReviewList = (params?: Recordable) =>
  defHttp.get({ url: '/biz/review/list', params: { pageNo: 1, pageSize: 20, ...params } });

/** 看板：概览（含 summary / tagTop） */
export async function fetchOverview(params?: Recordable) {
  return (await fetchDashboardOverview(params)) as {
    summary?: OverviewSummary;
    tagTop?: { items?: TagTopItem[] };
  };
}

/** 看板：热门标签 */
export async function fetchTagTop(limit = 12, params?: Recordable) {
  const data = await defHttp.get({
    url: '/biz/dashboard/tagTop',
    params: { limit, ...params },
  });
  const items = (data?.items || []).map((it: any) => ({
    name: String(it.name || ''),
    count: Number(it.count || 0),
    rate: it.rate,
    tone: it.tone,
  })) as TagTopItem[];
  return { items };
}
