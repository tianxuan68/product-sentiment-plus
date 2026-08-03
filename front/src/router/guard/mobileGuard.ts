import type { Router } from 'vue-router';
import { PageEnum } from '/@/enums/pageEnum';
import { forceDesktopOnce, isMobileDevice } from '/@/utils/isMobileDevice';

/** 手机打开落地页时默认进手机端；加 ?desktop=1 可回桌面 */
const LANDING_PATHS = new Set<string>([
  '/',
  PageEnum.BASE_HOME,
  PageEnum.BASE_WELCOME,
]);

export function createMobileGuard(router: Router) {
  router.beforeEach((to, _from, next) => {
    if (to.query.desktop === '1' || to.query.desktop === 'true') {
      forceDesktopOnce();
      const q = { ...to.query };
      delete q.desktop;
      next({ path: to.path, query: q, hash: to.hash, replace: true });
      return;
    }

    if (!isMobileDevice()) {
      next();
      return;
    }

    // 已在手机端、登录/鉴权相关页：不拦截
    if (to.path === PageEnum.MOBILE_HOME || to.path.startsWith(`${PageEnum.MOBILE_HOME}/`)) {
      next();
      return;
    }
    if (
      to.path === PageEnum.BASE_LOGIN ||
      to.path === PageEnum.OAUTH2_LOGIN_PAGE_PATH ||
      to.path === PageEnum.TOKEN_LOGIN
    ) {
      next();
      return;
    }

    if (LANDING_PATHS.has(to.path)) {
      next({ path: PageEnum.MOBILE_SELECT, replace: true });
      return;
    }

    next();
  });
}
