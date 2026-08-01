import type { App } from 'vue';
import { warn } from '/@/utils/log';

// 精简版：不加载 AI/低代码等增值 npm 包
const lazyPackages: { name: string; importer: () => Promise<unknown> }[] = [];

let appInstance: App | null = null;

// noinspection JSUnusedGlobalSymbols
const installOptions = {
  baseImport,
};

export function registerPackages(app: App) {
  appInstance = app;
}

/** 已加载的包缓存 */
const loadedPackages = new Map<string, unknown>();
/** 正在加载的包 Promise 缓存（防止重复加载） */
const loadingPromises = new Map<string, Promise<unknown>>();

/**
 * 按需加载包并注册
 */
async function ensurePackageLoaded(pkgConfig: (typeof lazyPackages)[number]) {
  const { name, importer } = pkgConfig;
  if (loadedPackages.has(name)) {
    return loadedPackages.get(name);
  }
  if (!loadingPromises.has(name)) {
    const promise = importer().then((pkg) => {
      loadedPackages.set(name, pkg);
      loadingPromises.delete(name);
      return pkg;
    });
    loadingPromises.set(name, promise);
  }
  return loadingPromises.get(name);
}

/**
 * 根据 component 路径关键字匹配优先加载的包
 */
function getMatchedPackage(component: string): (typeof lazyPackages)[number] | null {
  const lc = component.toLowerCase();
  for (const pkgConfig of lazyPackages) {
    const keyword = pkgConfig.name.split('/').pop()!;
    if (lc.includes(keyword)) {
      return pkgConfig;
    }
  }
  return null;
}

/**
 * 从指定包中查找组件
 */
async function findComponentInPackage(
  pkgConfig: (typeof lazyPackages)[number],
  component: string
): Promise<(() => Promise<Recordable>) | null> {
  try {
    const mod = (await ensurePackageLoaded(pkgConfig)) as Recordable;
    const views = mod.getViews?.();
    if (!views) {
      return null;
    }
    for (const key of Object.keys(views)) {
      const k = key.replace('./src/views', '');
      const startFlag = component.startsWith('/');
      const endFlag = component.endsWith('.vue') || component.endsWith('.tsx');
      const startIndex = startFlag ? 0 : 1;
      const lastIndex = endFlag ? k.length : k.lastIndexOf('.');
      if (k.substring(startIndex, lastIndex) === component) {
        return views[key];
      }
    }
  } catch (e) {
    // 包不存在或加载失败，跳过
  }
  return null;
}

/**
 * 按需加载包组件：当路由匹配不到本地组件时调用
 */
export async function loadPackageComponent(component: string): Promise<(() => Promise<Recordable>) | null> {
  const matched = getMatchedPackage(component);
  if (matched) {
    return findComponentInPackage(matched, component);
  }
  for (const pkgConfig of lazyPackages) {
    const result = await findComponentInPackage(pkgConfig, component);
    if (result) return result;
  }
  return null;
}

// 模块里可使用的import
const importGlobs = [import.meta.glob('../../utils/**/*.{ts,js,tsx}'), import.meta.glob('../../hooks/**/*.{ts,js,tsx}')];

/**
 * 基础项目导包
 */
async function baseImport(path: string) {
  if (path) {
    path = path.replace(/^\/@\//, '../../');
    for (const glob of importGlobs) {
      for (const key of Object.keys(glob)) {
        if (path === key || `${path}.ts` === key || `${path}.tsx` === key) {
          return glob[key]();
        }
      }
    }
    warn(`引入失败：${path} 不存在`);
  }
  return null;
}
