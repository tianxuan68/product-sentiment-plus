<template>
  <div class="m-shell m-theme">
    <router-view v-slot="{ Component }">
      <keep-alive include="MobileSelect,MobileBoard,MobileInsight">
        <component :is="Component" />
      </keep-alive>
    </router-view>

    <nav class="m-tabbar" aria-label="底部导航">
      <button
        v-for="tab in tabs"
        :key="tab.path"
        type="button"
        class="tab-item"
        :class="{ active: isActive(tab.path) }"
        @click="go(tab.path)"
      >
        <i class="tab-ico" v-html="tab.icon" />
        <span>{{ tab.label }}</span>
      </button>
    </nav>
  </div>
</template>

<script lang="ts" name="MobileShell" setup>
  import { useRoute, useRouter } from 'vue-router';
  import { PageEnum } from '/@/enums/pageEnum';
  import './mobile-theme.less';

  const route = useRoute();
  const router = useRouter();

  const tabs = [
    {
      label: '评论',
      path: PageEnum.MOBILE_SELECT,
      icon: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M4 4h7v7H4V4zm9 0h7v7h-7V4zM4 13h7v7H4v-7zm9 0h7v7h-7v-7z"/></svg>',
    },
    {
      label: '洞察',
      path: PageEnum.MOBILE_INSIGHT,
      icon: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 3a9 9 0 100 18 9 9 0 000-18zm1 13h-2v-2h2v2zm0-4h-2V7h2v5z"/></svg>',
    },
    {
      label: '看板',
      path: PageEnum.MOBILE_BOARD,
      icon: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z"/></svg>',
    },
    {
      label: '我的',
      path: PageEnum.MOBILE_MINE,
      icon: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 12a4 4 0 100-8 4 4 0 000 8zm0 2c-4.4 0-8 2.2-8 5v1h16v-1c0-2.8-3.6-5-8-5z"/></svg>',
    },
  ];

  function isActive(path: string) {
    return route.path === path || route.path.startsWith(path + '/');
  }

  function go(path: string) {
    router.push(path);
  }
</script>

<style lang="less" scoped>
  .m-shell {
    min-height: 100dvh;
    padding-bottom: calc(58px + env(safe-area-inset-bottom));
  }
  .m-tabbar {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 100;
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    height: calc(58px + env(safe-area-inset-bottom));
    padding-bottom: env(safe-area-inset-bottom);
    background: rgba(247, 252, 251, 0.92);
    border-top: 1px solid var(--line);
    backdrop-filter: blur(16px);
  }
  .tab-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 2px;
    border: 0;
    background: transparent;
    color: var(--muted);
    font-size: 11px;
    .tab-ico {
      width: 22px;
      height: 22px;
      display: inline-flex;
      :deep(svg) {
        width: 22px;
        height: 22px;
      }
    }
    &.active {
      color: var(--teal);
      font-weight: 700;
    }
  }
  @media (min-width: 768px) {
    .m-shell,
    .m-tabbar {
      max-width: 430px;
      margin: 0 auto;
    }
    .m-tabbar {
      left: 50%;
      right: auto;
      transform: translateX(-50%);
      width: 100%;
    }
  }
</style>
