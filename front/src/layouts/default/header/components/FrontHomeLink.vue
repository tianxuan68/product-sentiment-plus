<template>
  <button class="sentiment-front-link nav-cta" type="button" title="返回前台首页" @click="goFront">
    返回前台 <span>↖</span>
  </button>
</template>

<script lang="ts" setup>
  import { useRouter } from 'vue-router';
  import { PageEnum } from '/@/enums/pageEnum';

  const router = useRouter();

  function goFront() {
    router.push(PageEnum.BASE_HOME);
  }
</script>

<style lang="less" scoped>
  /* 与 Welcome.home-nav .nav-cta 同规格，避免继承顶栏 72px 行高 */
  .sentiment-front-link.nav-cta {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    box-sizing: border-box;
    height: 40px;
    min-height: 40px;
    max-height: 40px;
    margin: 0 8px 0 0;
    padding: 0 17px;
    border: 0;
    border-radius: 14px;
    color: #f5fffc;
    background: #167f87;
    box-shadow: 0 10px 22px rgba(22, 127, 135, 0.17);
    font-size: 13px;
    font-weight: 700;
    line-height: 1;
    cursor: pointer;
    transition: transform 0.2s, box-shadow 0.2s;

    span {
      font-weight: 500;
      line-height: 1;
    }

    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 12px 24px rgba(22, 127, 135, 0.22);
    }
  }
</style>
