<template>
  <div
    ref="loginRoot"
    :class="[prefixCls, 'ocean-login']"
    class="relative w-full h-full"
    @pointermove="handlePointerMove"
  >
    <div class="ocean-backdrop" aria-hidden="true">
      <div class="ocean-sun" />
      <div ref="cursorLight" class="ocean-cursor-light" />
      <div class="ocean-haze ocean-haze-one" />
      <div class="ocean-haze ocean-haze-two" />
      <div class="ocean-surface ocean-surface-back" />
      <div class="ocean-surface ocean-surface-front" />
      <div ref="rippleLayer" class="ocean-ripples" />
      <div class="ocean-grain" />
    </div>

    <AppLocalePicker class="ocean-toolbar ocean-locale" :showText="false" v-if="!sessionTimeout && showLocale" />
    <AppDarkModeToggle class="ocean-toolbar ocean-theme" v-if="!sessionTimeout" />

    <div class="ocean-shell relative h-full mx-auto">
      <section class="ocean-intro" aria-label="Sentiment Plus">
        <div class="ocean-brand-mark">
          <span class="ocean-brand-dot" />
          <span>SENTIMENT PLUS</span>
        </div>
        <h1>把海面的光，<br /><em>变成清晰洞察。</em></h1>
        <p>在波光粼粼的海风里，读取每一条真实反馈，让产品决策更接近用户。</p>
        <div class="ocean-intro-meta">
          <span class="ocean-meta-line" />
          <span>PRODUCT SENTIMENT INTELLIGENCE</span>
        </div>
        <div class="ocean-scroll-hint"><span /> SCROLL INTO INSIGHT</div>
      </section>

      <section class="ocean-login-panel" aria-label="登录">
        <div class="ocean-panel-glow" />
        <div class="ocean-panel-inner">
          <div class="ocean-panel-topline">
            <AppLogo :alwaysShowTitle="true" />
            <span class="ocean-status"><i /> ONLINE</span>
          </div>
          <div :class="`${prefixCls}-form`" class="ocean-form-wrap">
            <LoginForm />
            <ForgetPasswordForm />
            <RegisterForm />
            <MobileForm />
            <QrCodeForm />
          </div>
          <p class="ocean-panel-footer">SECURE ACCESS · BUILT FOR BETTER PRODUCTS</p>
        </div>
      </section>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
  import { AppLogo, AppLocalePicker, AppDarkModeToggle } from '/@/components/Application';
  import LoginForm from './LoginForm.vue';
  import ForgetPasswordForm from './ForgetPasswordForm.vue';
  import RegisterForm from './RegisterForm.vue';
  import MobileForm from './MobileForm.vue';
  import QrCodeForm from './QrCodeForm.vue';
  import { useGlobSetting } from '/@/hooks/setting';
  import { useI18n } from '/@/hooks/web/useI18n';
  import { useDesign } from '/@/hooks/web/useDesign';
  import { useLocaleStore } from '/@/store/modules/locale';
  import { useLoginState } from './useLogin';

  defineProps({ sessionTimeout: { type: Boolean } });

  const globSetting = useGlobSetting();
  const { prefixCls } = useDesign('login');
  const { t } = useI18n();
  const localeStore = useLocaleStore();
  const showLocale = localeStore.getShowPicker;
  const title = computed(() => globSetting?.title ?? 'Sentiment Plus');
  const { handleBackLogin } = useLoginState();
  const loginRoot = ref<HTMLElement>();
  const rippleLayer = ref<HTMLElement>();
  const cursorLight = ref<HTMLElement>();
  let gsapContext: any;
  let lastRippleAt = 0;
  let lastRippleX = -Infinity;
  let lastRippleY = -Infinity;

  declare global {
    interface Window {
      gsap?: any;
    }
  }

  function spawnRipple(x: number, y: number) {
    const layer = rippleLayer.value;
    if (!layer) return;
    const ripple = document.createElement('span');
    ripple.className = 'ocean-ripple';
    ripple.style.left = `${x}px`;
    ripple.style.top = `${y}px`;
    for (let index = 0; index < 3; index += 1) {
      const ring = document.createElement('i');
      ring.className = `ocean-ripple-ring ocean-ripple-ring-${index + 1}`;
      ripple.appendChild(ring);
    }
    layer.appendChild(ripple);
    requestAnimationFrame(() => ripple.classList.add('is-visible'));
    window.setTimeout(() => ripple.remove(), 1650);
  }

  function handlePointerMove(event: PointerEvent) {
    if (event.pointerType === 'touch') return;
    const root = loginRoot.value;
    if (!root) return;
    const bounds = root.getBoundingClientRect();
    const x = event.clientX - bounds.left;
    const y = event.clientY - bounds.top;
    root.style.setProperty('--pointer-x', `${x}px`);
    root.style.setProperty('--pointer-y', `${y}px`);
    if (cursorLight.value && window.gsap) {
      const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      window.gsap[reduced ? 'set' : 'to'](cursorLight.value, reduced ? { x, y } : {
        x,
        y,
        duration: 0.42,
        ease: 'power3.out',
        overwrite: 'auto',
      });
    }
    const now = Date.now();
    const distance = Math.hypot(x - lastRippleX, y - lastRippleY);
    if (now - lastRippleAt > 125 && distance > 18) {
      lastRippleAt = now;
      lastRippleX = x;
      lastRippleY = y;
      spawnRipple(x, y);
    }
  }

  onMounted(() => {
    handleBackLogin();
    const root = loginRoot.value;
    const engine = window.gsap;
    if (!root || !engine) return;
    gsapContext = engine.context(() => {
      const mm = engine.matchMedia();
      mm.add({
        reduceMotion: '(prefers-reduced-motion: reduce)',
        finePointer: '(hover: hover) and (pointer: fine)',
      }, (context: any) => {
        const { reduceMotion, finePointer } = context.conditions;
        if (reduceMotion) {
          engine.set('.ocean-intro > *, .ocean-login-panel', { autoAlpha: 1, clearProps: 'transform' });
          return;
        }
        engine.from('.ocean-intro > *', {
          y: 24,
          autoAlpha: 0,
          duration: 0.85,
          ease: 'power3.out',
          stagger: 0.08,
        });
        engine.from('.ocean-login-panel', {
          y: 20,
          autoAlpha: 0,
          duration: 0.9,
          ease: 'power3.out',
        }, '-=0.58');
        engine.to('.ocean-sun', {
          x: 36,
          y: 18,
          duration: 6,
          ease: 'sine.inOut',
          repeat: -1,
          yoyo: true,
        });
        if (finePointer) {
          engine.to('.ocean-panel-glow', {
            scale: 1.16,
            autoAlpha: 0.48,
            duration: 2.6,
            ease: 'sine.inOut',
            repeat: -1,
            yoyo: true,
          });
        }
      });
    }, root);
  });
  onBeforeUnmount(() => {
    gsapContext?.revert();
    rippleLayer.value?.replaceChildren();
  });
