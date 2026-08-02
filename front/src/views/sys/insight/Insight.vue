<template>
  <main class="insight-page">
    <header class="insight-nav">
      <button class="insight-brand" type="button" @click="router.push('/system/user')">
        <span class="brand-mark"><i /><i /><i /></span>
        <b class="brand-word">Sentiment</b>
      </button>
      <div class="mode-switch">
        <button :class="{ active: activeTab === 'chat' }" type="button" @click="activeTab = 'chat'">聊天</button>
        <button :class="{ active: activeTab === 'work' }" type="button" @click="activeTab = 'work'">工作</button>
      </div>
      <button class="exit-button" type="button" @click="logout">退出登录</button>
    </header>

    <section v-if="activeTab === 'chat'" class="chat-workspace">
      <div v-if="!messages.length" class="chat-intro">
        <span class="insight-kicker">SENTIMENT COPILOT</span>
        <h1>准备好了，随时开始</h1>
        <p>补充商品信息或直接输入用户反馈，模型会像对话一样返回情绪分析结果。</p>
      </div>

      <div v-else ref="threadRef" class="chat-thread">
        <article v-for="item in messages" :key="item.id" class="chat-row" :class="item.role">
          <div class="chat-avatar">{{ item.role === 'user' ? '你' : 'AI' }}</div>
          <div class="chat-bubble">
            <template v-if="item.role === 'user'">
              <p class="bubble-text">{{ item.content }}</p>
              <div v-if="item.productName" class="bubble-meta">商品：{{ item.productName }}</div>
            </template>
            <template v-else-if="item.pending">
              <p class="bubble-text pending">正在分析情绪与标签…</p>
            </template>
            <template v-else-if="item.result">
              <div class="result-head">
                <div>
                  <span class="result-label">情绪倾向</span>
                  <strong :class="'tone-' + item.result.sentiment">{{ sentimentLabel(item.result.sentiment) }}</strong>
                </div>
                <div>
                  <span class="result-label">置信度</span>
                  <strong>{{ item.result.score }}%</strong>
                </div>
              </div>
              <p class="bubble-text">{{ item.result.summary }}</p>
              <div v-if="item.result.keywords?.length" class="keyword-row">
                <span v-for="word in item.result.keywords" :key="word">{{ word }}</span>
              </div>
            </template>
            <template v-else>
              <p class="bubble-text">{{ item.content }}</p>
            </template>
          </div>
        </article>
      </div>

      <form class="chat-composer" @submit.prevent="submitMessage">
        <button class="plus-button" type="button" aria-label="添加商品信息" @click="showProductModal = true">＋</button>
        <input
          v-model="message"
          :placeholder="language === 'zh' ? '问问用户的真实感受' : 'Ask about your users’ real feelings'"
          :disabled="loading"
        />
        <button class="language-button" type="button" :aria-label="language === 'zh' ? '切换英文' : '切换中文'" @click="toggleLanguage">
          {{ language === 'zh' ? '中' : 'EN' }}<span>⌄</span>
        </button>
        <button class="send-button" type="submit" :disabled="loading">{{ loading ? '…' : '↑' }}</button>
      </form>
      <p class="api-hint">
        <span v-if="product.name" class="product-chip">已绑定：{{ product.name }}</span>
        {{ apiMessage }}
      </p>
    </section>

    <section v-else class="work-panel">
      <span class="insight-kicker">WORKSPACE</span>
      <h1>把洞察变成下一步行动。</h1>
      <p>这里会承载后续的产品分析工作流。</p>
      <button class="back-action" type="button" @click="activeTab = 'chat'">回到聊天 <span>→</span></button>
    </section>

    <div v-if="showProductModal" class="modal-mask" @click.self="closeProductModal">
      <form class="product-modal" @submit.prevent="saveProduct">
        <button class="modal-close" type="button" @click="closeProductModal">×</button>
        <span class="insight-kicker">PRODUCT CONTEXT</span>
        <h2>补充商品信息</h2>
        <p>填写商品与用户评价后保存，将调用模型分析并在对话中展示结果。</p>
        <label>商品名称<input v-model="product.name" required placeholder="例如：澄见智能水杯" /></label>
        <label>
          商品类别
          <select v-model="product.category">
            <option value="">请选择商品类别</option>
            <option v-for="cat in categoryOptions" :key="cat" :value="cat">{{ cat }}</option>
          </select>
        </label>
        <label>评分<input v-model="product.rating" placeholder="例如：4.5 / 5" /></label>
        <label>
          用户评价
          <textarea v-model="reviewContent" rows="4" required placeholder="例如：质量很好，发货很快，很满意，会回购" />
        </label>
        <label>备注<textarea v-model="product.note" rows="2" placeholder="补充更多背景信息（可选）" /></label>
        <button class="save-product" type="submit" :disabled="loading">
          {{ loading ? '分析中…' : '保存并继续' }} <span>→</span>
        </button>
      </form>
    </div>
  </main>
