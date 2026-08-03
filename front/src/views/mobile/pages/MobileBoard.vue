<template>
  <div class="board-m m-theme">
    <header class="head">
      <span class="kicker">MOBILE BOARD</span>
      <h1>看板</h1>
      <p>与桌面端同源：概览指标与热门标签</p>
    </header>

    <section class="stats">
      <article v-for="s in cards" :key="s.label">
        <span>{{ s.label }}</span>
        <strong>{{ s.value }}</strong>
      </article>
    </section>

    <section class="panel">
      <div class="panel-h">
        <h2>热门标签</h2>
        <button type="button" @click="load">刷新</button>
      </div>
      <p v-if="loading" class="muted">加载中…</p>
      <p v-else-if="!tags.length" class="muted">暂无标签数据</p>
      <ul v-else>
        <li v-for="(t, i) in tags" :key="t.name">
          <span class="rank">{{ i + 1 }}</span>
          <div>
            <strong>{{ t.name }}</strong>
            <small>{{ t.count }} 次</small>
          </div>
        </li>
      </ul>
    </section>
  </div>
</template>

<script lang="ts" name="MobileBoard" setup>
  import { computed, onMounted, ref } from 'vue';
  import { fetchOverview, fetchTagTop, type OverviewSummary, type TagTopItem } from '../mobile.api';
  import '../mobile-theme.less';

  const loading = ref(false);
  const summary = ref<OverviewSummary | null>(null);
  const tags = ref<TagTopItem[]>([]);

  const cards = computed(() => {
    const s = summary.value;
    if (!s) {
      return [
        { label: '评价', value: '—' },
        { label: '正向', value: '—' },
        { label: '正向率', value: '—' },
        { label: '负向', value: '—' },
      ];
    }
    const rate = Number(s.positiveRate || 0);
    const rateText = rate <= 1 ? `${(rate * 100).toFixed(0)}%` : `${rate}%`;
    return [
      { label: '评价', value: String(s.total ?? 0) },
      { label: '正向', value: String(s.positive ?? 0) },
      { label: '正向率', value: rateText },
      { label: '负向', value: String(s.negative ?? 0) },
    ];
  });

  async function load() {
    loading.value = true;
    try {
      const [ov, top] = await Promise.all([fetchOverview(), fetchTagTop(12)]);
      summary.value = ov?.summary ?? null;
      tags.value = top?.items ?? ov?.tagTop?.items ?? [];
    } catch {
      summary.value = null;
      tags.value = [];
    } finally {
      loading.value = false;
    }
  }

  onMounted(() => {
    document.title = '看板 · Sentiment';
    load();
  });
</script>

<style lang="less" scoped>
  .board-m {
    padding: 14px 14px 24px;
  }
  .head {
    .kicker {
      font-size: 10px;
      letter-spacing: 0.12em;
      color: var(--muted);
    }
    h1 {
      margin: 4px 0 0;
      font-size: 24px;
      letter-spacing: -0.04em;
    }
    p {
      margin: 6px 0 0;
      color: var(--muted);
      font-size: 13px;
    }
  }
  .stats {
    margin-top: 14px;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    article {
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px;
      span {
        display: block;
        font-size: 12px;
        color: var(--muted);
      }
      strong {
        display: block;
        margin-top: 6px;
        font-size: 22px;
        letter-spacing: -0.03em;
        color: var(--teal);
      }
    }
  }
  .panel {
    margin-top: 14px;
    background: #fff;
    border: 1px solid var(--line);
    border-radius: 16px;
    padding: 12px;
  }
  .panel-h {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
    h2 {
      margin: 0;
      font-size: 16px;
    }
    button {
      border: 0;
      background: var(--teal-soft);
      color: var(--teal);
      border-radius: 12px;
      padding: 6px 10px;
      font-size: 12px;
    }
  }
  .muted {
    color: var(--muted);
    font-size: 13px;
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  li {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 0;
    border-top: 1px solid var(--line);
    &:first-child {
      border-top: 0;
    }
    .rank {
      width: 22px;
      height: 22px;
      border-radius: 8px;
      background: var(--teal-soft);
      color: var(--teal);
      display: grid;
      place-items: center;
      font-size: 11px;
      font-weight: 700;
    }
    div {
      flex: 1;
      min-width: 0;
      strong {
        display: block;
        font-size: 14px;
      }
      small {
        color: var(--muted);
        font-size: 11px;
      }
    }
  }
</style>
