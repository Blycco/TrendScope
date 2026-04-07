<script lang="ts">
	import { t } from 'svelte-i18n';

	interface ForecastDataPoint {
		date: string;
		yhat: number;
		yhat_lower: number;
		yhat_upper: number;
	}

	interface Props {
		data: ForecastDataPoint[];
	}

	let { data }: Props = $props();

	const PAD_LEFT = 50;
	const PAD_RIGHT = 20;
	const PAD_TOP = 20;
	const PAD_BOTTOM = 36;
	const CHART_HEIGHT = 220;

	let chartWidth = $state(700);

	const drawWidth = $derived(chartWidth - PAD_LEFT - PAD_RIGHT);
	const drawHeight = $derived(CHART_HEIGHT - PAD_TOP - PAD_BOTTOM);

	// Sample data for display (show every Nth point to avoid SVG overload)
	const sampled = $derived(() => {
		if (data.length <= 60) return data;
		const step = Math.ceil(data.length / 60);
		return data.filter((_, i) => i % step === 0 || i === data.length - 1);
	});

	const maxVal = $derived(Math.max(1, ...data.map((p) => p.yhat_upper)));
	const minVal = $derived(Math.min(...data.map((p) => p.yhat_lower)));
	const valRange = $derived(Math.max(1, maxVal - minVal));

	function x(i: number, total: number): number {
		if (total <= 1) return PAD_LEFT;
		return PAD_LEFT + (i / (total - 1)) * drawWidth;
	}

	function y(val: number): number {
		return PAD_TOP + drawHeight - ((val - minVal) / valRange) * drawHeight;
	}

	// Predicted line
	const predictedLine = $derived(() => {
		const pts = sampled();
		return pts.map((p, i) => `${x(i, pts.length)},${y(p.yhat)}`).join(' ');
	});

	// Confidence band polygon
	const confidenceBand = $derived(() => {
		const pts = sampled();
		const upper = pts.map((p, i) => `${x(i, pts.length)},${y(p.yhat_upper)}`);
		const lower = [...pts].reverse().map((p, i) => `${x(pts.length - 1 - i, pts.length)},${y(p.yhat_lower)}`);
		return [...upper, ...lower].join(' ');
	});

	// Y-axis ticks
	const yTicks = $derived(() => {
		const step = valRange <= 4 ? 1 : Math.ceil(valRange / 4);
		const ticks: number[] = [];
		for (let v = Math.floor(minVal); v <= maxVal; v += step) {
			ticks.push(v);
		}
		return ticks;
	});

	// X-axis labels (show ~5 labels)
	const xLabels = $derived(() => {
		const pts = sampled();
		if (pts.length === 0) return [];
		const step = Math.max(1, Math.floor(pts.length / 5));
		const labels: { i: number; label: string }[] = [];
		for (let i = 0; i < pts.length; i += step) {
			const d = new Date(pts[i].date);
			labels.push({
				i,
				label: d.toLocaleDateString('ko-KR', { year: '2-digit', month: 'short' })
			});
		}
		return labels;
	});

	let hoveredIndex = $state<number | null>(null);
</script>

