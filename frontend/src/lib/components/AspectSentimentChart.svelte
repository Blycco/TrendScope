<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { apiRequest } from '$lib/api';
	import type { AspectSentimentResponse } from '$lib/api';

	let { groupId }: { groupId: string } = $props();

	let data = $state<AspectSentimentResponse | null>(null);
	let isLoading = $state(true);

	onMount(async () => {
		try {
			data = await apiRequest<AspectSentimentResponse>(
				`/trends/${groupId}/sentiment/aspects`
			);
		} catch {
			// silent fail — component simply stays hidden
		} finally {
			isLoading = false;
		}
	});
</script>

{#if !isLoading && data && data.aspects.length > 0}
	<div class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4">
		<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
			{$t('trend.sentiment.aspects.title')}
		</h3>
		<div class="space-y-2">
			{#each data.aspects as item}
				{@const maxTotal = Math.max(...data.aspects.map((a) => a.total))}
				{@const barWidth = maxTotal > 0 ? (item.total / maxTotal) * 100 : 0}
				{@const posW = item.total > 0 ? (item.positive / item.total) * barWidth : 0}
				{@const neuW = item.total > 0 ? (item.neutral / item.total) * barWidth : 0}
				{@const negW = item.total > 0 ? (item.negative / item.total) * barWidth : 0}
				<div class="flex items-center gap-2">
					<span class="w-20 text-xs text-gray-600 dark:text-gray-400 truncate shrink-0">
						{item.aspect}
					</span>
					<div
						class="flex-1 h-5 bg-gray-100 dark:bg-gray-700 rounded overflow-hidden relative"
						role="img"
						aria-label="{item.aspect}: {$t('trend.sentiment.aspects.total', { values: { count: item.total } })}"
					>
						<div class="absolute left-0 top-0 h-full flex">
							<div style="width:{posW}%" class="bg-green-400"></div>
							<div style="width:{neuW}%" class="bg-gray-400"></div>
							<div style="width:{negW}%" class="bg-red-400"></div>
						</div>
					</div>
					<span class="text-xs text-gray-400 w-6 text-right shrink-0">{item.total}</span>
				</div>
			{/each}
		</div>
	</div>
{:else if !isLoading && data && data.aspects.length === 0}
	<p class="text-sm text-gray-500 dark:text-gray-400">
		{$t('trend.sentiment.aspects.empty')}
	</p>
{/if}
