<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { apiRequest } from '$lib/api';
	import type { TrendTimelineResponse, TimelinePoint } from '$lib/api';

	interface Props {
		groupId: string;
	}

	let { groupId }: Props = $props();

	const intervals = ['15m', '30m', '1h', '6h', '24h', '7d'] as const;
	type Interval = (typeof intervals)[number];

	const intervalLabelKey: Record<Interval, string> = {
		'15m': 'chart.timeline.interval.15m',
		'30m': 'chart.timeline.interval.30m',
		'1h': 'filter.time.1h',
		'6h': 'filter.time.6h',
		'24h': 'filter.time.24h',
		'7d': 'filter.time.7d'
	};

	let selectedInterval = $state<Interval>('1h');
	let points = $state<TimelinePoint[]>([]);
	let isLoading = $state(true);
	let hoveredIndex = $state<number | null>(null);
	let chartWidth = $state(600);

	const PAD_LEFT = 40;
	const PAD_RIGHT = 16;
	const PAD_TOP = 16;
	const PAD_BOTTOM = 28;
	const CHART_HEIGHT = 180;

	const drawWidth = $derived(chartWidth - PAD_LEFT - PAD_RIGHT);
	const drawHeight = $derived(CHART_HEIGHT - PAD_TOP - PAD_BOTTOM);

	const maxCount = $derived(Math.max(1, ...points.map((p) => p.article_count)));

	function x(i: number): number {
		if (points.length <= 1) return PAD_LEFT;
		return PAD_LEFT + (i / (points.length - 1)) * drawWidth;
	}

	function y(val: number): number {
		return PAD_TOP + drawHeight - (val / maxCount) * drawHeight;
	}

	const polylinePoints = $derived(points.map((p, i) => `${x(i)},${y(p.article_count)}`).join(' '));

	const polygonPoints = $derived(
		points.length > 0
			? [
					...points.map((p, i) => `${x(i)},${y(p.article_count)}`),
					`${x(points.length - 1)},${PAD_TOP + drawHeight}`,
					`${PAD_LEFT},${PAD_TOP + drawHeight}`
				].join(' ')
			: ''
	);

	const yTicks = $derived(() => {
		const step = maxCount <= 4 ? 1 : Math.ceil(maxCount / 4);
		const ticks: number[] = [];
		for (let v = 0; v <= maxCount; v += step) {
			ticks.push(v);
		}
		return ticks;
	});

	const xLabels = $derived(() => {
		if (points.length === 0) return [];
		const step = Math.max(1, Math.floor(points.length / 5));
		const labels: { i: number; label: string }[] = [];
		for (let i = 0; i < points.length; i += step) {
			const d = new Date(points[i].timestamp);
			const label =
				selectedInterval === '7d'
					? d.toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' })
					: selectedInterval === '24h'
						? d.toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' })
						: d.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
			labels.push({ i, label });
		}
		return labels;
	});

	async function loadTimeline(): Promise<void> {
		isLoading = true;
		try {
			const resp = await apiRequest<TrendTimelineResponse>(
				`/trends/${groupId}/timeline?interval=${selectedInterval}`
			);
			points = resp.points;
		} catch {
			points = [];
		} finally {
			isLoading = false;
		}
	}

	function selectInterval(interval: Interval): void {
		selectedInterval = interval;
		loadTimeline();
	}

	onMount(() => {
		loadTimeline();
	});
</script>

