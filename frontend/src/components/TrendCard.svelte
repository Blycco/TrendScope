<script lang="ts">
	import { t } from 'svelte-i18n';
	import type { TrendItem } from '$lib/api';
	import EarlyBadge from './EarlyBadge.svelte';
	import DirectionBadge from './DirectionBadge.svelte';
	import StatusBadge from '$lib/ui/StatusBadge.svelte';
	import { formatDate } from '$lib/utils/locale';

	interface Props {
		trend: TrendItem;
	}

	let { trend }: Props = $props();

	const formattedDate = $derived(
		formatDate(trend.created_at, { year: 'numeric', month: 'short', day: 'numeric' })
	);

	const keywordTitle = $derived(trend.keywords.length > 0 ? trend.keywords.join(' · ') : trend.title);

	const scoreColor = $derived(
		trend.score >= 80
			? 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400'
			: trend.score >= 50
				? 'bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-400'
				: trend.score >= 20
					? 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400'
					: 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
	);
</script>

<a
	href="/trends/{trend.id}"
	class="block rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 hover:shadow-md transition-shadow"
>
	<div class="flex items-start justify-between gap-3">
		<div class="flex-1 min-w-0">
			<div class="flex items-center gap-2 flex-wrap">
				<h3 class="text-base font-bold text-gray-900 dark:text-gray-100 leading-snug">
					{keywordTitle}
				</h3>
				<EarlyBadge score={trend.early_trend_score} />
				<DirectionBadge direction={trend.direction} />
				<StatusBadge status={trend.status} />
			</div>

			{#if trend.keywords.length > 0 && trend.title !== keywordTitle}
				<p class="mt-1 text-sm text-gray-500 dark:text-gray-400 truncate">{trend.title}</p>
			{/if}
		</div>

		<span class="shrink-0 inline-flex items-center rounded-full px-2.5 py-1 text-sm font-semibold {scoreColor}">
			{trend.score.toFixed(1)}
		</span>
	</div>

	<div class="mt-3 flex items-center gap-3 text-xs text-gray-500 dark:text-gray-400">
		<span class="inline-flex items-center gap-1 rounded bg-blue-50 dark:bg-blue-900/20 px-2 py-0.5 text-blue-700 dark:text-blue-400">
			{trend.category}
		</span>
		{#if trend.article_count > 0}
			<span>{$t('trend.article_count', { values: { count: trend.article_count } })}</span>
		{/if}
		<span class="ml-auto">{formattedDate}</span>
	</div>
</a>
