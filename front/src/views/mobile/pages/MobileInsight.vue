<template>
  <div class="insight-m m-theme">
    <header class="head">
      <div>
        <span class="kicker">SENTIMENT COPILOT</span>
        <h1>情绪洞察</h1>
      </div>
      <button type="button" class="bind" @click="showProduct = true">
        {{ product.name ? `已绑：${product.name}` : '+ 商品' }}
      </button>
    </header>

    <div ref="threadRef" class="thread">
      <div v-if="!messages.length" class="intro">
        <p>输入用户评价，模型会返回情绪倾向与方面标签。</p>
      </div>
      <article v-for="m in messages" :key="m.id" class="row" :class="m.role">
        <div class="avatar">{{ m.role === 'user' ? '你' : 'AI' }}</div>
        <div class="bubble">
          <template v-if="m.role === 'user'">
            <p>{{ m.content }}</p>
            <small v-if="m.productName">商品：{{ m.productName }}</small>
          </template>
          <template v-else-if="m.pending">
            <p class="pending">正在分析…</p>
          </template>
          <template v-else-if="m.result">
            <div class="result-head">
              <strong :class="'tone-' + m.result.sentiment">{{ label(m.result.sentiment) }}</strong>
              <span>{{ m.result.score }}%</span>
            </div>
            <p>{{ m.result.summary }}</p>
            <div v-if="m.result.keywords?.length" class="chips">
              <span v-for="k in m.result.keywords" :key="k">{{ k }}</span>
            </div>
          </template>
          <p v-else>{{ m.content }}</p>
        </div>
      </article>
    </div>

    <form class="composer" @submit.prevent="submit">
      <input v-model="text" :disabled="loading" placeholder="问问用户的真实感受" />
      <button type="submit" :disabled="loading">{{ loading ? '…' : '↑' }}</button>
    </form>
    <p class="hint">{{ hint }}</p>

    <div v-if="showProduct" class="mask" @click.self="showProduct = false">
      <form class="sheet" @submit.prevent="saveProduct">
        <h3>补充商品信息</h3>
        <label>商品名称<input v-model="product.name" required /></label>
        <label>
          类目
          <select v-model="product.category">
            <option value="">请选择</option>
            <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
          </select>
        </label>
        <label>评价<textarea v-model="reviewDraft" rows="3" required placeholder="用户评价原文" /></label>
        <button type="submit" class="ok">保存并分析</button>
      </form>
    </div>
  </div>
</template>

<script lang="ts" name="MobileInsight" setup>
  import { nextTick, onMounted, ref } from 'vue';
  import { useRoute } from 'vue-router';
  import { predictSentiment, type ProductDraft, type SentimentPredictResult } from '/@/api/sentiment';
  import '../mobile-theme.less';

  type Msg = {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    productName?: string;
    pending?: boolean;
    result?: SentimentPredictResult;
  };

  const route = useRoute();
  const text = ref('');
  const loading = ref(false);
  const hint = ref('结果由后端与 AI 模型接口返回');
  const messages = ref<Msg[]>([]);
  const threadRef = ref<HTMLElement | null>(null);
  const showProduct = ref(false);
  const reviewDraft = ref('');
  const product = ref<ProductDraft>({ name: '', category: '', rating: '', note: '' });
  const categories = [
    '图书音像', '电脑/办公', '手机/数码', '美妆个护', '家用电器', '家居生活', '其他',
    '母婴/玩具', '家具/家装/建材', '钟表/首饰/眼镜/礼品', '食品/保健', '鞋类箱包',
    '运动户外', '服饰服装', '机票/充值/票务/虚拟',
  ];

  let seq = 0;
  const uid = () => `m-${Date.now()}-${++seq}`;

  function label(s: SentimentPredictResult['sentiment']) {
    if (s === 'positive') return '正向';
    if (s === 'negative') return '负向';
    return '中性';
  }

  async function scrollBottom() {
    await nextTick();
    const el = threadRef.value;
    if (el) el.scrollTop = el.scrollHeight;
  }

  async function runPredict(content: string) {
    const body = content.trim();
    if (!body) return;
    loading.value = true;
    hint.value = '正在分析…';
    messages.value.push({
      id: uid(),
      role: 'user',
      content: body,
      productName: product.value.name || undefined,
    });
    const pendingId = uid();
    messages.value.push({ id: pendingId, role: 'assistant', content: '', pending: true });
    await scrollBottom();
    try {
      const result = await predictSentiment({
        content: body,
        product: product.value.name ? { ...product.value } : undefined,
      });
      const idx = messages.value.findIndex((m) => m.id === pendingId);
      if (idx >= 0) {
        messages.value[idx] = { id: pendingId, role: 'assistant', content: result.summary, result };
      }
      hint.value = '分析完成';
    } catch (e) {
      const idx = messages.value.findIndex((m) => m.id === pendingId);
      if (idx >= 0) {
        messages.value[idx] = {
          id: pendingId,
          role: 'assistant',
          content: e instanceof Error ? e.message : '分析失败',
        };
      }
      hint.value = '分析失败，请稍后重试';
    } finally {
      loading.value = false;
      await scrollBottom();
    }
  }

  async function submit() {
    const t = text.value;
    text.value = '';
    await runPredict(t);
  }

  async function saveProduct() {
    showProduct.value = false;
    const draft = reviewDraft.value;
    reviewDraft.value = '';
    await runPredict(draft);
  }

  onMounted(() => {
    document.title = '洞察 · Sentiment';
    const name = String(route.query.productName || '').trim();
    const category = String(route.query.category || '').trim();
    const content = String(route.query.content || '').trim();
    if (name) product.value.name = name;
    if (category) product.value.category = category;
    if (name) hint.value = `已带入商品「${name}」，直接输入评价即可`;
    if (content) {
      text.value = content;
      hint.value = '已带入评价原文，可直接发送分析';
    }
  });
