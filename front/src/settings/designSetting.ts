import { ThemeEnum } from '../enums/appEnum';

export const prefixCls = 'jeecg';

export const darkMode = ThemeEnum.LIGHT;

/** 与前台 Welcome / Insight 主色一致 */
export const SENTIMENT_PRIMARY = '#167f87';
export const SENTIMENT_HEADER_BG = '#f3fbfc';

// app theme preset color
export const APP_PRESET_COLOR_LIST: string[] = [
  SENTIMENT_PRIMARY,
  '#0960bd',
  '#1890ff',
  '#009688',
  '#536dfe',
  '#ff5c93',
  '#13c2c2',
  '#52c41a',
  '#ee4f12',
  '#0096c7',
  '#9c27b0',
  '#ff9800',
];

// header preset color
export const HEADER_PRESET_BG_COLOR_LIST: string[] = [
  SENTIMENT_HEADER_BG,
  '#ffffff',
  '#151515',
  '#009688',
  '#5172DC',
  '#018ffb',
  '#13c2c2',
  '#e74c3c',
  '#52c41a',
  '#394664',
  '#faad14',
  '#383f45',
];

// sider preset color
export const SIDE_BAR_BG_COLOR_LIST: string[] = [
  '#001529',
  // '#212121',
  '#009688',
  '#273352',
  '#ffffff',
  '#191b24',
  // '#191a23',
  '#037bd5',
  '#304156',
  '#001628',
  '#28333E',
  // '#344058',
  '#e74c3c',
  '#383f45',
];

// 项目配置默认：顶栏前台同色底 / 菜单白色（配合 sentiment-admin.less）
export const DEFAULT_HEADER_BG_COLOR = SENTIMENT_HEADER_BG;
export const DEFAULT_SIDEBAR_BG_COLOR = SIDE_BAR_BG_COLOR_LIST[3];

// sider logo line preset color
export const SIDER_LOGO_BG_COLOR_LIST: string[] = [
  'linear-gradient(180deg, #000000, #021d37)',
  // 'linear-gradient(180deg, #000000, #282828)',
  'linear-gradient(180deg, #078d80, #029184)',
  'linear-gradient(180deg, #1c253e, #2b385c)',
  'linear-gradient(180deg, #f3fbfc, #ffffff)',
  'linear-gradient(180deg, #000000, #242735)',
  // 'linear-gradient(180deg, #000000, #1d1f2a)',
  'linear-gradient(180deg, #1d77bb, #188efa)',
  'linear-gradient(180deg, #304156, #32455d)',
  'linear-gradient(180deg, #000000, #001f39)',
  'linear-gradient(180deg, #000000, #2b3743)',
  // 'linear-gradient(180deg, #344058, #374560)',
  'linear-gradient(180deg, #e83723, #e52611)',
  'linear-gradient(180deg, #383f45, #3b434b)',
];
