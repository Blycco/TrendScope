<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { apiRequest } from '$lib/api';
	import type { MetaTrendListResponse, MetaTrendItem } from '$lib/api';
	import { ChevronDown, ChevronUp } from 'lucide-svelte';

	let { locale }: { locale?: string } = $props();

	let data = $state<MetaTrendListResponse | null>(null);
	let isLoading = $state(true);
	let expanded = $state(false);

	onMount(async () => {
		try {
			const params = new URLSearchParams();
			if (locale) params.set('locale', locale);
			const qs = params.toString();
			data = await apiRequest<MetaTrendListResponse>(
				`/trends/meta${qs ? `?${qs}` : ''}`
			);
		} catch {
			// silent fail
		} finally {
			isLoading = false;
		}
	});
</script>

{#if !isLoading && data && data.items.length > 0}
	<div class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
		<button
			class="flex w-full items-center justify-between px-4 py-3 text-left"
			onclick={() => (expanded = !expanded)}
			aria-expanded={expanded}
		>
			<div>
				<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300">
					{$t('meta_trends.title')}
				</h3>
				<p class="text-xs text-gray-500 dark:text-gray-400">
					{$t('meta_trends.subtitle')}
				</p>
			</div>
			{#if expanded}
				<ChevronUp size={16} class="text-gray-400 shrink-0" />
			{:else}
				<ChevronDown size={16} class="text-gray-400 shrink-0" />
			{/if}
		</button>

		{#if expanded}
			<div class="border-t border-gray-100 dark:border-gray-700 divide-y divide-gray-100 dark:divide-gray-700">
				{#each data.items as item (item.meta_title)}
					<div class="px-4 py-3">
						<p class="text-sm font-medium text-gray-800 dark:text-gray-200">
							{item.meta_title}
						</p>
						<p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
							{$t('meta_trends.sub_trends', { values: { count: item.sub_trend_ids.length } })}
						</p>
						<div class="mt-1.5 flex flex-wrap gap-1">
							{#each item.keywords.slice(0, 6) as kw}
								<span
									class="inline-flex rounded bg-blue-50 dark:bg-blue-900/30 px-1.5 py-0.5 text-xs text-blue-700 dark:text-blue-300"
								>
									{kw}
								</span>
							{/each}
						</div>
					</div>
				{/each}
			</div>
		{/if}
	</div>
{:else if !isLoading && data && data.items.length === 0}
	<p class="text-sm text-gray-500 dark:text-gray-400">
		{$t('meta_trends.empty')}
	</p>
{/if}
