<template>
  <main class="sentiment-welcome" @wheel="handleWheel">
    <div class="welcome-image" aria-hidden="true" />
    <div class="welcome-wash" aria-hidden="true" />
    <div class="welcome-grain" aria-hidden="true" />
    <header class="welcome-header"><span class="welcome-kicker">PRODUCT SENTIMENT INTELLIGENCE</span><span class="welcome-index">01 / 02</span></header>
    <section ref="welcomeContent" class="welcome-content" aria-label="Sentiment Plus"><div class="welcome-logo-mark" aria-hidden="true"><span /><span /><span /></div><h1>Sentiment</h1><p>看见产品与用户之间的每一层情绪波纹</p></section>
    <button class="welcome-scroll" type="button" @click="enterProduct"><span class="welcome-scroll-line" /><span>SCROLL TO ENTER</span><span class="welcome-scroll-arrow">↓</span></button>
  </main>
</template>
<script lang="ts" setup>
  import { onBeforeUnmount, onMounted, ref } from 'vue';
  import { useRouter } from 'vue-router';
  import { PageEnum } from '/@/enums/pageEnum';
  declare global { interface Window { gsap?: any } }
  const router = useRouter(); const welcomeContent = ref<HTMLElement>(); let isLeaving = false; let gsapContext: any;
  function enterProduct() { if (isLeaving) return; isLeaving = true; document.documentElement.classList.add('welcome-is-leaving'); const engine = window.gsap; if (!engine || !welcomeContent.value) { router.replace(PageEnum.BASE_HOME); return; } engine.to(welcomeContent.value, { y: -80, autoAlpha: 0, duration: .55, ease: 'power2.inOut', onComplete: () => router.replace(PageEnum.BASE_HOME) }); }
  function handleWheel(event: WheelEvent) { if (event.deltaY > 0) enterProduct(); }
  onMounted(() => { const engine = window.gsap; if (!engine || !welcomeContent.value) return; gsapContext = engine.context(() => { const mm = engine.matchMedia(); mm.add('(prefers-reduced-motion: reduce)', () => engine.set(welcomeContent.value, { autoAlpha: 1, clearProps: 'transform' })); mm.add('(prefers-reduced-motion: no-preference)', () => engine.from(welcomeContent.value, { y: 22, autoAlpha: 0, duration: .9, ease: 'power3.out' })); }, welcomeContent.value); });
  onBeforeUnmount(() => { gsapContext?.revert(); document.documentElement.classList.remove('welcome-is-leaving'); });
</script>
<style lang="less" scoped>
  .sentiment-welcome { position:relative; display:grid; min-height:100dvh; overflow:hidden; color:#f5fffb; isolation:isolate; background:#073e74; }
  .welcome-image,.welcome-wash,.welcome-grain { position:absolute; inset:0; pointer-events:none; }
  .welcome-image { z-index:-3; background:url('/resource/img/sentiment-welcome-coast.png') left center/cover no-repeat; filter:saturate(.88) contrast(.96); transform:scale(1.04); }
  .welcome-wash { z-index:-2; background:linear-gradient(90deg,rgba(5,111,138,.18),rgba(8,71,183,.54) 50%,rgba(31,32,153,.82)),radial-gradient(circle at 48% 48%,rgba(39,96,232,.12),transparent 42%),linear-gradient(180deg,rgba(3,69,119,.18),rgba(12,23,113,.44)); mix-blend-mode:multiply; }
  .welcome-grain { z-index:-1; opacity:.12; background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 160 160' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.78' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='.32'/%3E%3C/svg%3E"); }
  .welcome-header { position:absolute; top:30px; left:clamp(24px,5vw,76px); right:clamp(24px,5vw,76px); display:flex; align-items:center; justify-content:space-between; color:rgba(237,255,250,.72); font-size:10px; letter-spacing:.22em; }
  .welcome-content { align-self:center; justify-self:center; display:flex; flex-direction:column; align-items:center; text-align:center; transform:translateY(-2vh); }
  .welcome-logo-mark { position:relative; width:106px; height:72px; margin-bottom:28px; opacity:.92; } .welcome-logo-mark span { position:absolute; display:block; border:8px solid rgba(244,255,251,.92); border-radius:3px; } .welcome-logo-mark span:nth-child(1){top:0;left:0;width:40px;height:48px;border-right:0}.welcome-logo-mark span:nth-child(2){top:16px;left:32px;width:54px;height:32px;border-left:0;border-bottom:0;transform:skewX(-32deg)}.welcome-logo-mark span:nth-child(3){right:0;bottom:0;width:54px;height:24px;border-left:0;border-top:0}
  .welcome-content h1 { margin:0; color:#f5fffb; font-size:clamp(74px,13vw,184px); font-weight:600; line-height:.9; letter-spacing:-.085em; text-shadow:0 14px 40px rgba(0,34,110,.24); } .welcome-content p { margin:30px 0 0; color:rgba(239,255,251,.76); font-size:clamp(13px,1.4vw,17px); letter-spacing:.18em; }
  .welcome-scroll { position:absolute; right:clamp(24px,5vw,76px); bottom:32px; display:flex; align-items:center; gap:12px; border:0; color:rgba(239,255,251,.75); font:inherit; font-size:10px; letter-spacing:.2em; background:transparent; cursor:pointer; } .welcome-scroll-line{width:40px;height:1px;background:rgba(239,255,251,.62)} .welcome-scroll-arrow{font-size:18px;line-height:1;transition:transform .25s ease}.welcome-scroll:hover .welcome-scroll-arrow{transform:translateY(4px)}
  @media(max-width:680px){.welcome-header{top:22px;font-size:8px}.welcome-index{display:none}.welcome-image{background-position:28% center}.welcome-content p{max-width:280px;line-height:1.7;letter-spacing:.1em}.welcome-scroll{right:50%;transform:translateX(50%);white-space:nowrap}}
  @media(prefers-reduced-motion:reduce){.welcome-scroll-arrow{transition:none}.welcome-image{transform:none}}
</style>
