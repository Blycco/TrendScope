<script lang="ts">
	/**
	 * SentimentChart — SVG donut chart showing positive/neutral/negative distribution.
	 */
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { apiRequest } from '$lib/api';
	import type { SentimentDistribution } from '$lib/api';

	interface Props {
		groupId: string;
	}

	let { groupId }: Props = $props();

	let data = $state<SentimentDistribution | null>(null);
	let isLoading = $state(true);

	const SIZE = 160;
	const CENTER = SIZE / 2;
	const OUTER_R = 64;
	const INNER_R = 40;

	interface Segment {
		label: string;
		count: number;
		color: string;
		i18nKey: string;
	}

	const segments = $derived<Segment[]>(
		data && data.total > 0
			? [
					{ label: 'positive', count: data.positive, color: '#22c55e', i18nKey: 'trend.sentiment.positive' },
					{ label: 'neutral', count: data.neutral, color: '#9ca3af', i18nKey: 'trend.sentiment.neutral' },
					{ label: 'negative', count: data.negative, color: '#ef4444', i18nKey: 'trend.sentiment.negative' }
				]
			: []
	);

	function describeArc(startAngle: number, endAngle: number, outerR: number, innerR: number): string {
		const startOuter = polarToCartesian(CENTER, CENTER, outerR, endAngle);
		const endOuter = polarToCartesian(CENTER, CENTER, outerR, startAngle);
		const startInner = polarToCartesian(CENTER, CENTER, innerR, startAngle);
		const endInner = polarToCartesian(CENTER, CENTER, innerR, endAngle);
		const largeArc = endAngle - startAngle > 180 ? 1 : 0;

		return [
			`M ${startOuter.x} ${startOuter.y}`,
			`A ${outerR} ${outerR} 0 ${largeArc} 0 ${endOuter.x} ${endOuter.y}`,
			`L ${startInner.x} ${startInner.y}`,
			`A ${innerR} ${innerR} 0 ${largeArc} 1 ${endInner.x} ${endInner.y}`,
			'Z'
		].join(' ');
	}

	function polarToCartesian(cx: number, cy: number, r: number, angleDeg: number): { x: number; y: number } {
		const rad = ((angleDeg - 90) * Math.PI) / 180;
		return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
	}

	const arcs = $derived(() => {
		if (!data || data.total === 0) return [];
		let currentAngle = 0;
		return segments
			.filter((s) => s.count > 0)
			.map((s) => {
				const sweep = (s.count / data!.total) * 360;
				const start = currentAngle;
				const end = currentAngle + sweep;
				currentAngle = end;
				return { ...s, path: describeArc(start, end, OUTER_R, INNER_R) };
			});
	});

	onMount(async () => {
		try {
			data = await apiRequest<SentimentDistribution>(`/trends/${groupId}/sentiment`);
		} catch {
			data = null;
		} finally {
			isLoading = false;
		}
	});
</script>

<div class="rounded-lg border border-gray-200 bg-white p-4">
	<h3 class="text-sm font-semibold text-gray-700 mb-3">{$t('trend.sentiment')}</h3>

	{#if isLoading}
		<div class="flex items-center justify-center" style="height: {SIZE}px">
			<p class="text-sm text-gray-400">{$t('status.loading')}</p>
		</div>
	{:else if !data || data.total === 0}
		<div class="flex items-center justify-center" style="height: {SIZE}px">
			<p class="text-sm text-gray-400">{$t('trend.sentiment.no_data')}</p>
		</div>
	{:else}
		<div class="flex items-center gap-6">
			<svg
				viewBox="0 0 {SIZE} {SIZE}"
				width={SIZE}
				height={SIZE}
				role="img"
				aria-label={$t('trend.sentiment')}
			>
				{#each arcs() as arc}
					<path d={arc.path} fill={arc.color} />
				{/each}
				<!-- Center text -->
				<text
					x={CENTER}
					y={CENTER - 6}
					text-anchor="middle"
					dominant-baseline="middle"
					font-size="20"
					font-weight="600"
					fill="#1f2937"
				>
					{data.total}
				</text>
				<text
					x={CENTER}
					y={CENTER + 12}
					text-anchor="middle"
					dominant-baseline="middle"
					font-size="10"
					fill="#6b7280"
				>
					{$t('trend.article_count', { values: { count: data.total } })}
				</text>
			</svg>

			<div class="flex flex-col gap-2">
				{#each segments as seg}
					<div class="flex items-center gap-2 text-sm">
						<span
							class="inline-block h-3 w-3 rounded-full"
							style="background-color: {seg.color}"
						></span>
						<span class="text-gray-600">{$t(seg.i18nKey)}</span>
						<span class="font-medium text-gray-900">{seg.count}</span>
						<span class="text-gray-400">
							({data.total > 0 ? Math.round((seg.count / data.total) * 100) : 0}%)
						</span>
					</div>
				{/each}
			</div>
		</div>
	{/if}
</div>
