<!--
 * Sentiment 品牌 Logo：与前台 home-nav brand-mark 一致
-->
<template>
  <div class="anticon" :class="getAppLogoClass" @click="goHome">
    <span class="sentiment-brand-mark" aria-hidden="true"><i /><i /><i /></span>
    <div class="ml-2 truncate md:opacity-100" :class="getTitleClass" v-show="showTitle">
      {{ brandTitle }}
    </div>
  </div>
</template>
<script lang="ts" setup>
  import { computed, unref } from 'vue';
  import { useGo } from '/@/hooks/web/usePage';
  import { useMenuSetting } from '/@/hooks/setting/useMenuSetting';
  import { useDesign } from '/@/hooks/web/useDesign';
  import { PageEnum } from '/@/enums/pageEnum';

  const props = defineProps({
    /**
     * The theme of the current parent component
     */
    theme: { type: String, validator: (v: string) => ['light', 'dark'].includes(v) },
    /**
     * Whether to show title
     */
    showTitle: { type: Boolean, default: true },
    /**
     * The title is also displayed when the menu is collapsed
     */
    alwaysShowTitle: { type: Boolean },
  });

  const { prefixCls } = useDesign('app-logo');
  const { getCollapsedShowTitle } = useMenuSetting();
  const go = useGo();
  const brandTitle = 'Sentiment';

  const getAppLogoClass = computed(() => [prefixCls, props.theme, { 'collapsed-show-title': unref(getCollapsedShowTitle) }]);

  const getTitleClass = computed(() => [
    `${prefixCls}__title`,
    {
      'xs:opacity-0': !props.alwaysShowTitle,
    },
  ]);

  function goHome() {
    // 前后台同一 SPA / 同一 TOKEN__：点 Logo 回前台首页
    go(PageEnum.BASE_HOME);
  }
</script>
<style lang="less" scoped>
  @prefix-cls: ~'@{namespace}-app-logo';

  .@{prefix-cls} {
    display: flex;
    align-items: center;
    padding-left: 7px;
    cursor: pointer;
    transition: all 0.2s ease;

    &.jeecg-layout-mix-sider-logo,
    &.jeecg-layout-menu-logo {
      background: transparent;
    }

    &.collapsed-show-title {
      padding-left: 20px;
    }

    &.light &__title {
      color: #214d58;
    }

    &.dark &__title {
      color: @white;
    }

    &__title {
      font-size: 20px;
      font-weight: 600;
      letter-spacing: -0.06em;
      transition: all 0.5s;
      line-height: normal;
    }

    .sentiment-brand-mark {
      position: relative;
      display: inline-block;
      flex-shrink: 0;
      width: 31px;
      height: 31px;
      border-radius: 12px 12px 12px 3px;
      background: linear-gradient(135deg, #1aa2a3, #82d9c2);
      box-shadow: 0 7px 18px rgba(25, 149, 144, 0.18);

      i {
        position: absolute;
        display: block;
        border: 2px solid #f1fffb;
        border-radius: 2px;
      }

      i:nth-child(1) {
        top: 7px;
        left: 6px;
        width: 11px;
        height: 9px;
        border-right: 0;
      }

      i:nth-child(2) {
        top: 11px;
        left: 13px;
        width: 12px;
        height: 8px;
        border-left: 0;
        border-bottom: 0;
        transform: skewX(-25deg);
      }

      i:nth-child(3) {
        right: 4px;
        bottom: 7px;
        width: 11px;
        height: 6px;
        border-left: 0;
        border-top: 0;
      }
    }
  }
</style>
