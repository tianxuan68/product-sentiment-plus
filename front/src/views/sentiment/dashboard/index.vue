<template>
  <div class="sentiment-board">
    <a-alert v-if="errorMsg" type="warning" show-icon :message="errorMsg" class="board-alert" />

    <div class="board-kpis">
      <div class="kpi" v-for="item in kpiItems" :key="item.label">
        <div class="kpi-label">{{ item.label }}</div>
        <div class="kpi-value" :style="{ color: item.color }">{{ item.value }}</div>
      </div>
    </div>

    <div class="board-grid board-grid--pie">
      <div class="chart-panel">
        <div class="chart-title">情感极性分布</div>
        <div ref="pieRef" class="chart-box"></div>
      </div>
      <div class="chart-panel">
        <div class="chart-title">高频方面词 Top10</div>
        <div ref="tagRef" class="chart-box"></div>
      </div>
    </div>

    <div class="board-grid board-grid--product">
      <div class="chart-panel">
        <div class="chart-title">最热商品 Top10 <span>按评价条数</span></div>
        <div ref="productTopRef" class="chart-box tall"></div>
      </div>
      <div class="chart-panel">
        <div class="chart-title">商品评论情感结构 <span>各商品正/中/负占比</span></div>
        <div ref="productSentRef" class="chart-box tall"></div>
      </div>
    </div>

    <div class="board-grid board-grid--aspect">
      <div class="chart-panel">
        <div class="chart-title">方面 × 情感分解 <span>细粒度方面情感</span></div>
        <div ref="aspectRef" class="chart-box tall"></div>
      </div>
      <div class="chart-panel">
        <div class="chart-title">服务体验因果透镜 <span>干预视角 ATE</span></div>
        <div ref="lensRef" class="chart-box tall"></div>
        <div class="lens-note" v-if="ateText">{{ ateText }}</div>
      </div>
    </div>

    <div class="board-grid board-grid--mix">
      <div class="chart-panel">
        <div class="chart-title">类目评价分布</div>
        <div ref="categoryRef" class="chart-box"></div>
      </div>
      <div class="chart-panel">
        <div class="chart-title">方面关注雷达 <span>提及强度 vs 正向占比</span></div>
        <div ref="radarRef" class="chart-box"></div>
      </div>
    </div>

    <div class="chart-panel">
      <div class="chart-title">情感时序趋势</div>
      <div ref="trendRef" class="chart-box"></div>
    </div>
  </div>
