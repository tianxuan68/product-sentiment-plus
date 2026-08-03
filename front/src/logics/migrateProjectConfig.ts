import type { ProjectConfig } from '/#/config';
import { PROJ_THEME_CFG_VERSION, PROJ_THEME_VERSION_KEY } from '/@/enums/cacheEnum';
import { ThemeEnum } from '/@/enums/appEnum';
import {
  DEFAULT_HEADER_BG_COLOR,
  DEFAULT_SIDEBAR_BG_COLOR,
  SENTIMENT_PRIMARY,
} from '/@/settings/designSetting';
import { Persistent } from '/@/utils/cache/persistent';

export interface ThemeDefaultsMigrationResult {
  config: ProjectConfig | null | undefined;
  migrated: boolean;
}

/**
 * 首次升级或尚未写入主题版本时，将顶栏/菜单强制对齐前台 Sentiment 壳层，
 * 避免 localStorage 中的 JeecgBoot 旧配色覆盖 projectSetting。
 */
export function applyProjectThemeDefaults(
  cfg?: ProjectConfig | null,
): ThemeDefaultsMigrationResult {
  const savedVersion = Persistent.getLocal(PROJ_THEME_VERSION_KEY) as number | undefined;
  if (savedVersion === PROJ_THEME_CFG_VERSION) {
    return { config: cfg, migrated: false };
  }

  Persistent.setLocal(PROJ_THEME_VERSION_KEY, PROJ_THEME_CFG_VERSION);

  const next: ProjectConfig = {
    ...(cfg ?? ({} as ProjectConfig)),
    themeColor: SENTIMENT_PRIMARY,
    themeMode: ThemeEnum.LIGHT,
    showSettingButton: false,
    showDarkModeToggle: false,
    headerSetting: {
      ...(cfg?.headerSetting ?? {}),
      bgColor: DEFAULT_HEADER_BG_COLOR,
      theme: ThemeEnum.LIGHT,
      showNotice: false,
      showSearch: false,
    },
    menuSetting: {
      ...(cfg?.menuSetting ?? {}),
      bgColor: DEFAULT_SIDEBAR_BG_COLOR,
      theme: ThemeEnum.LIGHT,
      isThemeBright: false,
    },
  };

  return { config: next, migrated: true };
}

/** @deprecated use applyProjectThemeDefaults */
export function migrateProjectThemeDefaults(cfg?: ProjectConfig | null): ProjectConfig | undefined {
  return applyProjectThemeDefaults(cfg).config ?? undefined;
}