<div class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4">
	<div class="flex items-center justify-between mb-3">
		<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300">{$t('chart.timeline.title')}</h3>
		<div class="flex gap-1">
			{#each intervals as interval}
				<button
					type="button"
					class="px-2 py-0.5 text-xs rounded-md transition-colors {selectedInterval === interval
						? 'bg-blue-600 text-white'
						: 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600'}"
					onclick={() => selectInterval(interval)}
				>
					{$t(intervalLabelKey[interval])}
				</button>
			{/each}
		</div>
	</div>

	{#if isLoading}
		<div class="flex items-center justify-center" style="height: {CHART_HEIGHT}px">
			<p class="text-sm text-gray-400">{$t('status.loading')}</p>
		</div>
	{:else if points.length === 0}
		<div class="flex items-center justify-center" style="height: {CHART_HEIGHT}px">
			<p class="text-sm text-gray-400">{$t('chart.timeline.no_data')}</p>
		</div>
	{:else}
		<div bind:clientWidth={chartWidth}>
			<svg
				viewBox="0 0 {chartWidth} {CHART_HEIGHT}"
				class="w-full"
				style="height: {CHART_HEIGHT}px"
				role="img"
				aria-label={$t('chart.timeline.title')}
			>
				<defs>
					<linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
						<stop offset="0%" stop-color="var(--chart-area-start)" />
						<stop offset="100%" stop-color="var(--chart-area-end)" />
					</linearGradient>
				</defs>

				<!-- Y-axis gridlines -->
				{#each yTicks() as tick}
					<line
						x1={PAD_LEFT}
						y1={y(tick)}
						x2={chartWidth - PAD_RIGHT}
						y2={y(tick)}
						stroke="var(--chart-grid)"
						stroke-width="1"
					/>
					<text x={PAD_LEFT - 6} y={y(tick) + 4} text-anchor="end" class="fill-gray-400" font-size="10">
						{tick}
					</text>
				{/each}

				<!-- Area -->
				{#if polygonPoints}
					<polygon points={polygonPoints} fill="url(#areaGrad)" />
				{/if}

				<!-- Line -->
				<polyline points={polylinePoints} fill="none" stroke="var(--chart-line)" stroke-width="2" />

				<!-- Data points -->
				{#each points as point, i}
					<circle cx={x(i)} cy={y(point.article_count)} r="3" fill="var(--chart-line)" opacity={hoveredIndex === i ? 1 : 0} />
				{/each}

				<!-- Hover columns -->
				{#each points as _, i}
					<rect
						x={points.length <= 1 ? PAD_LEFT : x(i) - drawWidth / (points.length - 1) / 2}
						y={PAD_TOP}
						width={points.length <= 1 ? drawWidth : drawWidth / (points.length - 1)}
						height={drawHeight}
						fill="transparent"
						onmouseenter={() => (hoveredIndex = i)}
						onmouseleave={() => (hoveredIndex = null)}
						ontouchstart={() => (hoveredIndex = i)}
					/>
				{/each}

				<!-- X-axis labels -->
				{#each xLabels() as { i, label }}
					<text x={x(i)} y={CHART_HEIGHT - 4} text-anchor="middle" class="fill-gray-400" font-size="10">
						{label}
					</text>
				{/each}

				<!-- Tooltip -->
				{#if hoveredIndex !== null && points[hoveredIndex]}
					{@const pt = points[hoveredIndex]}
					{@const tx = Math.min(Math.max(x(hoveredIndex), PAD_LEFT + 60), chartWidth - PAD_RIGHT - 60)}
					<g>
						<rect x={tx - 56} y={PAD_TOP - 2} width="112" height="40" rx="4" fill="var(--chart-tooltip-bg)" opacity="0.9" />
						<text x={tx} y={PAD_TOP + 13} text-anchor="middle" fill="var(--chart-tooltip-text)" font-size="10">
							{new Date(pt.timestamp).toLocaleString('ko-KR', {
								month: 'short',
								day: 'numeric',
								hour: '2-digit',
								minute: '2-digit'
							})}
						</text>
						<text x={tx} y={PAD_TOP + 27} text-anchor="middle" fill="var(--chart-tooltip-text)" font-size="10">
							{$t('chart.timeline.article_count')}: {pt.article_count} · {$t('chart.timeline.source_count')}: {pt.source_count}
						</text>
					</g>
				{/if}
			</svg>
		</div>
	{/if}
</div>