<div class="rounded-lg border border-gray-200 bg-white p-4">
	<div class="flex items-center justify-between mb-3">
		<h3 class="text-sm font-semibold text-gray-700">{$t('forecast.title')}</h3>
		<div class="flex items-center gap-4 text-xs text-gray-500">
			<span class="flex items-center gap-1">
				<span class="inline-block h-0.5 w-4 bg-emerald-500"></span>
				{$t('forecast.predicted')}
			</span>
			<span class="flex items-center gap-1">
				<span class="inline-block h-2.5 w-4 rounded-sm bg-emerald-100 border border-emerald-200"></span>
				{$t('forecast.confidence')}
			</span>
		</div>
	</div>

	{#if data.length === 0}
		<div class="flex items-center justify-center" style="height: {CHART_HEIGHT}px">
			<p class="text-sm text-gray-400">{$t('forecast.no_data')}</p>
		</div>
	{:else}
		<div bind:clientWidth={chartWidth}>
			<svg
				viewBox="0 0 {chartWidth} {CHART_HEIGHT}"
				class="w-full"
				style="height: {CHART_HEIGHT}px"
				role="img"
				aria-label={$t('forecast.title')}
			>
				<defs>
					<linearGradient id="forecastGrad" x1="0" y1="0" x2="0" y2="1">
						<stop offset="0%" stop-color="#10b981" stop-opacity="0.2" />
						<stop offset="100%" stop-color="#10b981" stop-opacity="0.02" />
					</linearGradient>
				</defs>

				<!-- Y-axis gridlines -->
				{#each yTicks() as tick}
					<line
						x1={PAD_LEFT}
						y1={y(tick)}
						x2={chartWidth - PAD_RIGHT}
						y2={y(tick)}
						stroke="#e5e7eb"
						stroke-width="1"
					/>
					<text x={PAD_LEFT - 6} y={y(tick) + 4} text-anchor="end" class="fill-gray-400" font-size="10">
						{Math.round(tick)}
					</text>
				{/each}

				<!-- Confidence interval band -->
				{#if confidenceBand()}
					<polygon points={confidenceBand()} fill="url(#forecastGrad)" stroke="none" />
				{/if}

				<!-- Predicted line -->
				{#if predictedLine()}
					<polyline points={predictedLine()} fill="none" stroke="#10b981" stroke-width="2" />
				{/if}

				<!-- Hover columns & data points -->
				{#each sampled() as point, i}
					<circle
						cx={x(i, sampled().length)}
						cy={y(point.yhat)}
						r="3"
						fill="#10b981"
						opacity={hoveredIndex === i ? 1 : 0}
					/>
					<rect
						x={sampled().length <= 1 ? PAD_LEFT : x(i, sampled().length) - drawWidth / (sampled().length - 1) / 2}
						y={PAD_TOP}
						width={sampled().length <= 1 ? drawWidth : drawWidth / (sampled().length - 1)}
						height={drawHeight}
						fill="transparent"
						onmouseenter={() => (hoveredIndex = i)}
						onmouseleave={() => (hoveredIndex = null)}
						ontouchstart={() => (hoveredIndex = i)}
					/>
				{/each}

				<!-- X-axis labels -->
				{#each xLabels() as { i, label }}
					<text x={x(i, sampled().length)} y={CHART_HEIGHT - 4} text-anchor="middle" class="fill-gray-400" font-size="10">
						{label}
					</text>
				{/each}

				<!-- Tooltip -->
				{#if hoveredIndex !== null && sampled()[hoveredIndex]}
					{@const pt = sampled()[hoveredIndex]}
					{@const tx = Math.min(Math.max(x(hoveredIndex, sampled().length), PAD_LEFT + 70), chartWidth - PAD_RIGHT - 70)}
					<g>
						<rect x={tx - 66} y={PAD_TOP - 2} width="132" height="50" rx="4" fill="#1f2937" opacity="0.9" />
						<text x={tx} y={PAD_TOP + 12} text-anchor="middle" fill="white" font-size="10">
							{new Date(pt.date).toLocaleDateString('ko-KR', { year: 'numeric', month: 'short', day: 'numeric' })}
						</text>
						<text x={tx} y={PAD_TOP + 26} text-anchor="middle" fill="white" font-size="10">
							{$t('forecast.value')}: {pt.yhat.toFixed(1)}
						</text>
						<text x={tx} y={PAD_TOP + 39} text-anchor="middle" fill="#9ca3af" font-size="9">
							[{pt.yhat_lower.toFixed(1)} ~ {pt.yhat_upper.toFixed(1)}]
						</text>
					</g>
				{/if}
			</svg>
		</div>
	{/if}
</div>
