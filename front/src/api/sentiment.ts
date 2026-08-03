import { defHttp } from '/@/utils/http/axios';

export interface SentimentPredictParams { content: string; productId?: string; product?: ProductDraft }
export interface SentimentPredictResult { sentiment: 'positive' | 'neutral' | 'negative'; score: number; summary: string; keywords: string[] }
export interface ProductDraft { name: string; category: string; rating: string; note: string }

const Api = { predict: '/sentiment/predict', products: '/sentiment/products' };
export function predictSentiment(params: SentimentPredictParams) {
  return defHttp.post<SentimentPredictResult>(
    { url: Api.predict, data: params, timeout: 90 * 1000 },
    { errorMessageMode: 'none' },
  );
}

export function saveProductDraft(params: ProductDraft) {
  return defHttp.post({ url: Api.products, data: params }, { errorMessageMode: 'none' });
}