</template>

<script lang="ts" setup>
  import { nextTick, ref } from 'vue';
  import { useRouter } from 'vue-router';
  import { predictSentiment, saveProductDraft, type ProductDraft, type SentimentPredictResult } from '/@/api/sentiment';
  import { useUserStore } from '/@/store/modules/user';

  type ChatRole = 'user' | 'assistant' | 'system';
  interface ChatMessage {
    id: string;
    role: ChatRole;
    content: string;
    productName?: string;
    pending?: boolean;
    result?: SentimentPredictResult;
  }

  const router = useRouter();
  const userStore = useUserStore();
  const activeTab = ref<'chat' | 'work'>('chat');
  const language = ref<'zh' | 'en'>('zh');
  const message = ref('');
  const reviewContent = ref('');
  const loading = ref(false);
  const showProductModal = ref(false);
  const apiMessage = ref('输入评价或补充商品信息后，将调用后端情绪模型接口。');
  const threadRef = ref<HTMLElement | null>(null);
  const messages = ref<ChatMessage[]>([]);
  const product = ref<ProductDraft>({ name: '', category: '', rating: '', note: '' });
  /** 与 AI 模块 _TRAIN_CATEGORIES / reviews_train.csv 一致，不含前端别名 */
  const categoryOptions = [
    '图书音像',
    '电脑/办公',
    '手机/数码',
    '美妆个护',
    '家用电器',
    '家居生活',
    '其他',
    '母婴/玩具',
    '家具/家装/建材',
    '钟表/首饰/眼镜/礼品',
    '食品/保健',
    '鞋类箱包',
    '运动户外',
    '服饰服装',
    '机票/充值/票务/虚拟',
  ] as const;

  let seq = 0;
  function uid(prefix: string) {
    seq += 1;
    return `${prefix}-${Date.now()}-${seq}`;
  }

  function sentimentLabel(sentiment: SentimentPredictResult['sentiment']) {
    if (sentiment === 'positive') return '正向';
    if (sentiment === 'negative') return '负向';
    return '中性';
  }

  function toggleLanguage() {
    language.value = language.value === 'zh' ? 'en' : 'zh';
    apiMessage.value = language.value === 'zh' ? '已切换为中文输入' : 'Switched to English input';
  }

  async function scrollThread() {
    await nextTick();
    const el = threadRef.value;
    if (el) el.scrollTop = el.scrollHeight;
  }

  function closeProductModal() {
    if (!loading.value) showProductModal.value = false;
  }

  async function runPredict(content: string, fromModal = false) {
    const text = content.trim();
    if (!text) {
      apiMessage.value = language.value === 'zh' ? '请先填写用户评价内容。' : 'Please enter review content first.';
      return;
    }

    activeTab.value = 'chat';
    loading.value = true;
    apiMessage.value = '正在调用后端与情绪模型…';

    const productPayload = product.value.name ? { ...product.value } : undefined;
    messages.value.push({
      id: uid('user'),
      role: 'user',
      content: text,
      productName: productPayload?.name,
    });
    const pendingId = uid('ai');
    messages.value.push({ id: pendingId, role: 'assistant', content: '', pending: true });
    await scrollThread();

    try {
      if (fromModal && productPayload) {
        await saveProductDraft(productPayload);
      }
      const result = await predictSentiment({
        content: text,
        product: productPayload,
      });
      const idx = messages.value.findIndex((m) => m.id === pendingId);
      if (idx >= 0) {
        messages.value[idx] = {
          id: pendingId,
          role: 'assistant',
          content: result.summary,
          result,
        };
      }
      apiMessage.value = fromModal
        ? '商品信息已保存，分析结果已返回。'
        : '分析完成，结果由模型接口返回。';
    } catch (err) {
      const idx = messages.value.findIndex((m) => m.id === pendingId);
      const fallback: SentimentPredictResult = {
        sentiment: 'neutral',
        score: 0,
        summary: '模型接口暂时不可用，请确认后端与 product-sentiment-ai 服务已启动后重试。',
        keywords: ['接口异常'],
      };
      if (idx >= 0) {
        messages.value[idx] = {
          id: pendingId,
          role: 'assistant',
          content: fallback.summary,
          result: fallback,
        };
      }
      apiMessage.value = err instanceof Error ? err.message : '分析失败，请稍后重试。';
    } finally {
      loading.value = false;
      await scrollThread();
    }
  }

  async function submitMessage() {
    const text = message.value.trim();
    if (!text) {
      apiMessage.value = language.value === 'zh' ? '先输入一段用户反馈，再发送给模型。' : 'Enter some user feedback before sending.';
      return;
    }
    message.value = '';
    await runPredict(text, false);
  }

  async function saveProduct() {
    const text = reviewContent.value.trim();
    if (!product.value.name.trim()) {
      apiMessage.value = '请填写商品名称。';
      return;
    }
    if (!text) {
      apiMessage.value = '请填写用户评价，以便调用模型分析。';
      return;
    }
    showProductModal.value = false;
    if (!message.value.trim()) message.value = '';
    reviewContent.value = '';
    await runPredict(text, true);
  }

  async function logout() {
    await userStore.logout(true);
  }
