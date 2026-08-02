<template>
  <main class="sentiment-home">
    <div class="home-light home-light-a" />
    <div class="home-light home-light-b" />
    <div class="home-grid" />

    <header class="home-nav">
      <button class="home-brand" type="button" @click="scrollToTop">
        <span class="brand-mark"><i /><i /><i /></span>
        <span class="brand-word">Sentiment</span>
      </button>
      <nav class="home-links" aria-label="主导航">
        <button class="is-active" type="button" @click="scrollToTop">首页</button>
        <button type="button" @click="scrollToSection('insights')">产品介绍</button>
        <button type="button" @click="scrollToSection('solutions')">解决方案</button>
        <button type="button" @click="scrollToSection('footer')">关于我们</button>
      </nav>
      <div class="home-nav-actions">
        <button class="login-link" type="button" @click="logout">退出登录</button>
        <button class="nav-cta" type="button" @click="scrollToSection('solutions')">开始使用 <span>↗</span></button>
      </div>
      <button class="mobile-menu" type="button" aria-label="展开导航" @click="mobileOpen = !mobileOpen">{{ mobileOpen ? '×' : '☰' }}</button>
    </header>

    <nav v-if="mobileOpen" class="mobile-nav">
      <button type="button" @click="scrollToTop">首页</button>
      <button type="button" @click="scrollToSection('insights')">产品介绍</button>
      <button type="button" @click="scrollToSection('solutions')">解决方案</button>
      <button type="button" @click="scrollToSection('footer')">关于我们</button>
      <button type="button" @click="logout">退出登录</button>
    </nav>

    <section class="home-hero">
      <div class="hero-copy">
        <span class="home-eyebrow"><i /> 产品情绪洞察平台</span>
        <h1>看见用户的<br /><em>真实感受。</em></h1>
        <p>从海量反馈中，捕捉情绪的方向与温度。<br />让每一次产品决策，都更接近用户心里的答案。</p>
        <div class="hero-actions">
          <button class="primary-action" type="button" @click="scrollToSection('insights')">进入我的空间 <span>→</span></button>
          <button class="secondary-action" type="button" @click="scrollToSection('solutions')"><b>▶</b> 看看它如何工作</button>
        </div>
        <div class="hero-proof"><span class="proof-avatars"><i>J</i><i>L</i><i>Y</i><i>+</i></span><span>被 2,000+ 个团队<br />用来听见用户</span><b>✓</b></div>
      </div>

      <div class="hero-visual" aria-label="产品情绪趋势视觉展示">
        <div class="visual-orb"><span>情绪<br /><b>流动</b></span></div>
        <div class="floating-note note-a"><i>♥</i><span><b>正向情绪</b><small>+ 8.6% 本周</small></span></div>
        <div class="floating-note note-b"><i>◌</i><span><b>12,840</b><small>条真实声音</small></span></div>
        <span class="visual-status">◉ Live signal · 现在 <b>↗</b></span>
      </div>
    </section>

    <section class="signal-strip"><span>你的产品，正在被这样感受</span><div><b>● 体验更顺滑</b><b>● 值得被推荐</b><b>● 还可以更贴心</b><b>● 我们听见了</b></div></section>

    <section id="insights" class="insights-section">
      <div class="section-intro"><div><span class="section-kicker">从反馈，到洞察</span><h2>把分散的声音，<br /><em>汇成清晰的方向。</em></h2></div><p>不止告诉你发生了什么，<br />也帮你理解为什么，以及下一步。</p></div>
      <div class="insight-grid">
        <button v-for="(item, index) in insights" :key="item.title" class="insight-card" :class="`card-${index}`" type="button" @click="openInsight(item.route)"><div class="card-top"><i>{{ item.icon }}</i><span>{{ item.label }}</span><b>↗</b></div><h3>{{ item.title }}</h3><p>{{ item.description }}</p><div class="card-line" /></button>
      </div>
    </section>

    <section id="solutions" class="quiet-cta"><div><span class="section-kicker">准备好了吗</span><h2>从今天开始，<br /><em>听见更多可能。</em></h2></div><button class="primary-action" type="button" @click="openInsight('/system/user/insight')">开始探索 <span>→</span></button><div class="quiet-checks"><span>✓ 无需信用卡</span><span>✓ 5 分钟上手</span></div></section>

    <footer id="footer" class="home-footer"><span><i class="brand-mark"><i /><i /><i /></i><b class="brand-word">Sentiment</b></span><p>让每一个真实的声音，都被温柔地看见。</p><small>© 2026 Insight · Made for clarity</small></footer>
  </main>
