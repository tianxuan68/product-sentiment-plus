import type { AppRouteRecordRaw, AppRouteModule } from '/@/router/types';

import { PAGE_NOT_FOUND_ROUTE, REDIRECT_ROUTE } from '/@/router/routes/basic';

import { mainOutRoutes } from './mainOut';
import { PageEnum } from '/@/enums/pageEnum';
import { t } from '/@/hooks/web/useI18n';
import { LAYOUT } from '/@/router/constant';

const modules = import.meta.glob('./modules/**/*.ts', { eager: true });

const routeModuleList: AppRouteModule[] = [];

// 加入到路由集合中
Object.keys(modules).forEach((key) => {
  const mod = (modules as Recordable)[key].default || {};
  const modList = Array.isArray(mod) ? [...mod] : [mod];
  routeModuleList.push(...modList);
});

export const asyncRoutes = [PAGE_NOT_FOUND_ROUTE, ...routeModuleList];

export const RootRoute: AppRouteRecordRaw = {
  path: '/',
  name: 'Root',
  redirect: PageEnum.BASE_HOME,
  meta: {
    title: 'Root',
  },
};

export const LoginRoute: AppRouteRecordRaw = {
  path: '/login',
  name: 'Login',
  //新版后台登录，如果想要使用旧版登录放开即可
  // component: () => import('/@/views/sys/login/Login.vue'),
  component: () => import('/@/views/sys/login/Login.vue'),
  meta: {
    title: t('routes.basic.login'),
  },
};

export const WelcomeRoute: AppRouteRecordRaw = {
  path: PageEnum.BASE_WELCOME,
  name: 'Welcome',
  component: () => import('/@/views/sys/welcome/LegacyWelcome.vue'),
  meta: {
    title: 'Sentiment',
    ignoreAuth: false,
  },
};

export const UserHomeRoute: AppRouteRecordRaw = {
  path: PageEnum.BASE_HOME,
  name: 'UserHome',
  component: () => import('/@/views/sys/welcome/Welcome.vue'),
  meta: { title: 'Sentiment', ignoreAuth: false, hideMenu: true, hideBreadcrumb: true },
};

export const InsightRoute: AppRouteRecordRaw = {
  path: PageEnum.BASE_INSIGHT,
  name: 'InsightWorkspace',
  component: () => import('/@/views/sys/insight/Insight.vue'),
  meta: { title: '情绪洞察', ignoreAuth: false, hideMenu: true, hideBreadcrumb: true },
};

/** 手机端：评论查找 + 看板/洞察/我的 */
export const MobileRoute: AppRouteRecordRaw = {
  path: PageEnum.MOBILE_HOME,
  name: 'MobileShell',
  component: () => import('/@/views/mobile/MobileShell.vue'),
  redirect: PageEnum.MOBILE_SELECT,
  meta: { title: '评论', ignoreAuth: false, hideMenu: true, hideBreadcrumb: true },
  children: [
    {
      path: 'select',
      name: 'MobileSelect',
      component: () => import('/@/views/mobile/pages/MobileSelect.vue'),
      meta: { title: '评论', ignoreAuth: false, hideMenu: true },
    },
    {
      path: 'insight',
      name: 'MobileInsight',
      component: () => import('/@/views/mobile/pages/MobileInsight.vue'),
      meta: { title: '洞察', ignoreAuth: false, hideMenu: true },
    },
    {
      path: 'board',
      name: 'MobileBoard',
      component: () => import('/@/views/mobile/pages/MobileBoard.vue'),
      meta: { title: '看板', ignoreAuth: false, hideMenu: true },
    },
    {
      path: 'mine',
      name: 'MobileMine',
      component: () => import('/@/views/mobile/pages/MobileMine.vue'),
      meta: { title: '我的', ignoreAuth: false, hideMenu: true },
    },
  ],
};

/** 旧前台路径兼容：洞察页曾挂在 /system/user/insight */
export const LegacyInsightRedirectRoute: AppRouteRecordRaw = {
  path: '/system/user/insight',
  name: 'LegacyInsightRedirect',
  redirect: PageEnum.BASE_INSIGHT,
  meta: { hideMenu: true, ignoreAuth: false },
};

// 代码逻辑说明: auth2登录页面路由------------
export const Oauth2LoginRoute: AppRouteRecordRaw = {
  path: '/oauth2-app/login',
  name: 'oauth2-app-login',
  //新版钉钉免登录，如果想要使用旧版放开即可
  // component: () => import('/@/views/sys/login/OAuth2Login.vue'),
  component: () => import('/@/views/system/loginmini/OAuth2Login.vue'),
  meta: {
    title: t('routes.oauth2.login'),
  },
};

/**
 * 【通过token直接静默登录】流程办理登录页面 中转跳转
 */
export const TokenLoginRoute: AppRouteRecordRaw = {
  path: '/tokenLogin',
  name: 'TokenLoginRoute',
  component: () => import('/@/views/sys/login/TokenLoginPage.vue'),
  meta: {
    title: '带token登录页面',
    ignoreAuth: true,
  },
};
// Basic routing without permission
export const basicRoutes = [
  LoginRoute,
  WelcomeRoute,
  UserHomeRoute,
  InsightRoute,
  MobileRoute,
  LegacyInsightRedirectRoute,
  RootRoute,
  ...mainOutRoutes,
  REDIRECT_ROUTE,
  PAGE_NOT_FOUND_ROUTE,
  TokenLoginRoute,
  Oauth2LoginRoute,
];