</script>

<style lang="less">
  @prefix-cls: ~'@{namespace}-login';

  .@{prefix-cls}.ocean-login {
    --pointer-x: 72%;
    --pointer-y: 20%;
    min-height: 100%;
    overflow: hidden;
    color: #f7fffe;
    background: #063d52;
    isolation: isolate;

    .ocean-backdrop,
    .ocean-grain,
    .ocean-ripples {
      position: absolute;
      inset: 0;
      pointer-events: none;
    }

    .ocean-backdrop {
      z-index: -2;
      overflow: hidden;
      background-color: #087c8d;
      background-image:
        linear-gradient(112deg, rgba(3, 50, 66, 0.54), rgba(13, 164, 170, 0.2) 55%, rgba(255, 224, 146, 0.28)),
        url('/resource/img/maldives-surface.png');
      background-position: center, center;
      background-size: cover, cover;
      background-blend-mode: multiply, screen;
    }

    .ocean-sun {
      position: absolute;
      top: -22vh;
      right: -5vw;
      width: 72vw;
      height: 72vw;
      max-width: 920px;
      max-height: 920px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(255, 249, 201, 0.8) 0, rgba(255, 219, 145, 0.28) 22%, transparent 66%);
      filter: blur(6px);
      opacity: 0.9;
    }

    .ocean-cursor-light {
      position: absolute;
      z-index: 2;
      top: 0;
      left: 0;
      width: 260px;
      height: 260px;
      border-radius: 50%;
      pointer-events: none;
      transform: translate(-50%, -50%);
      background: radial-gradient(circle, rgba(255, 248, 201, 0.26), rgba(255, 248, 201, 0.08) 28%, transparent 70%);
      mix-blend-mode: screen;
      filter: blur(3px);
    }

    .ocean-haze {
      position: absolute;
      width: 55vw;
      height: 55vw;
      border-radius: 50%;
      filter: blur(40px);
      opacity: 0.42;
      animation: ocean-drift 14s ease-in-out infinite alternate;
    }

    .ocean-haze-one { left: -18vw; bottom: -32vw; background: #005f78; }
    .ocean-haze-two { right: 4vw; bottom: -42vw; background: #4fd2be; animation-delay: -5s; }

    .ocean-surface {
      position: absolute;
      right: -10%;
      bottom: -12%;
      left: -10%;
      height: 60%;
      opacity: 0.46;
      transform: rotate(-4deg) scale(1.15);
      background: repeating-linear-gradient(174deg, transparent 0 13px, rgba(239, 255, 231, 0.22) 14px 16px, transparent 17px 31px);
      mix-blend-mode: screen;
    }

    .ocean-surface-back { animation: ocean-shimmer 10s linear infinite; opacity: 0.16; }
    .ocean-surface-front { bottom: -18%; animation: ocean-shimmer 7s linear infinite reverse; opacity: 0.2; }

    .ocean-grain {
      z-index: 1;
      opacity: 0.08;
      background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 160 160' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='.4'/%3E%3C/svg%3E");
    }

    .ocean-ripples { z-index: 3; overflow: hidden; }
    .ocean-ripple {
      position: absolute;
      width: 1px;
      height: 1px;
      transform: translate(-50%, -50%);
      pointer-events: none;
    }
    .ocean-ripple-ring {
      position: absolute;
      top: 0;
      left: 0;
      width: 14px;
      height: 14px;
      border: 1px solid rgba(224, 255, 248, 0.52);
      border-radius: 50%;
      transform: translate(-50%, -50%) scale(0.18);
      opacity: 0.54;
      box-shadow: 0 0 10px rgba(201, 255, 239, 0.18);
      transition: transform 1.35s cubic-bezier(0.16, 0.72, 0.28, 1), opacity 1.00s ease;
    }
    .ocean-ripple-ring-2 { width: 24px; height: 24px; transition-delay: 0.04s; opacity: 0.4; }
    .ocean-ripple-ring-3 { width: 34px; height: 34px; transition-delay: 0.08s; opacity: 0.3; }
    .ocean-ripple.is-visible .ocean-ripple-ring-1 { transform: translate(-50%, -50%) scale(3.8); opacity: 0; }
    .ocean-ripple.is-visible .ocean-ripple-ring-2 { transform: translate(-50%, -50%) scale(4.5); opacity: 0; }
    .ocean-ripple.is-visible .ocean-ripple-ring-3 { transform: translate(-50%, -50%) scale(5.2); opacity: 0; }

    .ocean-toolbar { position: absolute; z-index: 6; color: #fff; }
    .ocean-locale { top: 20px; right: 78px; }
    .ocean-theme { top: 15px; right: 24px; }

    .ocean-shell { z-index: 4; display: flex; align-items: center; justify-content: space-between; width: min(1240px, calc(100% - 80px)); gap: 7vw; }
    .ocean-intro { width: min(560px, 48%); padding-bottom: 5vh; text-shadow: 0 8px 30px rgba(0, 49, 64, 0.18); }
    .ocean-brand-mark { display: flex; align-items: center; gap: 12px; margin-bottom: 32px; color: rgba(239, 255, 246, 0.84); font-size: 11px; letter-spacing: 0.28em; }
    .ocean-brand-dot { width: 10px; height: 10px; border: 2px solid #fff2b9; border-radius: 50%; box-shadow: 0 0 18px #fff2b9; }
    .ocean-intro h1 { margin: 0; color: #fffef4; font-size: clamp(42px, 5.2vw, 78px); font-weight: 300; line-height: 1.08; letter-spacing: -0.045em; }
    .ocean-intro h1 em { color: #fff0ae; font-style: normal; font-weight: 600; }
    .ocean-intro p { max-width: 430px; margin: 28px 0 0; color: rgba(239, 255, 249, 0.78); font-size: 16px; line-height: 1.9; }
    .ocean-intro-meta { display: flex; align-items: center; gap: 12px; margin-top: 40px; color: rgba(242, 255, 247, 0.58); font-size: 10px; letter-spacing: 0.18em; }
    .ocean-meta-line { width: 52px; height: 1px; background: #ffdfa0; box-shadow: 0 0 12px #ffdfa0; }
    .ocean-scroll-hint { display: flex; align-items: center; gap: 12px; margin-top: 80px; color: rgba(255,255,255,0.5); font-size: 9px; letter-spacing: 0.2em; }
    .ocean-scroll-hint span { display: block; width: 34px; height: 1px; background: rgba(255,255,255,0.6); }

    .ocean-login-panel { position: relative; width: min(440px, 44vw); min-width: 360px; padding: 1px; border: 1px solid rgba(255,255,255,0.46); border-radius: 28px; background: linear-gradient(145deg, rgba(255,255,255,0.32), rgba(255,255,255,0.06)); box-shadow: 0 28px 90px rgba(0, 45, 65, 0.3), inset 0 1px rgba(255,255,255,0.45); backdrop-filter: blur(22px); }
    .ocean-panel-glow { position: absolute; top: -40px; right: 20px; width: 120px; height: 120px; border-radius: 50%; background: #fff2ad; filter: blur(50px); opacity: 0.35; pointer-events: none; }
    .ocean-panel-inner { position: relative; padding: 28px 32px 24px; border-radius: 27px; background: linear-gradient(150deg, rgba(5, 61, 77, 0.6), rgba(3, 45, 66, 0.38)); }
    .ocean-panel-topline { display: flex; align-items: center; justify-content: space-between; min-height: 42px; }
    .ocean-panel-topline .@{namespace}-app-logo { position: static; width: auto; height: 42px; }
    .ocean-panel-topline .@{namespace}-app-logo__title { color: #fff; font-size: 16px; }
    .ocean-panel-topline .@{namespace}-app-logo img { max-width: 170px; max-height: 42px; }
    .ocean-status { color: rgba(231, 255, 239, 0.64); font-size: 9px; letter-spacing: 0.16em; }
    .ocean-status i { display: inline-block; width: 6px; height: 6px; margin-right: 7px; border-radius: 50%; background: #a9f4bc; box-shadow: 0 0 12px #a9f4bc; }
    .ocean-form-wrap { margin-top: 28px; }
    .ocean-form-wrap .login-form-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 24px; }
    .ocean-form-wrap .login-form-heading h2 { flex: 0 0 auto; margin: 0; }
    .ocean-form-wrap .login-form-switches { display: flex; align-items: center; gap: 8px; }
    .ocean-form-wrap .login-form-switches-full { width: 100%; gap: 8px; }
    .ocean-form-wrap .login-form-switches .ant-btn { flex: 1 1 0; min-width: 0; height: 36px; padding: 0 8px; border: 1px solid rgba(235, 255, 249, 0.25); border-radius: 10px; color: rgba(239, 255, 250, 0.82); background: rgba(235, 255, 249, 0.08); }
    .ocean-form-wrap .login-form-switches .ant-btn.is-active { border-color: rgba(255, 241, 178, 0.72); color: #064459; background: linear-gradient(110deg, rgba(255, 241, 178, 0.9), rgba(182, 244, 221, 0.86)); box-shadow: 0 6px 16px rgba(255, 221, 153, 0.12); }
    .ocean-form-wrap .login-form-switches .ant-btn.is-active:hover { color: #064459; }
    .ocean-form-wrap .login-form-switches .ant-btn:hover { border-color: rgba(255, 241, 178, 0.72); color: #fff1b2; }
    .ocean-form-wrap h2 { margin-bottom: 24px; color: #fff; font-size: 28px; font-weight: 500; text-align: left; }
    .ocean-form-wrap form { padding: 0; }
    .ocean-form-wrap .ant-form-item { margin-bottom: 18px; }
    .ocean-form-wrap .ant-input-affix-wrapper,
    .ocean-form-wrap .ant-input { min-width: 0; border: 1px solid rgba(235, 255, 249, 0.22); border-radius: 13px; color: #fff; background: rgba(235, 255, 249, 0.1); box-shadow: none; }
    .ocean-form-wrap .ant-input-affix-wrapper:hover,
    .ocean-form-wrap .ant-input-affix-wrapper:focus-within { border-color: rgba(255, 236, 172, 0.85); background: rgba(235, 255, 249, 0.16); box-shadow: 0 0 0 3px rgba(255, 224, 162, 0.1); }
    .ocean-form-wrap .ant-input::placeholder,
    .ocean-form-wrap .ant-input-affix-wrapper input::placeholder { color: rgba(239, 255, 250, 0.52); }
    .ocean-form-wrap .ant-input-prefix, .ocean-form-wrap .ant-input-password-icon { color: rgba(235, 255, 249, 0.7); }
    .ocean-form-wrap .ant-btn-primary { height: 48px; border: 0; border-radius: 13px; color: #064459; font-weight: 700; background: linear-gradient(110deg, #fff1b2, #b6f4dd); box-shadow: 0 14px 30px rgba(255, 221, 153, 0.2); }
    .ocean-form-wrap .ant-btn-primary:hover { color: #064459; background: linear-gradient(110deg, #fff7ce, #d0ffed); transform: translateY(-1px); }
    .ocean-form-wrap .ant-checkbox-wrapper, .ocean-form-wrap .ant-btn-link, .ocean-form-wrap .ant-divider-inner-text { color: rgba(239, 255, 250, 0.65); }
    .ocean-form-wrap .login-secondary-actions .ant-form-item-control-input-content { display: flex; align-items: center; justify-content: flex-end; gap: 4px; }
    .ocean-form-wrap .login-secondary-actions .ant-btn-link:first-child { padding-left: 0; }
    .ocean-form-wrap .ant-divider { border-color: rgba(239, 255, 250, 0.18); }
    .ocean-form-wrap .ant-btn:not(.ant-btn-primary) { border-color: rgba(235, 255, 249, 0.23); border-radius: 11px; color: rgba(239, 255, 250, 0.78); background: rgba(235, 255, 249, 0.08); }
    .ocean-form-wrap .ant-btn:not(.ant-btn-primary):hover { border-color: #fff1b2; color: #fff1b2; }
    .ocean-panel-footer { margin: 24px 0 0; color: rgba(232, 255, 248, 0.35); font-size: 9px; letter-spacing: 0.15em; text-align: center; }

    @media (max-width: 1100px) {
      .ocean-shell { width: min(700px, calc(100% - 48px)); justify-content: center; }
      .ocean-intro { display: none; }
      .ocean-login-panel { width: min(440px, 100%); }
    }

    @media (max-width: 480px) {
      .ocean-shell { width: calc(100% - 28px); }
      .ocean-login-panel { min-width: 0; border-radius: 22px; }
      .ocean-panel-inner { padding: 22px 18px 20px; border-radius: 21px; }
      .ocean-status { display: none; }
      .ocean-form-wrap h2 { font-size: 25px; }
      .ocean-form-wrap .login-form-heading { gap: 6px; }
      .ocean-form-wrap .login-form-switches { gap: 4px; }
      .ocean-form-wrap .login-form-switches .ant-btn { padding: 0 4px; font-size: 12px; }
      .ocean-locale { right: 58px; }
    }
  }

  @keyframes ocean-shimmer { from { transform: rotate(-4deg) translateX(-3%); } to { transform: rotate(-4deg) translateX(3%); } }
  @keyframes ocean-drift { from { transform: translate3d(-4%, 0, 0) scale(1); } to { transform: translate3d(5%, -4%, 0) scale(1.08); } }

  @media (prefers-reduced-motion: reduce) {
    .@{prefix-cls}.ocean-login *,
    .@{prefix-cls}.ocean-login *::before,
    .@{prefix-cls}.ocean-login *::after {
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
      scroll-behavior: auto !important;
      transition-duration: 0.01ms !important;
    }
    .@{prefix-cls}.ocean-login .ocean-cursor-light,
    .@{prefix-cls}.ocean-login .ocean-ripples { display: none; }
  }

  html[data-theme='dark'] .@{prefix-cls}.ocean-login { background: #042d40; }
</style>