</template>
<script lang="ts" name="sentiment-dashboard" setup>
  import { computed, nextTick, onMounted, reactive, ref, Ref } from 'vue';
  import { useECharts } from '/@/hooks/web/useECharts';
  import { fetchOverview } from './dashboard.api';

  const colors = {
    positive: '#167f87',
    neutral: '#8aa8ad',
    negative: '#d46b4a',
    ink: '#214d58',
    accent: '#3aa6a8',
  };

  const summary = reactive({ total: 0, positive: 0, neutral: 0, negative: 0 });
  const ateText = ref('');
  const errorMsg = ref('');

  const pieRef = ref<HTMLDivElement | null>(null);
  const tagRef = ref<HTMLDivElement | null>(null);
  const productTopRef = ref<HTMLDivElement | null>(null);
  const productSentRef = ref<HTMLDivElement | null>(null);
  const aspectRef = ref<HTMLDivElement | null>(null);
  const lensRef = ref<HTMLDivElement | null>(null);
  const categoryRef = ref<HTMLDivElement | null>(null);
  const radarRef = ref<HTMLDivElement | null>(null);
  const trendRef = ref<HTMLDivElement | null>(null);

  const { setOptions: setPie } = useECharts(pieRef as Ref<HTMLDivElement>);
  const { setOptions: setTag } = useECharts(tagRef as Ref<HTMLDivElement>);
  const { setOptions: setProductTop } = useECharts(productTopRef as Ref<HTMLDivElement>);
  const { setOptions: setProductSent } = useECharts(productSentRef as Ref<HTMLDivElement>);
  const { setOptions: setAspect } = useECharts(aspectRef as Ref<HTMLDivElement>);
  const { setOptions: setLens } = useECharts(lensRef as Ref<HTMLDivElement>);
  const { setOptions: setCategory } = useECharts(categoryRef as Ref<HTMLDivElement>);
  const { setOptions: setRadar } = useECharts(radarRef as Ref<HTMLDivElement>);
  const { setOptions: setTrend } = useECharts(trendRef as Ref<HTMLDivElement>);

  const kpiItems = computed(() => [
    { label: '评价总数', value: summary.total, color: colors.ink },
    { label: '正向', value: summary.positive, color: colors.positive },
    { label: '中性', value: summary.neutral, color: colors.neutral },
    { label: '负向', value: summary.negative, color: colors.negative },
  ]);

  function seriesMap(list: any[] | undefined) {
    return Object.fromEntries((list || []).map((s) => [s.key, s.data || []]));
  }

  function shortLabel(text: string, max = 10) {
    const s = String(text || '');
    return s.length > max ? `${s.slice(0, max)}…` : s;
  }

  onMounted(async () => {
    let data: any = null;
    try {
      data = await fetchOverview({ limit: 10 });
    } catch (e: any) {
      errorMsg.value = e?.message || '看板数据加载失败，请确认后端已启动并重新登录';
      return;
    }
    if (!data || typeof data !== 'object') {
      errorMsg.value = '看板接口无数据，请检查 /biz/dashboard/overview';
      return;
    }

    const sum = data.summary || {};
    Object.assign(summary, {
      total: Number(sum.total ?? 0),
      positive: Number(sum.positive ?? 0),
      neutral: Number(sum.neutral ?? 0),
      negative: Number(sum.negative ?? 0),
    });
    if (!summary.total) {
      errorMsg.value = '暂无评价数据：请先在评价管理积累记录，或执行演示种子 SQL';
    }

    await nextTick();

    setPie({
      tooltip: { trigger: 'item' },
      legend: { bottom: 0 },
      color: [colors.positive, colors.neutral, colors.negative],
      series: [
        {
          type: 'pie',
          radius: ['42%', '68%'],
          center: ['50%', '46%'],
          label: { formatter: '{b}\n{d}%' },
          data: [
            { name: '正向', value: summary.positive },
            { name: '中性', value: summary.neutral },
            { name: '负向', value: summary.negative },
          ],
        },
      ],
    });

    const tag = data.tagTop || {};
    const tagLabels = tag.labels?.length ? tag.labels : ['暂无数据'];
    const tagValues = tag.values?.length ? tag.values : [0];
    setTag({
      tooltip: { trigger: 'axis' },
      grid: { left: 72, right: 24, top: 16, bottom: 24 },
      xAxis: { type: 'value', name: '提及次数' },
      yAxis: {
        type: 'category',
        data: [...tagLabels].reverse(),
        axisLabel: { width: 64, overflow: 'truncate' },
      },
      series: [
        {
          type: 'bar',
          data: [...tagValues].reverse(),
          itemStyle: { color: colors.positive, borderRadius: [0, 8, 8, 0] },
          barMaxWidth: 18,
        },
      ],
    });

    const productTop = data.productTop || {};
    const pLabels = productTop.labels?.length ? productTop.labels : ['暂无'];
    const pValues = productTop.values?.length ? productTop.values : [0];
    const pRates = productTop.positiveRates || pLabels.map(() => 0);
    setProductTop({
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          const i = params?.[0]?.dataIndex ?? 0;
          const name = pLabels[i] || '';
          const count = pValues[i] ?? 0;
          const rate = Math.round(Number(pRates[i] || 0) * 1000) / 10;
          return `${name}<br/>评价 ${count} 条<br/>正向率 ${rate}%`;
        },
      },
      grid: { left: 96, right: 28, top: 16, bottom: 24 },
      xAxis: { type: 'value', name: '评价数', minInterval: 1 },
      yAxis: {
        type: 'category',
        data: pLabels.map((n) => shortLabel(n, 12)).reverse(),
      },
      series: [
        {
          type: 'bar',
          data: [...pValues].reverse(),
          itemStyle: { color: colors.accent, borderRadius: [0, 8, 8, 0] },
          barMaxWidth: 18,
        },
      ],
    });

    const productSent = data.productSentiment || {};
    const psLabels = productSent.labels?.length ? productSent.labels : ['暂无'];
    const psMap = seriesMap(productSent.series);
    setProductSent({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      legend: { top: 0 },
      grid: { left: 48, right: 16, top: 36, bottom: 48 },
      xAxis: {
        type: 'category',
        data: psLabels.map((n) => shortLabel(n, 8)),
        axisLabel: { interval: 0, rotate: 24 },
      },
      yAxis: { type: 'value', name: '条数', minInterval: 1 },
      color: [colors.positive, colors.neutral, colors.negative],
      series: [
        { name: '正向', type: 'bar', stack: 'p', data: psMap.positive || psLabels.map(() => 0), barMaxWidth: 28 },
        { name: '中性', type: 'bar', stack: 'p', data: psMap.neutral || psLabels.map(() => 0), barMaxWidth: 28 },
        { name: '负向', type: 'bar', stack: 'p', data: psMap.negative || psLabels.map(() => 0), barMaxWidth: 28 },
      ],
    });

    const aspect = data.aspectSentiment || {};
    const aspectLabels = aspect.labels?.length ? aspect.labels : ['暂无'];
    const aMap = seriesMap(aspect.series);
    setAspect({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      legend: { top: 0 },
      grid: { left: 48, right: 16, top: 36, bottom: 40 },
      xAxis: { type: 'category', data: aspectLabels, axisLabel: { interval: 0, rotate: 28 } },
      yAxis: { type: 'value', name: '次数' },
      color: [colors.positive, colors.neutral, colors.negative],
      series: [
        { name: '正向', type: 'bar', stack: 'sent', data: aMap.positive || aspectLabels.map(() => 0), barMaxWidth: 28 },
        { name: '中性', type: 'bar', stack: 'sent', data: aMap.neutral || aspectLabels.map(() => 0), barMaxWidth: 28 },
        { name: '负向', type: 'bar', stack: 'sent', data: aMap.negative || aspectLabels.map(() => 0), barMaxWidth: 28 },
      ],
    });

    const lens = data.serviceLens || {};
    const posRates = (lens.positiveRates || [0, 0]).map((v) => Math.round(Number(v) * 1000) / 10);
    const negRates = (lens.negativeRates || [0, 0]).map((v) => Math.round(Number(v) * 1000) / 10);
    if (lens.ate == null) {
      ateText.value = '样本量不足，暂无法估计服务体验干预效应';
    } else {
      const sign = lens.ate > 0 ? '高' : lens.ate < 0 ? '低' : '持平';
      ateText.value = `提及服务体验词时，正向率约${sign} ${Math.abs(Math.round(Number(lens.ate) * 1000) / 10)}%（粗估计 ATE）`;
    }
    setLens({
      tooltip: { trigger: 'axis', valueFormatter: (v) => `${v}%` },
      legend: { top: 0 },
      grid: { left: 48, right: 16, top: 36, bottom: 28 },
      xAxis: { type: 'category', data: lens.categories || ['提及服务体验', '未提及服务体验'] },
      yAxis: { type: 'value', name: '%', max: 100 },
      color: [colors.positive, colors.negative],
      series: [
        { name: '正向率', type: 'bar', data: posRates, barMaxWidth: 36, itemStyle: { borderRadius: [8, 8, 0, 0] } },
        { name: '负向率', type: 'bar', data: negRates, barMaxWidth: 36, itemStyle: { borderRadius: [8, 8, 0, 0] } },
      ],
    });

    const category = data.categoryMix || {};
    const catItems = category.items?.length
      ? category.items
      : [{ name: '暂无', value: 0 }];
    setCategory({
      tooltip: { trigger: 'item' },
      legend: { bottom: 0, type: 'scroll' },
      color: ['#167f87', '#3aa6a8', '#82d9c2', '#8aa8ad', '#d46b4a', '#e0a36b', '#6b8f96', '#214d58'],
      series: [
        {
          type: 'pie',
          roseType: 'radius',
          radius: ['18%', '62%'],
          center: ['50%', '44%'],
          label: { formatter: '{b} {d}%' },
          data: catItems.map((i) => ({ name: i.name, value: i.value })),
        },
      ],
    });

    const radar = data.aspectRadar || {};
    const indicators = radar.indicators?.length
      ? radar.indicators
      : [{ name: '暂无', max: 100 }];
    const radarSeries = radar.series || [];
    setRadar({
      tooltip: {},
      legend: { bottom: 0 },
      radar: {
        indicator: indicators,
        radius: '58%',
        center: ['50%', '46%'],
        splitArea: { areaStyle: { color: ['rgba(243,251,252,0.9)', 'rgba(232,246,241,0.55)'] } },
      },
      color: [colors.accent, colors.negative],
      series: [
        {
          type: 'radar',
          data: radarSeries.map((s) => ({
            name: s.name,
            value: s.data || indicators.map(() => 0),
            areaStyle: { opacity: 0.12 },
          })),
        },
      ],
    });

    const trend = data.dailyTrend || {};
    const trendLabels = trend.labels?.length ? trend.labels : ['暂无'];
    const tMap = seriesMap(trend.series);
    setTrend({
      tooltip: { trigger: 'axis' },
      legend: { top: 0 },
      grid: { left: 48, right: 24, top: 36, bottom: 28 },
      xAxis: { type: 'category', data: trendLabels, boundaryGap: false },
      yAxis: { type: 'value', minInterval: 1 },
      color: [colors.positive, colors.neutral, colors.negative],
      series: [
        { name: '正向', type: 'line', smooth: true, data: tMap.positive || [0], areaStyle: { opacity: 0.08 } },
        { name: '中性', type: 'line', smooth: true, data: tMap.neutral || [0], areaStyle: { opacity: 0.06 } },
        { name: '负向', type: 'line', smooth: true, data: tMap.negative || [0], areaStyle: { opacity: 0.08 } },
      ],
    });
  });