</script>

<style lang="less" scoped>
  .brand-word {
    color: #214d58;
    font-size: 22px;
    font-weight: 600;
    line-height: 0.9;
    letter-spacing: -0.085em;
  }

  .insight-page {
    min-height: 100dvh;
    color: #214d58;
    background: radial-gradient(circle at 82% 0, #dbf7f2, transparent 33rem), #f7fcfb;
  }

  .insight-nav {
    position: sticky;
    top: 0;
    z-index: 3;
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 78px;
    padding: 0 clamp(22px, 6vw, 90px);
    border-bottom: 1px solid rgba(46, 115, 126, 0.12);
    background: rgba(247, 252, 251, 0.8);
    backdrop-filter: blur(20px);
  }

  .insight-brand {
    display: flex;
    align-items: center;
    gap: 10px;
    border: 0;
    color: #214d58;
    background: transparent;
    cursor: pointer;
  }

  .brand-mark {
    position: relative;
    display: inline-block;
    width: 31px;
    height: 31px;
    border-radius: 12px 12px 12px 3px;
    background: linear-gradient(135deg, #1aa2a3, #82d9c2);
  }

  .brand-mark i {
    position: absolute;
    border: 2px solid #f1fffb;
    border-radius: 2px;
  }

  .brand-mark i:nth-child(1) {
    top: 7px;
    left: 6px;
    width: 11px;
    height: 9px;
    border-right: 0;
  }

  .brand-mark i:nth-child(2) {
    top: 11px;
    left: 13px;
    width: 12px;
    height: 8px;
    border-left: 0;
    border-bottom: 0;
    transform: skewX(-25deg);
  }

  .brand-mark i:nth-child(3) {
    right: 4px;
    bottom: 7px;
    width: 11px;
    height: 6px;
    border-left: 0;
    border-top: 0;
  }

  .mode-switch {
    display: flex;
    padding: 3px;
    border-radius: 999px;
    background: #edf4f2;
    box-shadow: inset 0 1px 2px rgba(66, 130, 132, 0.06);
  }

  .mode-switch button {
    min-width: 90px;
    height: 42px;
    border: 0;
    border-radius: 999px;
    color: #749297;
    background: transparent;
    cursor: pointer;
    font-size: 16px;
  }

  .mode-switch .active {
    color: #244f58;
    background: #fff;
    box-shadow: 0 5px 15px rgba(72, 129, 132, 0.12);
  }

  .exit-button {
    border: 0;
    color: #5d878a;
    background: transparent;
    cursor: pointer;
    font-size: 13px;
    font-weight: 700;
  }

  .chat-workspace {
    display: flex;
    min-height: calc(100dvh - 78px);
    flex-direction: column;
    align-items: center;
    padding: 36px 22px 28px;
  }

  .chat-intro {
    flex: 1;
    display: grid;
    place-content: center;
    text-align: center;
    max-width: 640px;
  }

  .insight-kicker {
    display: inline-flex;
    margin-bottom: 18px;
    color: #69a29e;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.18em;
  }

  .chat-intro h1,
  .work-panel h1 {
    margin: 0;
    color: #214d58;
    font-size: clamp(32px, 4vw, 52px);
    font-weight: 600;
    letter-spacing: -0.07em;
  }

  .chat-intro p,
  .work-panel p {
    margin: 17px 0 0;
    color: #8ba5a6;
    font-size: 13px;
  }

  .chat-thread {
    width: min(780px, 100%);
    flex: 1;
    max-height: calc(100dvh - 250px);
    overflow-y: auto;
    padding: 8px 4px 20px;
    scroll-behavior: smooth;
  }

  .chat-row {
    display: flex;
    gap: 12px;
    margin-bottom: 18px;
  }

  .chat-row.user {
    flex-direction: row-reverse;
  }

  .chat-avatar {
    flex: 0 0 36px;
    width: 36px;
    height: 36px;
    display: grid;
    place-items: center;
    border-radius: 12px;
    color: #effffc;
    background: #167f87;
    font-size: 12px;
    font-weight: 700;
  }

  .chat-row.user .chat-avatar {
    background: #3d6f78;
  }

  .chat-bubble {
    max-width: min(560px, calc(100% - 56px));
    padding: 16px 18px;
    border: 1px solid rgba(56, 125, 131, 0.12);
    border-radius: 18px;
    background: rgba(255, 255, 255, 0.88);
    box-shadow: 0 10px 28px rgba(76, 147, 144, 0.08);
  }

  .chat-row.user .chat-bubble {
    background: #e7f6f0;
    border-color: rgba(56, 125, 131, 0.1);
  }

  .bubble-text {
    margin: 0;
    color: #3f6a70;
    font-size: 14px;
    line-height: 1.7;
    white-space: pre-wrap;
  }

  .bubble-text.pending {
    color: #8ba5a6;
  }

  .bubble-meta {
    margin-top: 8px;
    color: #6f9497;
    font-size: 11px;
  }

  .result-head {
    display: flex;
    gap: 28px;
    margin-bottom: 12px;
  }

  .result-head > div {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .result-label {
    color: #8ba5a6;
    font-size: 11px;
  }

  .result-head strong {
    color: #238d89;
    font-size: 22px;
  }

  .tone-positive {
    color: #1f9a74 !important;
  }

  .tone-negative {
    color: #c45b5b !important;
  }

  .tone-neutral {
    color: #7a8f92 !important;
  }

  .keyword-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 12px;
  }

  .keyword-row span {
    padding: 6px 10px;
    border-radius: 999px;
    color: #4d8c88;
    background: #e7f6f0;
    font-size: 11px;
  }

  .chat-composer {
    display: flex;
    align-items: center;
    width: min(1150px, 100%);
    min-height: 76px;
    margin-top: 18px;
    padding: 9px 12px 9px 14px;
    border: 1px solid rgba(56, 125, 131, 0.13);
    border-radius: 22px;
    background: rgba(255, 255, 255, 0.82);
    box-shadow: 0 18px 45px rgba(76, 147, 144, 0.1);
  }

  .chat-composer input {
    flex: 1;
    min-width: 0;
    height: 52px;
    border: 0;
    outline: 0;
    color: #214d58;
    background: transparent;
    font-size: 16px;
  }

  .plus-button,
  .language-button,
  .send-button {
    border: 0;
    cursor: pointer;
  }

  .plus-button {
    width: 46px;
    height: 46px;
    border-radius: 14px;
    color: #368a87;
    background: #e1f5ef;
    font-size: 29px;
    font-weight: 300;
    line-height: 1;
  }

  .language-button {
    margin-right: 8px;
    color: #759397;
    background: transparent;
    font-size: 13px;
  }

  .send-button {
    width: 46px;
    height: 46px;
    border-radius: 50%;
    color: #effffc;
    background: #107f87;
    box-shadow: 0 7px 16px rgba(16, 127, 135, 0.2);
    font-size: 22px;
  }

  .send-button:disabled,
  .save-product:disabled {
    cursor: not-allowed;
    opacity: 0.42;
  }

  .api-hint {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    width: min(1150px, 100%);
    margin-top: 14px;
    color: #9ab1b1;
    font-size: 11px;
  }

  .product-chip {
    display: inline-flex;
    padding: 4px 10px;
    border-radius: 999px;
    color: #2f7d7a;
    background: #e1f5ef;
    font-weight: 700;
  }

  .work-panel {
    display: grid;
    min-height: calc(100dvh - 78px);
    place-content: center;
    padding: 40px 22px;
    text-align: center;
  }

  .back-action {
    margin: 35px auto 0;
    padding: 13px 20px;
    border: 0;
    border-radius: 13px;
    color: #f2fffc;
    background: #167f87;
    cursor: pointer;
  }

  .modal-mask {
    position: fixed;
    inset: 0;
    z-index: 10;
    display: grid;
    place-items: center;
    padding: 22px;
    background: rgba(31, 77, 84, 0.22);
    backdrop-filter: blur(8px);
  }

  .product-modal {
    position: relative;
    width: min(490px, 100%);
    max-height: min(90dvh, 720px);
    overflow: auto;
    padding: 31px;
    border: 1px solid rgba(255, 255, 255, 0.75);
    border-radius: 26px;
    background: rgba(250, 255, 253, 0.94);
    box-shadow: 0 25px 70px rgba(52, 115, 117, 0.19);
  }

  .modal-close {
    position: absolute;
    top: 17px;
    right: 18px;
    border: 0;
    color: #7e9b9d;
    background: transparent;
    cursor: pointer;
    font-size: 25px;
  }

  .product-modal h2 {
    margin: 0;
    color: #285963;
    font-size: 25px;
    letter-spacing: -0.06em;
  }

  .product-modal p {
    margin: 8px 0 24px;
    color: #8aa3a4;
    font-size: 12px;
  }

  .product-modal label {
    display: block;
    margin-top: 14px;
    color: #60878a;
    font-size: 11px;
  }

  .product-modal input,
  .product-modal select,
  .product-modal textarea {
    display: block;
    width: 100%;
    margin-top: 7px;
    padding: 0 13px;
    border: 1px solid rgba(56, 125, 131, 0.15);
    border-radius: 12px;
    outline: none;
    color: #285963;
    background: rgba(255, 255, 255, 0.76);
    font: inherit;
    font-size: 13px;
  }

  .product-modal input,
  .product-modal select {
    height: 43px;
  }

  .product-modal textarea {
    padding-top: 11px;
    resize: vertical;
  }

  .product-modal input:focus,
  .product-modal select:focus,
  .product-modal textarea:focus {
    border-color: #55b6a7;
    box-shadow: 0 0 0 3px rgba(85, 182, 167, 0.12);
  }

  .save-product {
    width: 100%;
    height: 45px;
    margin-top: 23px;
    border: 0;
    border-radius: 13px;
    color: #effffc;
    background: #167f87;
    cursor: pointer;
    font-size: 13px;
    font-weight: 700;
  }

  @media (max-width: 600px) {
    .insight-nav {
      padding: 0 18px;
    }

    .mode-switch button {
      min-width: 62px;
      font-size: 13px;
    }

    .exit-button {
      font-size: 11px;
    }

    .insight-brand b {
      font-size: 13px;
    }

    .chat-workspace {
      padding-top: 20px;
    }

    .chat-composer {
      min-height: 64px;
      border-radius: 18px;
    }

    .chat-composer input {
      height: 42px;
      font-size: 14px;
    }

    .plus-button,
    .send-button {
      width: 40px;
      height: 40px;
    }

    .language-button {
      display: none;
    }

    .product-modal {
      padding: 25px 20px;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .insight-page * {
      scroll-behavior: auto !important;
      transition-duration: 0.01ms !important;
    }
  }
</style>