</template>

<script lang="ts" setup>
  import { onBeforeUnmount, onMounted, ref } from 'vue';
  import { useRouter } from 'vue-router';
  import { useUserStore } from '/@/store/modules/user';

  const router = useRouter();
  const userStore = useUserStore();
  const mobileOpen = ref(false);
  const insights = [
    { label: '情绪趋势', icon: '≈', title: '本周品牌好感度正在回升', description: '基于真实反馈，正向情绪较上周持续提升。', route: '/system/user/insight' },
    { label: '用户声音', icon: '✦', title: '“轻松上手”成为高频关键词', description: '用户在最近的评价中持续提到体验顺滑、反馈及时。', route: '/system/user/insight?tab=work' },
    { label: '行动建议', icon: '◌', title: '让热爱转化为下一次选择', description: '还有 3 个可验证的优化机会，等待你打开。', route: '/system/user/insight?tab=advice' },
  ];

  function scrollToTop() { mobileOpen.value = false; window.scrollTo({ top: 0, behavior: 'smooth' }); }
  function scrollToSection(id: string) { mobileOpen.value = false; document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' }); }
  function openInsight(route: string) { router.push(route); }
  async function logout() { await userStore.logout(true); }
  onMounted(() => document.title = 'Sentiment · 产品情绪洞察');
  onBeforeUnmount(() => { mobileOpen.value = false; });
</script>

<style lang="less" scoped>
  .sentiment-home { --ink: #214d58; --muted: #75979b; --teal: #167f87; position: relative; min-height: 100dvh; overflow: hidden; color: var(--ink); background: radial-gradient(circle at 72% -5%, #d9f7f5 0, transparent 31rem), #f3fbfc; }
  .home-light, .home-grid { position: absolute; pointer-events: none; }
  .home-light { border-radius: 50%; filter: blur(6px); opacity: .5; }
  .home-light-a { width: 300px; height: 300px; right: -80px; top: 140px; background: #d1f2e6; }
  .home-light-b { width: 240px; height: 240px; left: -140px; top: 430px; background: #cdecef; }
  .home-grid { z-index: 0; top: 75px; right: 0; width: 50%; height: 560px; opacity: .22; background-image: linear-gradient(rgba(110, 193, 188, .22) 1px, transparent 1px), linear-gradient(90deg, rgba(110, 193, 188, .22) 1px, transparent 1px); background-size: 48px 48px; transform: rotate(-13deg) scale(1.35); }
  .home-nav { position: sticky; top: 0; z-index: 10; display: flex; align-items: center; justify-content: space-between; height: 78px; padding: 0 clamp(22px, 5vw, 76px); border-bottom: 1px solid rgba(64, 137, 143, .08); background: rgba(243, 251, 252, .74); backdrop-filter: blur(22px); }
  .home-brand, .home-links button, .login-link, .mobile-menu, .mobile-nav button { border: 0; background: transparent; cursor: pointer; color: inherit; }
  .home-brand { display: flex; align-items: center; gap: 10px; padding: 0; }
  .brand-word { color: #214d58; font-size: 22px; font-weight: 600; line-height: .9; letter-spacing: -.085em; }
  .brand-mark { position: relative; display: inline-block; width: 31px; height: 31px; border-radius: 12px 12px 12px 3px; background: linear-gradient(135deg, #1aa2a3, #82d9c2); box-shadow: 0 7px 18px rgba(25, 149, 144, .18); } .brand-mark i { position: absolute; display: block; border: 2px solid #f1fffb; border-radius: 2px; } .brand-mark i:nth-child(1) { top: 7px; left: 6px; width: 11px; height: 9px; border-right: 0; } .brand-mark i:nth-child(2) { top: 11px; left: 13px; width: 12px; height: 8px; border-left: 0; border-bottom: 0; transform: skewX(-25deg); } .brand-mark i:nth-child(3) { right: 4px; bottom: 7px; width: 11px; height: 6px; border-left: 0; border-top: 0; }
  .home-brand small { display: block; margin-top: 2px; color: #8badb0; font-size: 7px; letter-spacing: .24em; text-align: left; }
  .home-links { display: flex; gap: 31px; }
  .home-links button, .login-link { color: #688b91; font-size: 13px; transition: .2s; }
  .home-links button:hover, .home-links .is-active, .login-link:hover { color: var(--ink); }
  .home-nav-actions { display: flex; align-items: center; gap: 20px; }
  .login-link { color: var(--ink); font-weight: 600; }
  .nav-cta, .primary-action, .secondary-action { border: 0; border-radius: 14px; cursor: pointer; font-size: 13px; font-weight: 700; transition: transform .2s, box-shadow .2s; }
  .nav-cta { min-height: 40px; padding: 0 17px; color: #f5fffc; background: #167f87; box-shadow: 0 10px 22px rgba(22, 127, 135, .17); }
  .nav-cta:hover, .primary-action:hover, .secondary-action:hover { transform: translateY(-2px); }
  .mobile-menu, .mobile-nav { display: none; }
  .home-hero { position: relative; z-index: 1; display: grid; grid-template-columns: minmax(0, 1fr) minmax(460px, 1.02fr); align-items: center; gap: 50px; max-width: 1320px; min-height: 650px; margin: auto; padding: 74px clamp(22px, 6vw, 90px) 75px; }
  .home-eyebrow, .section-kicker { display: inline-flex; align-items: center; gap: 9px; color: #38878a; font-size: 11px; font-weight: 800; letter-spacing: .13em; text-transform: uppercase; }
  .home-eyebrow i { width: 7px; height: 7px; border-radius: 50%; background: #56c1af; box-shadow: 0 0 0 5px rgba(86, 193, 175, .12); }
  .hero-copy h1 { margin: 24px 0 25px; color: var(--ink); font-size: clamp(52px, 6.5vw, 88px); font-weight: 700; line-height: 1.08; letter-spacing: -.075em; }
  .hero-copy h1 em, .section-intro h2 em, .quiet-cta h2 em { color: #31a49d; font-style: normal; }
  .hero-copy p, .section-intro p { color: var(--muted); font-size: 16px; line-height: 1.85; }
  .hero-actions { display: flex; gap: 12px; margin-top: 34px; }
  .primary-action { display: inline-flex; align-items: center; gap: 10px; min-height: 46px; padding: 0 20px; color: #f5fffc; background: #167f87; box-shadow: 0 10px 22px rgba(22, 127, 135, .21); }
  .secondary-action { display: inline-flex; align-items: center; gap: 9px; min-height: 46px; padding: 0 18px; color: #426e76; border: 1px solid rgba(63, 130, 134, .18); background: rgba(255, 255, 255, .64); }
  .secondary-action b { display: grid; place-items: center; width: 22px; height: 22px; border-radius: 50%; color: #288e8c; background: #d4f1e9; font-size: 10px; }
  .hero-proof { display: flex; align-items: center; gap: 12px; margin-top: 50px; color: #87a2a5; font-size: 11px; line-height: 1.55; }
  .proof-avatars { display: flex; padding-left: 4px; }
  .proof-avatars i { display: grid; place-items: center; width: 27px; height: 27px; margin-left: -5px; border: 2px solid #f3fbfc; border-radius: 50%; color: #4f8b8f; background: #d5eeeb; font-size: 9px; font-style: normal; }
  .proof-avatars i:nth-child(2) { color: #a27351; background: #f0e5d4; } .proof-avatars i:nth-child(3) { color: #517d96; background: #cbe4f0; } .proof-avatars i:last-child { color: #6c9398; background: #fff; }
  .hero-proof b { color: #4bb4a2; }
  .hero-visual { position: relative; height: 465px; overflow: hidden; border-radius: 40px; background: linear-gradient(145deg, #d9f4ef 0%, #a8ddd8 37%, #88c9d4 75%, #bee8e8 100%); box-shadow: inset 0 0 0 1px rgba(255,255,255,.46), 0 25px 70px rgba(87,160,162,.15); }
  .hero-visual:before { position: absolute; inset: 0; content: ''; opacity: .22; background-image: linear-gradient(rgba(255,255,255,.42) 1px, transparent 1px), linear-gradient(90deg,rgba(255,255,255,.42) 1px,transparent 1px); background-size: 48px 48px; transform: rotate(-13deg) scale(1.35); }
  .visual-orb { position: absolute; top: 50%; left: 50%; z-index: 2; display: grid; place-items: center; width: 250px; height: 250px; border-radius: 50%; color: #39767d; text-align: center; font-size: 17px; line-height: 1.35; background: radial-gradient(circle at 35% 30%, rgba(255,255,255,.8), rgba(156,220,210,.35) 45%, rgba(59,162,164,.28)); box-shadow: inset -20px -30px 35px rgba(54,150,164,.2), inset 13px 15px 25px rgba(255,255,255,.68), 0 30px 60px rgba(70,145,154,.2); transform: translate(-50%, -50%); animation: orb-float 7s ease-in-out infinite; }
  .visual-orb b { color: #237f83; font-size: 26px; } .floating-note { position: absolute; z-index: 3; display: flex; align-items: center; gap: 10px; padding: 13px 16px; border: 1px solid rgba(255,255,255,.55); border-radius: 16px; color: #37737a; background: rgba(246,255,253,.52); box-shadow: 0 15px 28px rgba(36,123,132,.11); backdrop-filter: blur(14px); font-size: 11px; animation: note-float 4.5s ease-in-out infinite; } .floating-note i { display: grid; place-items: center; width: 29px; height: 29px; border-radius: 10px; color: #4cb49e; background: rgba(218,249,236,.82); font-style: normal; } .floating-note b, .floating-note small { display: block; } .floating-note small { margin-top: 3px; color: #6d9ba0; } .note-a { top: 24%; left: 8%; } .note-b { right: 7%; bottom: 21%; animation-delay: -1.8s; } .visual-status { position: absolute; bottom: 25px; left: 27px; z-index: 3; color: rgba(34,100,109,.66); font-size: 10px; letter-spacing: .04em; } .visual-status b { margin-left: 14px; }
  .signal-strip, .insights-section, .quiet-cta, .home-footer { position: relative; z-index: 1; max-width: 1165px; margin-right: auto; margin-left: auto; } .signal-strip { display: flex; align-items: center; justify-content: space-between; padding: 20px 0; border-top: 1px solid rgba(46,115,126,.15); border-bottom: 1px solid rgba(46,115,126,.15); color: #7b9da0; font-size: 11px; } .signal-strip > span { color: #3c747b; font-weight: 700; } .signal-strip div { display: flex; gap: 35px; } .signal-strip b { color: #6c9598; font-weight: 500; } .signal-strip b::first-letter { color: #65c5af; }
  .insights-section { padding: 125px 0 138px; } .section-intro { display: flex; align-items: end; justify-content: space-between; margin-bottom: 44px; } .section-kicker { margin-bottom: 15px; color: #70a2a1; font-size: 10px; } .section-intro h2, .quiet-cta h2 { color: #264e58; font-size: clamp(34px, 4.2vw, 58px); line-height: 1.12; letter-spacing: -.065em; } .section-intro h2 em { color: #77adb0; } .section-intro p { font-size: 13px; text-align: right; } .insight-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 17px; } .insight-card { display: block; width: 100%; min-height: 270px; padding: 22px; overflow: hidden; border: 1px solid rgba(44,127,132,.13); border-radius: 24px; position: relative; color: inherit; text-align: left; cursor: pointer; transition: transform .25s, box-shadow .25s; } .insight-card:hover { transform: translateY(-6px); box-shadow: 0 18px 35px rgba(66,146,147,.13); } .card-0 { background: linear-gradient(145deg, #e4f7ef, #c9ebe0); } .card-1 { background: linear-gradient(145deg, #e4f4f5, #cbe9e9); } .card-2 { background: linear-gradient(145deg, #fff2e5, #f7e2d4); } .card-top { display: flex; align-items: center; gap: 10px; color: #5b8d91; } .card-top i { display: grid; place-items: center; width: 32px; height: 32px; border-radius: 11px; color: #42a28f; background: rgba(255,255,255,.48); font-style: normal; } .card-top b { margin-left: auto; font-weight: 400; } .card-top span { font-size: 10px; letter-spacing: .1em; } .insight-card h3 { max-width: 260px; margin: 42px 0 13px; color: #2b626b; font-size: 23px; line-height: 1.28; letter-spacing: -.06em; } .insight-card p { max-width: 250px; color: #71989a; font-size: 12px; line-height: 1.7; } .card-line { position: absolute; right: 0; bottom: 0; left: 0; height: 4px; background: rgba(80,182,158,.44); }
  .quiet-cta { display: flex; align-items: center; gap: 40px; margin-bottom: 120px; padding: 74px 76px; overflow: hidden; border-radius: 31px; background: linear-gradient(125deg, #d7f2ec, #d9f0ee 56%, #e6f5f0); } .quiet-cta h2 { font-size: 45px; } .quiet-cta > .primary-action { margin-left: auto; } .quiet-checks { position: absolute; bottom: 21px; left: 77px; display: flex; gap: 16px; color: #6b9b9a; font-size: 10px; }
  .home-footer { display: flex; align-items: center; gap: 12px; padding: 28px 0 39px; border-top: 1px solid rgba(46,115,126,.15); color: #89a6a7; font-size: 11px; } .home-footer > span { display: flex; align-items: center; gap: 9px; color: #47747a; font-size: 14px; } .home-footer .brand-mark { width: 24px; height: 24px; font-size: 13px; } .home-footer small { margin-left: auto; }
  @keyframes orb-float { 0%,100% { transform: translate(-50%,-50%) translateY(0) rotate(0); } 50% { transform: translate(-50%,-50%) translateY(-12px) rotate(5deg); } } @keyframes note-float { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-8px); } }
  @media (max-width: 900px) { .home-hero { grid-template-columns: 1fr; } .hero-visual { width: 100%; max-width: 650px; margin: auto; } .signal-strip, .insights-section, .quiet-cta, .home-footer { margin-right: 24px; margin-left: 24px; } .auth-layout { gap: 50px; } }
  @media (max-width: 700px) { .home-nav { padding: 0 22px; } .home-links, .home-nav-actions { display: none; } .mobile-menu { display: block; color: var(--ink); font-size: 22px; } .mobile-nav { position: fixed; top: 68px; right: 16px; left: 16px; z-index: 9; display: grid; gap: 4px; padding: 13px; border: 1px solid rgba(46,115,126,.15); border-radius: 18px; background: rgba(249,255,254,.95); box-shadow: 0 14px 35px rgba(44,121,124,.12); } .mobile-nav button { padding: 12px; color: var(--ink); text-align: left; } .home-hero { gap: 43px; min-height: auto; padding-top: 44px; } .hero-copy h1 { font-size: 55px; } .hero-copy p { font-size: 14px; } .hero-actions { flex-direction: column; align-items: stretch; } .hero-actions button { width: 100%; } .hero-proof { margin-top: 29px; } .hero-visual { height: 390px; border-radius: 28px; } .visual-orb { width: 205px; height: 205px; } .signal-strip { flex-direction: column; align-items: flex-start; gap: 15px; } .signal-strip div { width: 100%; justify-content: space-between; gap: 10px; } .signal-strip b:nth-child(3), .signal-strip b:nth-child(4) { display: none; } .insights-section { padding: 85px 0; } .section-intro { display: block; } .section-intro p { margin-top: 20px; text-align: left; } .insight-grid { grid-template-columns: 1fr; } .insight-card { min-height: 230px; } .quiet-cta { display: block; margin-bottom: 80px; padding: 42px 27px 73px; } .quiet-cta h2 { font-size: 38px; } .quiet-cta > .primary-action { margin-top: 29px; } .quiet-checks { left: 27px; } .home-footer { flex-wrap: wrap; } .home-footer small { width: 100%; margin-left: 0; } }
  @media (prefers-reduced-motion: reduce) { .sentiment-home *, .sentiment-home *::before, .sentiment-home *::after { animation-duration: .01ms !important; animation-iteration-count: 1 !important; scroll-behavior: auto !important; transition-duration: .01ms !important; } }
</style>
