<script lang="ts">
	import type { TrendItem } from '$lib/api';
	import EarlyBadge from '../../components/EarlyBadge.svelte';
	import DirectionBadge from '../../components/DirectionBadge.svelte';

	interface Props {
		trends: TrendItem[];
	}

	let { trends }: Props = $props();

	const top = $derived(trends[0]);
	const rest = $derived(trends.slice(1, 5));

	function burstLabel(t: TrendItem): string {
		const b = t.burst_score ?? t.score / 100;
		return b > 0.7 ? '🔥' : b > 0.4 ? '📈' : '➡️';
	}

	function cardBg(t: TrendItem): string {
		const b = t.burst_score ?? t.score / 100;
		return b > 0.7
			? 'border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/20'
			: 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800';
	}
</script>

<!-- Mobile: simple list -->
<div class="md:hidden space-y-3">
	{#each trends.slice(0, 5) as trend (trend.id)}
		<a
			href="/trends/{trend.id}"
			class="block rounded-lg border p-4 hover:shadow-md transition-shadow {cardBg(trend)}"
		>
			<div class="flex items-center gap-2 mb-1">
				<span class="text-xs font-medium text-blue-600 dark:text-blue-400">{trend.category}</span>
				<EarlyBadge score={trend.early_trend_score} />
				<span class="ml-auto text-base">{burstLabel(trend)}</span>
			</div>
			<h3 class="text-sm font-bold text-gray-900 dark:text-gray-100 line-clamp-2">{trend.title}</h3>
		</a>
	{/each}
</div>

<!-- Desktop: Bento Grid -->
<div class="hidden md:grid md:grid-cols-3 lg:grid-cols-5 gap-3 auto-rows-fr">
	<!-- 1위: 대형 -->
	{#if top}
		<a
			href="/trends/{top.id}"
			class="md:col-span-2 md:row-span-2 rounded-xl border p-5 hover:shadow-lg transition-shadow flex flex-col {cardBg(top)}"
		>
			<div class="flex items-center gap-2 flex-wrap mb-3">
				<span class="inline-flex items-center rounded-full bg-blue-50 dark:bg-blue-900/20 px-2 py-0.5 text-xs font-medium text-blue-700 dark:text-blue-400">
					{top.category}
				</span>
				<EarlyBadge score={top.early_trend_score} />
				<DirectionBadge direction={top.direction} />
				{#if (top.burst_score ?? top.score / 100) > 0.7}
					<span class="text-xs font-bold text-red-600 dark:text-red-400 bg-red-100 dark:bg-red-900/30 px-2 py-0.5 rounded-full">
						🔥 폭발적
					</span>
				{/if}
			</div>
			<h3 class="text-lg font-bold text-gray-900 dark:text-gray-100 line-clamp-3 flex-1">
				{top.title}
			</h3>
			{#if top.summary}
				<p class="mt-2 text-sm text-gray-500 dark:text-gray-400 line-clamp-3">{top.summary}</p>
			{/if}
			<div class="mt-3 flex items-center gap-3 text-xs text-gray-400 dark:text-gray-500">
				<span>{top.article_count}건</span>
				<span class="text-sm font-semibold text-gray-700 dark:text-gray-300 ml-auto">{top.score.toFixed(1)}점</span>
			</div>
		</a>
	{/if}

	<!-- 2~5위: 소형 -->
	{#each rest as trend (trend.id)}
		<a
			href="/trends/{trend.id}"
			class="rounded-xl border p-3 hover:shadow-md transition-shadow flex flex-col {cardBg(trend)}"
		>
			<div class="flex items-center gap-1 mb-2">
				<span class="text-xs text-gray-500 dark:text-gray-400 truncate flex-1">{trend.category}</span>
				<span class="text-sm">{burstLabel(trend)}</span>
			</div>
			<h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 line-clamp-2 flex-1">
				{trend.title}
			</h3>
			<div class="mt-2 flex items-center gap-1">
				<DirectionBadge direction={trend.direction} />
				<span class="ml-auto text-xs font-bold text-gray-600 dark:text-gray-400">{trend.score.toFixed(1)}</span>
			</div>
		</a>
	{/each}
</div>
