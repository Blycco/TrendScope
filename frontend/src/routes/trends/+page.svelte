<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { apiRequest, ApiRequestError, QuotaExceededRequestError } from '$lib/api';
	import type { TrendListResponse, TrendItem } from '$lib/api';
	import TrendCard from '../../components/TrendCard.svelte';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';
	import QuotaExceededModal from '$lib/ui/QuotaExceededModal.svelte';

	interface PersonalizationSettings {
		category_weights: { tech: number; finance: number; entertainment: number; lifestyle: number };
		locale_ratio: number;
	}

	const ALL_CATEGORIES = ['tech', 'finance', 'entertainment', 'lifestyle'] as const;
	type Category = (typeof ALL_CATEGORIES)[number];

	let trends = $state<TrendItem[]>([]);
	let nextCursor = $state<string | null>(null);
	let isLoading = $state(true);
	let isLoadingMore = $state(false);
	let personalization = $state<PersonalizationSettings | null>(null);

	let errorOpen = $state(false);
	let errorCode = $state('');
	let errorMessageKey = $state('');

	let quotaOpen = $state(false);
	let quotaFeature = $state('');
	let quotaLimit = $state(0);
	let quotaResetTime = $state('');

	function getLocaleParam(): string | null {
		if (!personalization) return null;
		if (personalization.locale_ratio < 0.3) return 'en';
		if (personalization.locale_ratio > 0.7) return 'ko';
		return null;
	}

	function getSortedCategories(): Category[] {
		if (!personalization) return [...ALL_CATEGORIES];
		return [...ALL_CATEGORIES].sort(
			(a, b) => personalization!.category_weights[b] - personalization!.category_weights[a]
		);
	}

	async function loadTrends(cursor?: string): Promise<void> {
		try {
			const params = new URLSearchParams({ limit: '20' });
			if (cursor) params.set('cursor', cursor);
			const locale = getLocaleParam();
			if (locale) params.set('locale', locale);

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
		try {
			personalization = await apiRequest<PersonalizationSettings>('/personalization');
		} catch {
			// Non-critical — proceed without personalization
		}
		await loadTrends();
		isLoading = false;
	});
</script>

<div class="space-y-6">
	<div class="flex items-center gap-3">
		<h1 class="text-2xl font-bold text-gray-900">{$t('page.trends.title')}</h1>
		{#if personalization}
			<span class="inline-flex items-center rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-medium text-blue-700">
				{$t('trends.personalized_badge')}
			</span>
		{/if}
	</div>

	{#if personalization}
		<div class="flex gap-2 flex-wrap">
			{#each getSortedCategories() as cat}
				<span class="rounded-full border border-gray-200 bg-white px-3 py-1 text-xs font-medium text-gray-600">
					{cat}
				</span>
			{/each}
		</div>
	{/if}

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
