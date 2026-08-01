/** 浏览器访问的后端 API 基址（统一走 /jeecgboot，勿用 /jeecg-boot）。 */
export function normalizePublicApiBaseUrl(base?: string): string {
  let resolved = String(
    base || (window as any)._CONFIG?.domianURL || import.meta.env.VITE_GLOB_DOMAIN_URL || '',
  )
    .replace(/\/$/, '')
    .replace(/\/jeecg-boot$/i, '/jeecgboot');
  if (!/^https?:\/\//.test(resolved)) {
    resolved = `${window.location.origin}${resolved.startsWith('/') ? '' : '/'}${resolved}`;
  }
  return resolved;
}

/** 构建第三方 OAuth 弹窗地址。 */
export function buildThirdLoginRenderUrl(source: string): string {
  return `${normalizePublicApiBaseUrl()}/sys/thirdLogin/render/${source}`;
}

/** OAuth 开放平台需登记的回调地址。 */
export function buildThirdLoginCallbackUrl(source: string): string {
  return `${normalizePublicApiBaseUrl()}/sys/thirdLogin/${source}/callback`;
}

export const THIRD_LOGIN_SOURCE_LABELS: Record<string, string> = {
  github: 'GitHub',
  wechat_open: '微信',
  dingtalk: '钉钉',
  wechat_enterprise: '企业微信',
};
