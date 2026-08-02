import { defHttp } from '/@/utils/http/axios';

enum Api {
  overview = '/biz/dashboard/overview',
  tagTop = '/biz/dashboard/tagTop',
  summary = '/biz/dashboard/summary',
}

export const fetchOverview = (params?: { limit?: number; productId?: string; days?: number }) =>
  defHttp.get({ url: Api.overview, params });

export const fetchTagTop = (params?: { limit?: number; productId?: string; days?: number }) =>
  defHttp.get({ url: Api.tagTop, params });

export const fetchSummary = (params?: { productId?: string; days?: number }) =>
  defHttp.get({ url: Api.summary, params });
