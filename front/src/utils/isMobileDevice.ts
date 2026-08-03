/** 是否视为手机端访问（可被 ?desktop=1 强制关掉） */
export function isMobileDevice(): boolean {
  if (typeof window === 'undefined' || typeof navigator === 'undefined') return false;
  try {
    if (sessionStorage.getItem('forceDesktop') === '1') return false;
  } catch {
    /* ignore */
  }
  const ua = navigator.userAgent || '';
  if (/Android|webOS|iPhone|iPod|BlackBerry|IEMobile|Opera Mini|Mobile/i.test(ua)) return true;
  if (/iPad|Tablet/i.test(ua)) return true;
  return window.innerWidth > 0 && window.innerWidth <= 768;
}

/** 打开桌面版一次（本会话有效） */
export function forceDesktopOnce(): void {
  try {
    sessionStorage.setItem('forceDesktop', '1');
  } catch {
    /* ignore */
  }
}
