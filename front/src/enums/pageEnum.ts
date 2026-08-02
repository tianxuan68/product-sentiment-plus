export enum PageEnum {
  // basic login path
  BASE_LOGIN = '/login',
  // 前台品牌首页（勿占用 /system/user，该路径留给后台用户管理）
  BASE_HOME = '/home',
  // 前台洞察工作台
  BASE_INSIGHT = '/home/insight',
  // 后台默认落地：评价看板
  BASE_ADMIN = '/sentiment/dashboard',
  // post-login brand welcome path
  BASE_WELCOME = '/welcome',
  // error page path
  ERROR_PAGE = '/exception',
  // error log page path
  ERROR_LOG_PAGE = '/error-log/list',
  // auth2登录路由路径
  OAUTH2_LOGIN_PAGE_PATH = '/oauth2-app/login',
  //文件路由
  SYS_FILES_PATH = '/file/share',
  // 邮件中的跳转地址
  TOKEN_LOGIN = '/tokenLogin'
}
