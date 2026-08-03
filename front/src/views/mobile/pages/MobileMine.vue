<template>
  <div class="mine-page m-theme">
    <header class="profile">
      <div class="avatar">{{ avatarText }}</div>
      <div>
        <h1>{{ displayName }}</h1>
        <p>Sentiment · 评论与情绪洞察</p>
      </div>
    </header>

    <section class="group">
      <h2>核心功能</h2>
      <button type="button" @click="router.push(PageEnum.MOBILE_SELECT)">评论查找</button>
      <button type="button" @click="router.push(PageEnum.MOBILE_INSIGHT)">情绪洞察</button>
      <button type="button" @click="router.push(PageEnum.MOBILE_BOARD)">手机看板</button>
      <button type="button" @click="router.push(PageEnum.BASE_ADMIN)">评价看板（后台）</button>
    </section>

    <section class="group">
      <h2>业务管理</h2>
      <button type="button" @click="router.push('/product/info')">商品管理</button>
      <button type="button" @click="router.push('/product/category')">类目管理</button>
      <button type="button" @click="router.push('/sentiment/review')">评价管理</button>
      <button type="button" @click="router.push('/sentiment/keyword')">关键词管理</button>
      <button type="button" @click="router.push('/sentiment/causal')">因果分析</button>
    </section>

    <section class="group">
      <h2>系统</h2>
      <button type="button" @click="router.push(PageEnum.BASE_HOME + '?desktop=1')">桌面版前台</button>
      <button type="button" @click="router.push('/sentiment/dashboard?desktop=1')">评价看板（后台）</button>
      <button type="button" class="danger" @click="logout">退出登录</button>
    </section>
  </div>
</template>

<script lang="ts" name="MobileMine" setup>
  import { computed, onMounted } from 'vue';
  import { useRouter } from 'vue-router';
  import { PageEnum } from '/@/enums/pageEnum';
  import { useUserStore } from '/@/store/modules/user';
  import '../mobile-theme.less';

  const router = useRouter();
  const userStore = useUserStore();

  const displayName = computed(() => userStore.getUserInfo?.realname || userStore.getUserInfo?.username || '用户');
  const avatarText = computed(() => String(displayName.value).slice(0, 1).toUpperCase());

  async function logout() {
    await userStore.logout(true);
  }

  onMounted(() => {
    document.title = '我的 · Sentiment';
  });
</script>

<style lang="less" scoped>
  .mine-page {
    min-height: calc(100dvh - 58px);
    padding: 16px 12px 28px;
  }
  .profile {
    display: flex;
    gap: 12px;
    align-items: center;
    padding: 18px 14px;
    margin-bottom: 12px;
    border-radius: 16px;
    background: linear-gradient(135deg, #214d58, #167f87);
    color: #f5fffc;
    .avatar {
      width: 52px;
      height: 52px;
      border-radius: 16px;
      background: rgba(255, 255, 255, 0.18);
      display: grid;
      place-items: center;
      font-size: 22px;
      font-weight: 700;
    }
    h1 {
      margin: 0;
      font-size: 18px;
    }
    p {
      margin: 4px 0 0;
      opacity: 0.85;
      font-size: 12px;
    }
  }
  .group {
    background: #fff;
    border: 1px solid var(--line);
    border-radius: 14px;
    padding: 8px 4px;
    margin-bottom: 10px;
    h2 {
      margin: 8px 12px;
      font-size: 13px;
      color: var(--muted);
      font-weight: 500;
    }
    button {
      display: block;
      width: 100%;
      text-align: left;
      padding: 14px 12px;
      border: 0;
      border-bottom: 1px solid #f0f5f5;
      background: transparent;
      font-size: 15px;
      color: var(--ink);
      &:last-child {
        border-bottom: 0;
      }
      &.danger {
        color: var(--danger);
      }
    }
  }
</style>
