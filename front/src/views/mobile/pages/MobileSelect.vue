<template>
  <div class="pdd-page m-theme">
    <header class="pdd-search">
      <button type="button" class="brand" @click="router.push(PageEnum.BASE_HOME)">
        <span class="mark"><i /><i /><i /></span>
      </button>
      <div class="search-box">
        <span class="scope">评论</span>
        <input v-model="keyword" type="search" placeholder="搜索评价内容 / 商品" @keyup.enter="applySearch" />
        <button v-if="keyword" type="button" class="clear" @click="keyword = ''; applySearch()">×</button>
      </div>
      <button type="button" class="search-btn" @click="applySearch">搜索</button>
    </header>

    <div class="sort-bar">
      <button type="button" :class="{ on: sortKey === 'default' }" @click="setSort('default')">综合</button>
      <button type="button" :class="{ on: sortKey === 'latest' }" @click="setSort('latest')">最新</button>
      <button type="button" class="price-btn" :class="{ on: sortKey.startsWith('score') }" @click="toggleScore">
        评分
        <i class="arrows"><b :class="{ hi: sortKey === 'scoreAsc' }" /><b :class="{ hi: sortKey === 'scoreDesc' }" /></i>
      </button>
      <button type="button" :class="{ on: !!sentimentFilter || showSentiment }" @click="showSentiment = true">
        {{ sentimentLabel || '情绪' }} ▾
      </button>
      <button type="button" :class="{ on: filterOn }" @click="showFilter = true">筛选</button>
    </div>

    <div class="tag-row">
      <button type="button" class="tag" :class="{ on: !activeTag }" @click="pickTag('')">全部</button>
      <button v-for="t in tagList" :key="t" type="button" class="tag" :class="{ on: activeTag === t }" @click="pickTag(t)">
        {{ t }}
      </button>
    </div>

    <div class="body">
      <aside class="cat-rail">
        <button type="button" :class="{ on: !categoryId }" @click="pickCategory('')">全部</button>
        <button
          v-for="c in flatCategories"
          :key="c.id"
          type="button"
          :class="{ on: categoryId === c.id }"
          @click="pickCategory(c.id)"
        >
          {{ c.name }}
        </button>
      </aside>

      <section ref="feedRef" class="feed" @scroll="onScroll">
        <div class="feed-banner">
          <span>{{ feedHint }}</span>
          <em>真实评价</em>
        </div>

        <article v-for="item in reviews" :key="item.id" class="card" @click="openDetail(item)">
          <div class="thumb" :style="thumbStyle(item)">
            <img v-if="item.coverUrl" :src="item.coverUrl" :alt="item.productName || '评价图'" />
            <span v-else class="thumb-fallback">{{ fallbackChar(item) }}</span>
          </div>
          <div class="meta">
            <div class="badges">
              <span class="b-sent" :class="'tone-' + (item.sentiment || 'neutral')">
                {{ item.sentiment_dictText || sentimentText(item.sentiment) }}
              </span>
              <span v-if="item.productName" class="b-name">{{ item.productName }}</span>
              <span v-if="item.categoryName" class="b-flag">{{ item.categoryName }}</span>
            </div>
            <h3 class="title">{{ item.content }}</h3>
            <p class="svc">
              <template v-if="item.keywordsText">{{ item.keywordsText }}</template>
              <template v-else>{{ item.summary || '来自评论数据集' }}</template>
            </p>
            <div class="price-bar">
              <span class="price"><small>置信</small> {{ formatScore(item.score) }}</span>
              <span class="hot">{{ formatTime(item.createTime) }}</span>
            </div>
          </div>
        </article>

        <div v-if="loading" class="state">加载中…</div>
        <div v-else-if="!reviews.length" class="state">暂无评价，试试换个类目或关键词</div>
        <div v-else-if="!hasMore" class="state">已经到底了</div>
      </section>
    </div>

    <div v-if="showSentiment" class="mask" @click.self="showSentiment = false">
      <div class="drawer">
        <h4>情绪筛选</h4>
        <button type="button" class="opt" :class="{ on: !sentimentFilter }" @click="pickSentiment('')">全部情绪</button>
        <button
          v-for="s in sentimentOptions"
          :key="s.value"
          type="button"
          class="opt"
          :class="{ on: sentimentFilter === s.value }"
          @click="pickSentiment(s.value)"
        >
          {{ s.label }}
        </button>
      </div>
    </div>

    <div v-if="showFilter" class="mask" @click.self="showFilter = false">
      <div class="drawer">
        <h4>筛选评论</h4>
        <p class="section-label">配图</p>
        <div class="chips">
          <button type="button" :class="{ on: hasImage === null }" @click="hasImage = null">全部</button>
          <button type="button" :class="{ on: hasImage === true }" @click="hasImage = true">有图</button>
          <button type="button" :class="{ on: hasImage === false }" @click="hasImage = false">无图</button>
        </div>
        <p class="section-label">评分区间</p>
        <div class="price-range">
          <input v-model.number="scoreMin" type="number" min="0" max="100" placeholder="最低" />
          <span>—</span>
          <input v-model.number="scoreMax" type="number" min="0" max="100" placeholder="最高" />
        </div>
        <div class="drawer-actions">
          <button type="button" class="ghost" @click="resetFilter">重置</button>
          <button type="button" class="ok" @click="applyFilter">完成</button>
        </div>
      </div>
    </div>

    <div v-if="detail" class="mask" @click.self="detail = null">
      <div class="detail-sheet">
        <button type="button" class="sheet-close" @click="detail = null">×</button>
        <div class="detail-thumb" :style="thumbStyle(detail)">
          <img v-if="detail.coverUrl" :src="detail.coverUrl" :alt="detail.productName || '评价图'" />
        </div>
        <div class="badges detail-badges">
          <span class="b-sent" :class="'tone-' + (detail.sentiment || 'neutral')">
            {{ detail.sentiment_dictText || sentimentText(detail.sentiment) }}
          </span>
          <span v-if="detail.categoryName" class="b-flag">{{ detail.categoryName }}</span>
        </div>
        <h3>{{ detail.productName || '未关联商品' }}</h3>
        <p class="detail-sub">{{ detail.username || '匿名' }} · {{ formatTime(detail.createTime) }}</p>
        <p class="detail-price">置信分 {{ formatScore(detail.score) }}</p>
        <p class="detail-desc">{{ detail.content }}</p>
        <p v-if="detail.keywordsText" class="detail-stats">标签：{{ detail.keywordsText }}</p>
        <p v-if="detail.summary" class="detail-stats">摘要：{{ detail.summary }}</p>
        <div class="detail-actions">
          <button type="button" class="ghost" @click="goInsight(detail)">情绪洞察</button>
          <button type="button" class="primary" @click="goAdminReview">评价管理</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts" name="MobileSelect" setup>
  import { computed, onMounted, ref } from 'vue';
  import { useRouter } from 'vue-router';
  import { PageEnum } from '/@/enums/pageEnum';
  import { fetchCategoryTree, fetchKeywords, fetchReviewList } from '../mobile.api';
  import '../mobile-theme.less';

  const router = useRouter();
  const keyword = ref('');
  const sortKey = ref<'default' | 'latest' | 'scoreAsc' | 'scoreDesc'>('default');
  const showSentiment = ref(false);
  const showFilter = ref(false);
  const sentimentFilter = ref('');
  const activeTag = ref('');
  const categoryId = ref('');
  const hasImage = ref<boolean | null>(null);
  const scoreMin = ref<number | null>(null);
  const scoreMax = ref<number | null>(null);
  const loading = ref(false);
  const pageNo = ref(1);
  const hasMore = ref(true);
  const reviews = ref<Recordable[]>([]);
  const tagList = ref<string[]>([]);
  const flatCategories = ref<{ id: string; name: string }[]>([]);
  const detail = ref<Recordable | null>(null);
  const feedRef = ref<HTMLElement | null>(null);

  const sentimentOptions = [
    { value: 'positive', label: '正向' },
    { value: 'neutral', label: '中性' },
    { value: 'negative', label: '负向' },
  ];

  const sentimentLabel = computed(() => sentimentOptions.find((s) => s.value === sentimentFilter.value)?.label || '');

  const filterOn = computed(
    () =>
      hasImage.value !== null ||
      scoreMin.value != null ||
      scoreMax.value != null ||
      !!sentimentFilter.value ||
      !!activeTag.value,
  );

  const feedHint = computed(() => {
    const cat = flatCategories.value.find((c) => c.id === categoryId.value);
    if (cat) return `「${cat.name}」评价`;
    if (sentimentLabel.value) return `「${sentimentLabel.value}」评价`;
    if (activeTag.value) return `标签「${activeTag.value}」`;
    return '评论优先展示';
  });

  function sentimentText(s?: string) {
    if (s === 'positive') return '正向';
    if (s === 'negative') return '负向';
    return '中性';
  }
  function formatScore(v: unknown) {
    const n = Number(v);
    if (!Number.isFinite(n)) return '--';
    return `${Math.round(n)}`;
  }
  function formatTime(v: unknown) {
    const s = String(v || '');
    if (!s) return '';
    return s.slice(0, 10);
  }
  function fallbackChar(item: Recordable) {
    return String(item.productName || item.content || '?').slice(0, 1);
  }
  function thumbStyle(item: Recordable) {
    const hues = [168, 175, 190, 155, 200];
    const h = hues[(String(item.id || item.content).length || 0) % hues.length];
    return { background: `linear-gradient(145deg, hsl(${h} 45% 92%), hsl(${h} 35% 78%))` };
  }

  function sortParams() {
    if (sortKey.value === 'latest') return { column: 'createTime', order: 'desc' };
    if (sortKey.value === 'scoreAsc') return { column: 'score', order: 'asc' };
    if (sortKey.value === 'scoreDesc') return { column: 'score', order: 'desc' };
    return { column: 'createTime', order: 'desc' };
  }

  function setSort(key: typeof sortKey.value) {
    sortKey.value = key;
    reload(true);
  }
  function toggleScore() {
    sortKey.value = sortKey.value === 'scoreAsc' ? 'scoreDesc' : 'scoreAsc';
    reload(true);
  }
  function pickSentiment(v: string) {
    sentimentFilter.value = v;
    showSentiment.value = false;
    reload(true);
  }
  function pickTag(t: string) {
    activeTag.value = t;
    reload(true);
  }
  function pickCategory(id: string) {
    categoryId.value = id;
    reload(true);
  }
  function applySearch() {
    reload(true);
  }
  function resetFilter() {
    hasImage.value = null;
    scoreMin.value = null;
    scoreMax.value = null;
  }
  function applyFilter() {
    showFilter.value = false;
    reload(true);
  }
  function openDetail(item: Recordable) {
    detail.value = item;
  }
  function goInsight(item: Recordable) {
    detail.value = null;
    router.push({
      path: PageEnum.MOBILE_INSIGHT,
      query: {
        productName: item.productName || '',
        category: item.categoryName || '',
        content: item.content || '',
      },
    });
  }
  function goAdminReview() {
    detail.value = null;
    router.push('/sentiment/review');
  }

  function walkCategories(nodes: any[], out: { id: string; name: string }[]) {
    (nodes || []).forEach((n) => {
      if (n?.id && n?.name) out.push({ id: n.id, name: n.name });
      if (n?.children?.length) walkCategories(n.children, out);
    });
  }

  async function loadMeta() {
    try {
      const tree = await fetchCategoryTree();
      const cats: { id: string; name: string }[] = [];
      walkCategories(Array.isArray(tree) ? tree : [], cats);
      flatCategories.value = cats;
    } catch {
      flatCategories.value = [];
    }
    try {
      const kw = await fetchKeywords({ pageNo: 1, pageSize: 30 });
      const records = kw?.records || [];
      tagList.value = records.map((r: any) => String(r.word || '').trim()).filter(Boolean).slice(0, 16);
    } catch {
      tagList.value = ['物流', '发货', '包装', '客服', '质量', '性价比'];
    }
  }

  async function reload(reset = false) {
    if (loading.value) return;
    if (reset) {
      pageNo.value = 1;
      hasMore.value = true;
      reviews.value = [];
      if (feedRef.value) feedRef.value.scrollTop = 0;
    }
    if (!hasMore.value && !reset) return;
    loading.value = true;
    try {
      const sort = sortParams();
      const params: Recordable = {
        pageNo: pageNo.value,
        pageSize: 20,
        keyword: keyword.value || undefined,
        categoryId: categoryId.value || undefined,
        sentiment: sentimentFilter.value || undefined,
        tag: activeTag.value || undefined,
        ...sort,
      };
      if (hasImage.value === true) params.hasImage = true;
      if (hasImage.value === false) params.hasImage = false;
      if (scoreMin.value != null && Number.isFinite(scoreMin.value)) params.scoreMin = scoreMin.value;
      if (scoreMax.value != null && Number.isFinite(scoreMax.value)) params.scoreMax = scoreMax.value;
      const res = await fetchReviewList(params);
      const records = res?.records || [];
      reviews.value = reset ? records : reviews.value.concat(records);
      const total = Number(res?.total || 0);
      hasMore.value = reviews.value.length < total;
      if (records.length) pageNo.value += 1;
      else hasMore.value = false;
    } catch {
      if (reset) reviews.value = [];
      hasMore.value = false;
    } finally {
      loading.value = false;
    }
  }

  function onScroll() {
    const el = feedRef.value;
    if (!el || loading.value || !hasMore.value) return;
    if (el.scrollTop + el.clientHeight >= el.scrollHeight - 80) reload(false);
  }

  onMounted(async () => {
    document.title = '评论 · Sentiment';
    await loadMeta();
    await reload(true);
  });
