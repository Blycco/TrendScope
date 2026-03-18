<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { apiRequest, ApiRequestError, QuotaExceededRequestError } from '$lib/api';
	import type { TrendListResponse, TrendItem } from '$lib/api';
	import TrendCard from '../../components/TrendCard.svelte';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';
	import QuotaExceededModal from '$lib/ui/QuotaExceededModal.svelte';

	let trends = $state<TrendItem[]>([]);
	let nextCursor = $state<string | null>(null);
	let isLoading = $state(true);
	let isLoadingMore = $state(false);

	let errorOpen = $state(false);
	let errorCode = $state('');
	let errorMessageKey = $state('');

	let quotaOpen = $state(false);
	let quotaFeature = $state('');
	let quotaLimit = $state(0);
	let quotaResetTime = $state('');

	async function loadTrends(cursor?: string): Promise<void> {
		try {
			const params = new URLSearchParams({ limit: '20' });
			if (cursor) params.set('cursor', cursor);

			const data = await apiRequest<TrendListResponse>(`/trends?${params.toString()}`);
			if (cursor) {
				trends = [...trends, ...data.items];
			} else {
				trends = data.items;
			}
			nextCursor = data.next_cursor;
		} catch (error) {
			if (error instanceof QuotaExceededRequestError) {
				quotaFeature = error.quotaType;
				quotaLimit = error.limit;
				quotaResetTime = error.resetAt;
				quotaOpen = true;
			} else if (error instanceof ApiRequestError) {
				errorCode = error.errorCode;
				errorMessageKey = 'error.server';
				errorOpen = true;
			} else {
				errorCode = 'ERR_NETWORK';
				errorMessageKey = 'error.network';
				errorOpen = true;
			}
		}
	}

	async function loadMore(): Promise<void> {
		if (!nextCursor || isLoadingMore) return;
		isLoadingMore = true;
		await loadTrends(nextCursor);
		isLoadingMore = false;
	}

	onMount(async () => {
		await loadTrends();
		isLoading = false;
	});
</script>

<div class="space-y-6">
	<h1 class="text-2xl font-bold text-gray-900">{$t('page.trends.title')}</h1>

	{#if isLoading}
		<p class="text-gray-500">{$t('status.loading')}</p>
	{:else if trends.length === 0}
		<p class="text-gray-500">{$t('status.no_results')}</p>
	{:else}
		<div class="space-y-3">
			{#each trends as trend (trend.id)}
				<TrendCard {trend} />
			{/each}
		</div>

		{#if nextCursor}
			<div class="flex justify-center pt-4">
				<button
					onclick={loadMore}
					disabled={isLoadingMore}
					class="rounded-md border border-gray-300 px-6 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
				>
					{#if isLoadingMore}
						{$t('status.loading')}
					{:else}
						{$t('button.load_more')}
					{/if}
				</button>
			</div>
		{/if}
	{/if}
</div>

<ErrorModal open={errorOpen} errorCode={errorCode} messageKey={errorMessageKey} onClose={() => (errorOpen = false)} onRetry={() => { errorOpen = false; loadTrends(); }} />
<QuotaExceededModal open={quotaOpen} feature={quotaFeature} limit={quotaLimit} resetTime={quotaResetTime} onClose={() => (quotaOpen = false)} />
