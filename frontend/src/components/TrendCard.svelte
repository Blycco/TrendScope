<script lang="ts">
	import { t } from 'svelte-i18n';
	import { goto } from '$app/navigation';
	import type { TrendItem } from '$lib/api';
	import EarlyBadge from './EarlyBadge.svelte';
	import DirectionBadge from './DirectionBadge.svelte';
	import { compareStore } from '$lib/stores/compare.svelte';
	import { BarChart3 } from 'lucide-svelte';

	interface Props {
		trend: TrendItem;
	}

	let { trend }: Props = $props();

	// Use burst_score if available, fallback to score-based heuristic
	const burstScore = $derived(trend.burst_score ?? trend.score / 100);

	const burstLabel = $derived(
		burstScore > 0.7 ? $t('trend.burst.high') :
		burstScore > 0.4 ? $t('trend.burst.mid') :
		$t('trend.burst.low')
	);

	const burstCardBg = $derived(
		burstScore > 0.7
			? 'bg-red-50 dark:bg-red-950/20 border-red-200 dark:border-red-800'
			: 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700'
	);

	const burstBadgeClass = $derived(
		burstScore > 0.7
			? 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-400'
			: burstScore > 0.4
				? 'bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-400'
				: 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
	);

	function handleCompare(e: MouseEvent): void {
		e.preventDefault();
		e.stopPropagation();
		compareStore.addTrend(trend.id);
		goto(`/compare?ids=${compareStore.toUrlParam()}`);
	}
</script>

<a
	href="/trends/{trend.id}"
	class="block rounded-lg border p-4 hover:shadow-md transition-shadow {burstCardBg}"
>
	<!-- Header row: badges -->
	<div class="flex items-center gap-2 flex-wrap mb-2">
		<span class="inline-flex items-center rounded-full bg-blue-50 dark:bg-blue-900/20 px-2 py-0.5 text-xs font-medium text-blue-700 dark:text-blue-400">
			{trend.category}
		</span>
		<EarlyBadge score={trend.early_trend_score} />
		<DirectionBadge direction={trend.direction} />
		<span class="text-xs font-medium px-2 py-0.5 rounded-full {burstBadgeClass}">
			{burstLabel}
		</span>
		<div class="ml-auto flex items-center gap-1.5">
			<button
				type="button"
				class="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-blue-600 transition-colors"
				title={$t('compare.add')}
				onclick={handleCompare}
			>
				<BarChart3 size={14} />
			</button>
			<span class="text-sm font-bold text-gray-700 dark:text-gray-300">
				{trend.score.toFixed(1)}
			</span>
		</div>
	</div>

	<!-- Title -->
	<h3 class="text-base font-bold text-gray-900 dark:text-gray-100 line-clamp-2 leading-snug">
		{trend.title}
	</h3>

	<!-- Summary -->
	{#if trend.summary}
		<p class="mt-1.5 text-sm text-gray-500 dark:text-gray-400 line-clamp-2">
			{trend.summary}
		</p>
	{/if}

	<!-- Keyword hashtags -->
	{#if trend.keywords.length > 0}
		<div class="mt-2 flex flex-wrap gap-1">
			{#each trend.keywords.slice(0, 3) as kw}
				<span class="bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 rounded-full px-2 py-0.5 text-xs">
					#{kw}
				</span>
			{/each}
		</div>
	{/if}

	<!-- Footer: article count + date -->
	<div class="mt-3 flex items-center gap-3 text-xs text-gray-400 dark:text-gray-500">
		{#if trend.article_count > 0}
			<span>{$t('trend.articles', { values: { count: trend.article_count } })}</span>
		{/if}
		<span class="ml-auto">{new Date(trend.created_at).toLocaleDateString()}</span>
	</div>
</a>