</script>

<style lang="less" scoped>
  .pdd-page {
    height: calc(100dvh - 58px - env(safe-area-inset-bottom));
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .pdd-search {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 12px 8px;
    .brand {
      border: 0;
      background: transparent;
      padding: 0;
    }
    .mark {
      position: relative;
      display: inline-block;
      width: 30px;
      height: 30px;
      border-radius: 12px 12px 12px 3px;
      background: linear-gradient(135deg, #1aa2a3, #82d9c2);
      i {
        position: absolute;
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
    .search-box {
      flex: 1;
      display: flex;
      align-items: center;
      height: 36px;
      padding: 0 12px;
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.9);
      border: 1px solid var(--line);
      .scope {
        font-size: 12px;
        color: var(--muted);
        margin-right: 8px;
        padding-right: 8px;
        border-right: 1px solid var(--line);
      }
      input {
        flex: 1;
        border: 0;
        background: transparent;
        outline: none;
        font-size: 14px;
        color: var(--ink);
      }
      .clear {
        border: 0;
        width: 18px;
        height: 18px;
        border-radius: 50%;
        background: #c5d5d6;
        color: #fff;
      }
    }
    .search-btn {
      border: 0;
      background: transparent;
      color: var(--teal);
      font-weight: 700;
      font-size: 14px;
    }
  }
  .sort-bar {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    background: rgba(255, 255, 255, 0.72);
    border-bottom: 1px solid var(--line);
    button {
      height: 40px;
      border: 0;
      background: transparent;
      font-size: 13px;
      color: var(--muted);
      &.on {
        color: var(--teal);
        font-weight: 700;
      }
    }
    .price-btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 2px;
      .arrows {
        display: inline-flex;
        flex-direction: column;
        gap: 1px;
        b {
          width: 0;
          height: 0;
          border-left: 3px solid transparent;
          border-right: 3px solid transparent;
          border-bottom: 4px solid #b7c9cb;
          &:last-child {
            border-bottom: 0;
            border-top: 4px solid #b7c9cb;
          }
          &.hi {
            border-bottom-color: var(--teal);
            border-top-color: var(--teal);
          }
        }
      }
    }
  }
  .tag-row {
    display: flex;
    gap: 8px;
    padding: 8px 10px;
    overflow-x: auto;
    scrollbar-width: none;
    &::-webkit-scrollbar {
      display: none;
    }
    .tag {
      flex-shrink: 0;
      height: 28px;
      padding: 0 12px;
      border-radius: 14px;
      background: #fff;
      border: 1px solid var(--line);
      font-size: 12px;
      color: var(--ink);
      &.on {
        background: var(--teal-soft);
        color: var(--teal);
        border-color: transparent;
        font-weight: 700;
      }
    }
  }
  .body {
    flex: 1;
    min-height: 0;
    display: flex;
  }
  .cat-rail {
    width: 78px;
    overflow-y: auto;
    background: rgba(237, 247, 246, 0.9);
    button {
      display: block;
      width: 100%;
      padding: 14px 6px;
      border: 0;
      background: transparent;
      font-size: 12px;
      color: var(--muted);
      text-align: center;
      line-height: 1.3;
      &.on {
        background: #fff;
        color: var(--teal);
        font-weight: 700;
        position: relative;
        &::before {
          content: '';
          position: absolute;
          left: 0;
          top: 12px;
          bottom: 12px;
          width: 3px;
          border-radius: 0 2px 2px 0;
          background: var(--teal);
        }
      }
    }
  }
  .feed {
    flex: 1;
    overflow-y: auto;
    background: rgba(255, 255, 255, 0.55);
  }
  .feed-banner {
    display: flex;
    justify-content: space-between;
    margin: 8px;
    padding: 8px 12px;
    border-radius: 10px;
    background: linear-gradient(90deg, #1aa2a3, #167f87);
    color: #f5fffc;
    font-size: 12px;
    em {
      font-style: normal;
      opacity: 0.9;
    }
  }
  .card {
    display: flex;
    gap: 10px;
    padding: 12px 10px;
    border-bottom: 1px solid var(--line);
  }
  .thumb {
    width: 108px;
    height: 108px;
    border-radius: 12px;
    overflow: hidden;
    position: relative;
    flex-shrink: 0;
    img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
    .thumb-fallback {
      position: absolute;
      inset: 0;
      display: grid;
      place-items: center;
      font-size: 34px;
      font-weight: 700;
      color: rgba(33, 77, 88, 0.28);
    }
  }
  .meta {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
  }
  .badges {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-bottom: 4px;
    span {
      font-size: 10px;
      line-height: 16px;
      padding: 0 5px;
      border-radius: 4px;
    }
    .b-sent {
      color: #fff;
      &.tone-positive {
        background: var(--good);
      }
      &.tone-negative {
        background: var(--danger);
      }
      &.tone-neutral {
        background: var(--muted);
      }
    }
    .b-name,
    .b-flag {
      background: var(--teal-soft);
      color: var(--teal);
    }
  }
  .title {
    margin: 0;
    font-size: 14px;
    font-weight: 650;
    line-height: 1.35;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .svc {
    margin: 4px 0 0;
    font-size: 11px;
    color: var(--muted);
    display: -webkit-box;
    -webkit-line-clamp: 1;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .price-bar {
    margin-top: auto;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 5px 10px;
    border-radius: 8px;
    background: linear-gradient(90deg, #214d58, #167f87);
    color: #fff;
    .price {
      font-size: 15px;
      font-weight: 700;
      color: #d9f7f5;
      small {
        font-size: 10px;
        font-weight: 400;
        margin-right: 2px;
      }
    }
    .hot {
      font-size: 11px;
      opacity: 0.9;
    }
  }
  .state {
    padding: 20px;
    text-align: center;
    color: var(--muted);
    font-size: 13px;
  }
  .mask {
    position: fixed;
    inset: 0;
    z-index: 200;
    background: rgba(33, 77, 88, 0.35);
    display: flex;
    align-items: flex-end;
  }
  .drawer,
  .detail-sheet {
    width: 100%;
    max-height: 75dvh;
    overflow-y: auto;
    background: #fff;
    border-radius: 18px 18px 0 0;
    padding: 16px 16px calc(20px + env(safe-area-inset-bottom));
  }
  .drawer {
    h4 {
      margin: 0 0 12px;
      font-size: 16px;
    }
    .section-label {
      margin: 12px 0 8px;
      color: var(--muted);
      font-size: 13px;
    }
    .opt {
      display: block;
      width: 100%;
      text-align: left;
      padding: 12px 0;
      border: 0;
      border-bottom: 1px solid #f0f5f5;
      background: transparent;
      &.on {
        color: var(--teal);
        font-weight: 700;
      }
    }
    .chips {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      button {
        height: 30px;
        padding: 0 12px;
        border: 0;
        border-radius: 15px;
        background: #edf4f2;
        &.on {
          background: var(--teal-soft);
          color: var(--teal);
          font-weight: 700;
        }
      }
    }
    .price-range {
      display: flex;
      align-items: center;
      gap: 8px;
      input {
        flex: 1;
        height: 36px;
        border: 1px solid var(--line);
        border-radius: 10px;
        padding: 0 10px;
      }
    }
    .drawer-actions {
      display: grid;
      grid-template-columns: 1fr 1.4fr;
      gap: 10px;
      margin-top: 16px;
      .ghost,
      .ok {
        height: 42px;
        border: 0;
        border-radius: 21px;
      }
      .ghost {
        background: #edf4f2;
      }
      .ok {
        background: var(--teal);
        color: #fff;
      }
    }
  }
  .detail-sheet {
    position: relative;
    .sheet-close {
      position: absolute;
      right: 12px;
      top: 10px;
      border: 0;
      background: transparent;
      font-size: 28px;
      color: var(--muted);
    }
    .detail-thumb {
      height: 180px;
      border-radius: 14px;
      overflow: hidden;
      margin-bottom: 12px;
      img {
        width: 100%;
        height: 100%;
        object-fit: cover;
      }
    }
    .detail-badges {
      margin-bottom: 8px;
    }
    h3 {
      margin: 0;
      font-size: 17px;
    }
    .detail-sub,
    .detail-stats {
      margin: 6px 0;
      color: var(--muted);
      font-size: 13px;
    }
    .detail-price {
      margin: 0;
      color: var(--teal);
      font-size: 22px;
      font-weight: 700;
    }
    .detail-desc {
      margin: 10px 0 16px;
      color: #5a7a7e;
      font-size: 13px;
      line-height: 1.5;
    }
    .detail-actions {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      button {
        height: 42px;
        border: 0;
        border-radius: 21px;
        font-size: 15px;
      }
      .ghost {
        background: var(--teal-soft);
        color: var(--teal);
      }
      .primary {
        background: var(--teal);
        color: #fff;
      }
    }
  }
</style>