</script>

<style lang="less" scoped>
  .insight-m {
    height: calc(100dvh - 58px - env(safe-area-inset-bottom));
    display: flex;
    flex-direction: column;
  }
  .head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 14px 14px 8px;
    .kicker {
      display: block;
      font-size: 10px;
      letter-spacing: 0.12em;
      color: var(--muted);
    }
    h1 {
      margin: 4px 0 0;
      font-size: 22px;
      letter-spacing: -0.04em;
    }
    .bind {
      border: 0;
      background: var(--teal-soft);
      color: var(--teal);
      border-radius: 16px;
      padding: 8px 12px;
      font-size: 12px;
      font-weight: 650;
      max-width: 42%;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }
  .thread {
    flex: 1;
    overflow-y: auto;
    padding: 8px 12px 12px;
  }
  .intro p {
    color: var(--muted);
    font-size: 14px;
    line-height: 1.5;
  }
  .row {
    display: flex;
    gap: 8px;
    margin-bottom: 12px;
    &.user {
      flex-direction: row-reverse;
      .bubble {
        background: var(--teal);
        color: #f5fffc;
      }
      .avatar {
        background: var(--ink);
        color: #fff;
      }
    }
  }
  .avatar {
    width: 32px;
    height: 32px;
    border-radius: 10px;
    background: var(--teal-soft);
    color: var(--teal);
    display: grid;
    place-items: center;
    font-size: 12px;
    font-weight: 700;
    flex-shrink: 0;
  }
  .bubble {
    max-width: 78%;
    padding: 10px 12px;
    border-radius: 14px;
    background: #fff;
    border: 1px solid var(--line);
    font-size: 14px;
    line-height: 1.45;
    p {
      margin: 0;
    }
    small {
      display: block;
      margin-top: 6px;
      opacity: 0.8;
      font-size: 11px;
    }
    .pending {
      color: var(--muted);
    }
  }
  .result-head {
    display: flex;
    justify-content: space-between;
    margin-bottom: 6px;
    strong.tone-positive {
      color: var(--good);
    }
    strong.tone-negative {
      color: var(--danger);
    }
    strong.tone-neutral {
      color: var(--muted);
    }
  }
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 8px;
    span {
      background: var(--teal-soft);
      color: var(--teal);
      font-size: 11px;
      padding: 2px 8px;
      border-radius: 10px;
    }
  }
  .composer {
    display: flex;
    gap: 8px;
    padding: 8px 12px;
    input {
      flex: 1;
      height: 42px;
      border: 1px solid var(--line);
      border-radius: 21px;
      padding: 0 14px;
      background: #fff;
      outline: none;
    }
    button {
      width: 42px;
      height: 42px;
      border: 0;
      border-radius: 50%;
      background: var(--teal);
      color: #fff;
      font-size: 18px;
    }
  }
  .hint {
    margin: 0;
    padding: 0 14px 8px;
    font-size: 11px;
    color: var(--muted);
  }
  .mask {
    position: fixed;
    inset: 0;
    z-index: 200;
    background: rgba(33, 77, 88, 0.35);
    display: flex;
    align-items: flex-end;
  }
  .sheet {
    width: 100%;
    background: #fff;
    border-radius: 18px 18px 0 0;
    padding: 16px 16px calc(20px + env(safe-area-inset-bottom));
    display: grid;
    gap: 10px;
    h3 {
      margin: 0;
    }
    label {
      display: grid;
      gap: 6px;
      font-size: 13px;
      color: var(--muted);
    }
    input,
    select,
    textarea {
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 10px 12px;
      font-size: 14px;
      color: var(--ink);
    }
    .ok {
      height: 42px;
      border: 0;
      border-radius: 21px;
      background: var(--teal);
      color: #fff;
      font-size: 15px;
    }
  }
</style>