</script>
<style lang="less" scoped>
  .sentiment-board {
    display: flex;
    flex-direction: column;
    gap: 24px;
    width: 100%;
    box-sizing: border-box;
    // 与下方表格页查询区顶部留白对齐
    padding: 20px 0 16px;
  }

  .board-alert {
    border-radius: 12px;
  }

  .board-kpis,
  .board-grid {
    display: grid;
    gap: 24px;
    width: 100%;
    box-sizing: border-box;
  }

  .board-kpis {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .board-grid--pie,
  .board-grid--mix {
    grid-template-columns: minmax(0, 3fr) minmax(0, 5fr);
  }

  .board-grid--product,
  .board-grid--aspect {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  }

  .kpi,
  .chart-panel {
    min-width: 0;
    box-sizing: border-box;
    background: rgba(255, 255, 255, 0.94);
    border: 1px solid rgba(46, 115, 126, 0.12);
    border-radius: 16px;
    box-shadow: 0 8px 22px rgba(66, 146, 147, 0.06);
  }

  .kpi {
    padding: 18px 20px;
  }

  .kpi-label {
    margin-bottom: 8px;
    color: #75979b;
    font-size: 13px;
  }

  .kpi-value {
    font-size: 28px;
    font-weight: 700;
    letter-spacing: -0.04em;
    line-height: 1.1;
  }

  .chart-panel {
    padding: 18px 18px 12px;
  }

  .chart-title {
    margin-bottom: 8px;
    color: #214d58;
    font-size: 15px;
    font-weight: 650;

    span {
      margin-left: 8px;
      color: #75979b;
      font-size: 12px;
      font-weight: 500;
    }
  }

  .chart-box {
    width: 100%;
    height: 300px;

    &.tall {
      height: 340px;
    }
  }

  .lens-note {
    margin: 0 4px 8px;
    color: #75979b;
    font-size: 12px;
    line-height: 1.5;
  }

  @media (max-width: 992px) {
    .board-kpis {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .board-grid--pie,
    .board-grid--product,
    .board-grid--aspect,
    .board-grid--mix {
      grid-template-columns: minmax(0, 1fr);
    }
  }
</style>
