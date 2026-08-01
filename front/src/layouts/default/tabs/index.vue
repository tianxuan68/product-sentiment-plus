<template>
  <div :class="getWrapClass">
    <Tabs
      type="editable-card"
      size="small"
      :animated="false"
      :hideAdd="true"
      :tabBarGutter="3"
      :activeKey="activeKeyRef"
      @change="handleChange"
      @edit="handleEdit"
    >
      <template v-for="item in getTabsState" :key="item.query ? item.fullPath : item.path">
        <TabPane :closable="!(item && item.meta && item.meta.affix)">
          <template #tab>
            <TabContent :tabItem="item" />
          </template>
        </TabPane>
      </template>

      <template #rightExtra v-if="getShowRedo || getShowQuick">
        <div class="rightExtra">
          <TabRedo v-if="getShowRedo" />
          <!-- <TabContent isExtra :tabItem="$route" v-if="getShowQuick" /> -->
          <!-- 列表页全屏 
          <FoldButton v-if="getShowFold" />-->
          <!-- <FullscreenOutlined /> -->
        </div>
      </template>
    </Tabs>
  </div>
</template>
<script lang="ts">
  import type { RouteLocationNormalized, RouteMeta } from 'vue-router';

  import { defineComponent, computed, unref, ref } from 'vue';

  import { Tabs } from 'ant-design-vue';
  import TabContent from './components/TabContent.vue';
  import FoldButton from './components/FoldButton.vue';
  import TabRedo from './components/TabRedo.vue';

  import { useGo } from '/@/hooks/web/usePage';

  import { useMultipleTabStore } from '/@/store/modules/multipleTab';
  import { useUserStore } from '/@/store/modules/user';

  import { initAffixTabs, useTabsDrag } from './useMultipleTabs';
  import { useDesign } from '/@/hooks/web/useDesign';
  import { useMultipleTabSetting } from '/@/hooks/setting/useMultipleTabSetting';

  import { TabsThemeEnum } from '/@/enums/appEnum';
  import { REDIRECT_NAME } from '/@/router/constant';
  import { listenerRouteChange } from '/@/logics/mitt/routeChange';

  import { useRouter } from 'vue-router';

  export default defineComponent({
    name: 'MultipleTabs',
    components: {
      TabRedo,
      FoldButton,
      Tabs,
      TabPane: Tabs.TabPane,
      TabContent,
    },
    setup() {
      const affixTextList = initAffixTabs();
      const activeKeyRef = ref('');

      useTabsDrag(affixTextList);
      const tabStore = useMultipleTabStore();
      const userStore = useUserStore();
      const router = useRouter();

      const { prefixCls } = useDesign('multiple-tabs');
      const go = useGo();
      const { getShowQuick, getShowRedo, getShowFold, getTabsTheme } = useMultipleTabSetting();

      const getTabsState = computed(() => {
        return tabStore.getTabList.filter((item) => !item.meta?.hideTab);
      });

      const unClose = computed(() => unref(getTabsState).length === 1);

      // 极简模式隐藏标签栏AI入口图标
      const getIsSimpleTheme = computed(() => unref(getTabsTheme) === TabsThemeEnum.SIMPLE);

      const getWrapClass = computed(() => {
        return [
          prefixCls,
          {
            [`${prefixCls}--hide-close`]: unref(unClose),
          },
          `${prefixCls}--theme-${unref(getTabsTheme)}`,
        ];
      });

      listenerRouteChange((route) => {
        const { name } = route;
        if (name === REDIRECT_NAME || !route || !userStore.getToken) {
          return;
        }

        const { path, fullPath, meta = {} } = route;
        const { currentActiveMenu, hideTab } = meta as RouteMeta;
        const isHide = !hideTab ? null : currentActiveMenu;
        const p = isHide || fullPath || path;
        if (activeKeyRef.value !== p) {
          activeKeyRef.value = p as string;
        }

        if (isHide) {
          const findParentRoute = router.getRoutes().find((item) => item.path === currentActiveMenu);

          findParentRoute && tabStore.addTab(findParentRoute as unknown as RouteLocationNormalized);
        } else {
          tabStore.addTab(unref(route));
        }
      });

      function handleChange(activeKey: any) {
        activeKeyRef.value = activeKey;
        go(activeKey, false);
      }

      // Close the current tab
      function handleEdit(targetKey: string) {
        // Added operation to hide, currently only use delete operation
        if (unref(unClose)) {
          return;
        }

        tabStore.closeTabByKey(targetKey, router);
      }
      return {
        prefixCls,
        unClose,
        getWrapClass,
        handleEdit,
        handleChange,
        activeKeyRef,
        getTabsState,
        getShowQuick,
        getShowRedo,
        getShowFold,
        getIsSimpleTheme,
      };
    },
  });
</script>
<style lang="less">
  @import './index.less';
  @import './tabs.theme.card.less';
  @import './tabs.theme.smooth.less';
  @import './tabs.theme.simple.less';
</style>
<style lang="less" scoped>
@prefix-cls: ~'@{namespace}-multiple-tabs';
.@{prefix-cls} {
  :deep(.anticon) {
    display: inline-block;
  }
  // 代码逻辑说明: 【issues/7345】标签样式切换到极简模式样式错乱
  .rightExtra {
    display: flex;
    :deep(svg) {
      &:not(.icon) {
        vertical-align: -0.3em;
      }
    }
    .ai-icon {
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      width: 36px;
      color: @text-color;
      text-align: center;
      border-left: 1px solid @border-color-base;
    }
  }
}
</style>
