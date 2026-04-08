<script lang="ts">
	import { t } from 'svelte-i18n';
	import type { CompareTimelineItem } from '$lib/api';

	interface Props {
		trends: CompareTimelineItem[];
		interval: string;
	}

	let { trends, interval }: Props = $props();

	const COLORS = ['#3b82f6', '#ef4444', '#22c55e', '#f59e0b', '#8b5cf6'];

	const PAD_LEFT = 40;
	const PAD_RIGHT = 16;
	const PAD_TOP = 16;
	const PAD_BOTTOM = 28;
	const CHART_HEIGHT = 220;

	let chartWidth = $state(600);
	let hoveredIndex = $state<number | null>(null);

	const drawWidth = $derived(chartWidth - PAD_LEFT - PAD_RIGHT);
	const drawHeight = $derived(CHART_HEIGHT - PAD_TOP - PAD_BOTTOM);

	const maxPointsLen = $derived(Math.max(1, ...trends.map((tr) => tr.points.length)));
	const maxCount = $derived(
		Math.max(1, ...trends.flatMap((tr) => tr.points.map((p) => p.article_count)))
	);

	function x(i: number): number {
		if (maxPointsLen <= 1) return PAD_LEFT;
		return PAD_LEFT + (i / (maxPointsLen - 1)) * drawWidth;
	}

	function y(val: number): number {
		return PAD_TOP + drawHeight - (val / maxCount) * drawHeight;
	}

	function polylineForTrend(trend: CompareTimelineItem): string {
		return trend.points.map((p, i) => `${x(i)},${y(p.article_count)}`).join(' ');
	}

	const yTicks = $derived(() => {
		const step = maxCount <= 4 ? 1 : Math.ceil(maxCount / 4);
		const ticks: number[] = [];
		for (let v = 0; v <= maxCount; v += step) {
			ticks.push(v);
		}
		return ticks;
	});

	const xLabels = $derived(() => {
		if (trends.length === 0 || trends[0].points.length === 0) return [];
		const points = trends[0].points;
		const step = Math.max(1, Math.floor(points.length / 5));
		const labels: { i: number; label: string }[] = [];
		for (let i = 0; i < points.length; i += step) {
			const d = new Date(points[i].timestamp);
			const label =
				interval === '7d' || interval === '24h'
					? d.toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' })
					: d.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
			labels.push({ i, label });
		}
		return labels;
	});
</script>

<div class="rounded-lg border border-gray-200 bg-white p-4">
	<div bind:clientWidth={chartWidth}>
		<svg
			viewBox="0 0 {chartWidth} {CHART_HEIGHT}"
			class="w-full"
			style="height: {CHART_HEIGHT}px"
			role="img"
			aria-label={$t('page.compare.title')}
		>
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
				<text
					x={PAD_LEFT - 6}
					y={y(tick) + 4}
					text-anchor="end"
					class="fill-gray-400"
					font-size="10"
				>
					{tick}
				</text>
			{/each}

			<!-- Polylines for each trend -->
			{#each trends as trend, tIdx}
				<polyline
					points={polylineForTrend(trend)}
					fill="none"
					stroke={COLORS[tIdx % COLORS.length]}
					stroke-width="2"
				/>
			{/each}

			<!-- Hover columns -->
			{#if trends.length > 0 && trends[0].points.length > 0}
				{#each trends[0].points as _, i}
					<rect
						x={maxPointsLen <= 1
							? PAD_LEFT
							: x(i) - drawWidth / (maxPointsLen - 1) / 2}
						y={PAD_TOP}
						width={maxPointsLen <= 1 ? drawWidth : drawWidth / (maxPointsLen - 1)}
						height={drawHeight}
						fill="transparent"
						onmouseenter={() => (hoveredIndex = i)}
						onmouseleave={() => (hoveredIndex = null)}
						ontouchstart={() => (hoveredIndex = i)}
					/>
				{/each}
			{/if}

			<!-- Hover vertical line -->
			{#if hoveredIndex !== null}
				<line
					x1={x(hoveredIndex)}
					y1={PAD_TOP}
					x2={x(hoveredIndex)}
					y2={PAD_TOP + drawHeight}
					stroke="#9ca3af"
					stroke-width="1"
					stroke-dasharray="4,2"
				/>
			{/if}

			<!-- Hover dots -->
			{#if hoveredIndex !== null}
				{#each trends as trend, tIdx}
					{#if trend.points[hoveredIndex]}
						<circle
							cx={x(hoveredIndex)}
							cy={y(trend.points[hoveredIndex].article_count)}
							r="4"
							fill={COLORS[tIdx % COLORS.length]}
						/>
					{/if}
				{/each}
			{/if}

			<!-- X-axis labels -->
			{#each xLabels() as { i, label }}
				<text
					x={x(i)}
					y={CHART_HEIGHT - 4}
					text-anchor="middle"
					class="fill-gray-400"
					font-size="10"
				>
					{label}
				</text>
			{/each}

			<!-- Tooltip -->
			{#if hoveredIndex !== null && trends.length > 0 && trends[0].points[hoveredIndex]}
				{@const tx = Math.min(
					Math.max(x(hoveredIndex), PAD_LEFT + 70),
					chartWidth - PAD_RIGHT - 70
				)}
				{@const tooltipH = 18 + trends.length * 14}
				<g>
					<rect
						x={tx - 66}
						y={PAD_TOP - 2}
						width="132"
						height={tooltipH}
						rx="4"
						fill="#1f2937"
						opacity="0.9"
					/>
					<text x={tx} y={PAD_TOP + 11} text-anchor="middle" fill="white" font-size="10">
						{new Date(trends[0].points[hoveredIndex].timestamp).toLocaleString('ko-KR', {
							month: 'short',
							day: 'numeric',
							hour: '2-digit',
							minute: '2-digit'
						})}
					</text>
					{#each trends as trend, tIdx}
						{#if trend.points[hoveredIndex]}
							<text
								x={tx}
								y={PAD_TOP + 24 + tIdx * 14}
								text-anchor="middle"
								fill={COLORS[tIdx % COLORS.length]}
								font-size="10"
							>
								{trend.title}: {trend.points[hoveredIndex].article_count}
							</text>
						{/if}
					{/each}
				</g>
			{/if}
		</svg>
	</div>

	<!-- Legend -->
	<div class="mt-3 flex flex-wrap gap-4">
		{#each trends as trend, tIdx}
			<div class="flex items-center gap-1.5">
				<span
					class="inline-block h-3 w-3 rounded-full"
					style="background-color: {COLORS[tIdx % COLORS.length]}"
				></span>
				<span class="text-xs text-gray-600">{trend.title}</span>
			</div>
		{/each}
	</div>
</div>
