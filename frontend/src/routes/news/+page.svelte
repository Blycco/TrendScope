<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { apiRequest, ApiRequestError, QuotaExceededRequestError } from '$lib/api';
	import type { NewsListResponse, NewsItem } from '$lib/api';
	import NewsCard from '../../components/NewsCard.svelte';
	import SkeletonCard from '../../components/SkeletonCard.svelte';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';
	import QuotaExceededModal from '$lib/ui/QuotaExceededModal.svelte';

	const ALL_CATEGORIES = ['tech', 'economy', 'entertainment', 'lifestyle', 'politics', 'sports', 'society'] as const;
	const SOURCE_TYPES = ['news', 'community', 'sns'] as const;
	const TIME_OPTIONS = [
		{ label: 'filter.time.1h', value: 1 },
		{ label: 'filter.time.6h', value: 6 },
		{ label: 'filter.time.24h', value: 24 },
		{ label: 'filter.time.7d', value: 168 },
		{ label: 'filter.time.30d', value: 720 },
	] as const;

	let news = $state<NewsItem[]>([]);
	let nextCursor = $state<string | null>(null);
	let isLoading = $state(true);
	let isLoadingMore = $state(false);

	let selectedCategory = $state<string | null>(null);
	let selectedSourceType = $state<string | null>(null);
	let selectedTime = $state<number | null>(null);
	let selectedLocale = $state<string | null>(null);

	let errorOpen = $state(false);
	let errorCode = $state('');
	let errorMessageKey = $state('');

	let quotaOpen = $state(false);
	let quotaFeature = $state('');
	let quotaLimit = $state(0);
	let quotaResetTime = $state('');

	async function loadNews(cursor?: string): Promise<void> {
		try {
			const params = new URLSearchParams({ limit: '20' });
			if (cursor) params.set('cursor', cursor);
			if (selectedCategory) params.set('category', selectedCategory);
			if (selectedSourceType) params.set('source_type', selectedSourceType);
			if (selectedTime) params.set('since', String(selectedTime));
			if (selectedLocale) params.set('locale', selectedLocale);

			const data = await apiRequest<NewsListResponse>(`/news?${params.toString()}`);
			if (cursor) {
				news = [...news, ...data.items];
			} else {
				news = data.items;
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

	function applyFilter(type: 'category' | 'source' | 'time' | 'locale', value: string | number | null): void {
		if (type === 'category') selectedCategory = value as string | null;
		else if (type === 'source') selectedSourceType = value as string | null;
		else if (type === 'time') selectedTime = value as number | null;
		else if (type === 'locale') selectedLocale = value as string | null;
		news = [];
		nextCursor = null;
		loadNews();
	}

	async function loadMore(): Promise<void> {
		if (!nextCursor || isLoadingMore) return;
		isLoadingMore = true;
		await loadNews(nextCursor);
		isLoadingMore = false;
	}

	onMount(async () => {
		await loadNews();
		isLoading = false;
	});
</script>

<div class="space-y-3 sm:space-y-4">
	<h1 class="text-xl sm:text-2xl font-bold text-gray-900">{$t('page.news.title')}</h1>

	<!-- Filters -->
	<div class="space-y-2 sm:space-y-3">
		<!-- Locale filter -->
		<div class="flex gap-1.5 sm:gap-2 flex-wrap">
			<button
				onclick={() => applyFilter('locale', null)}
				class="rounded-full px-2.5 py-1 sm:px-3 text-xs font-medium transition-colors {selectedLocale === null ? 'bg-indigo-600 text-white' : 'border border-gray-200 bg-white text-gray-600 hover:bg-gray-50'}"
			>{$t('filter.all')}</button>
			<button
				onclick={() => applyFilter('locale', 'ko')}
				class="rounded-full px-2.5 py-1 sm:px-3 text-xs font-medium transition-colors {selectedLocale === 'ko' ? 'bg-indigo-600 text-white' : 'border border-gray-200 bg-white text-gray-600 hover:bg-gray-50'}"
			>{$t('filter.locale.domestic')}</button>
			<button
				onclick={() => applyFilter('locale', 'en')}
				class="rounded-full px-2.5 py-1 sm:px-3 text-xs font-medium transition-colors {selectedLocale === 'en' ? 'bg-indigo-600 text-white' : 'border border-gray-200 bg-white text-gray-600 hover:bg-gray-50'}"
			>{$t('filter.locale.international')}</button>
		</div>

		<!-- Category filter -->
		<div class="flex gap-1.5 sm:gap-2 flex-wrap">
			<button
				onclick={() => applyFilter('category', null)}
				class="rounded-full px-2.5 py-1 sm:px-3 text-xs font-medium transition-colors {selectedCategory === null ? 'bg-blue-600 text-white' : 'border border-gray-200 bg-white text-gray-600 hover:bg-gray-50'}"
			>{$t('filter.all')}</button>
			{#each ALL_CATEGORIES as cat}
				<button
					onclick={() => applyFilter('category', cat)}
					class="rounded-full px-2.5 py-1 sm:px-3 text-xs font-medium transition-colors {selectedCategory === cat ? 'bg-blue-600 text-white' : 'border border-gray-200 bg-white text-gray-600 hover:bg-gray-50'}"
				>{$t(`filter.category.${cat}`)}</button>
			{/each}
		</div>

		<!-- Source type + Time filters -->
		<div class="flex gap-2 sm:gap-4 flex-wrap">
			<div class="flex gap-1.5 sm:gap-2 flex-wrap">
				<button
					onclick={() => applyFilter('source', null)}
					class="rounded-full px-2.5 py-1 sm:px-3 text-xs font-medium transition-colors {selectedSourceType === null ? 'bg-green-600 text-white' : 'border border-gray-200 bg-white text-gray-600 hover:bg-gray-50'}"
				>{$t('filter.all')}</button>
				{#each SOURCE_TYPES as src}
					<button
						onclick={() => applyFilter('source', src)}
						class="rounded-full px-2.5 py-1 sm:px-3 text-xs font-medium transition-colors {selectedSourceType === src ? 'bg-green-600 text-white' : 'border border-gray-200 bg-white text-gray-600 hover:bg-gray-50'}"
					>{$t(`filter.source.${src}`)}</button>
				{/each}
			</div>

			<div class="flex gap-1.5 sm:gap-2 flex-wrap">
				<button
					onclick={() => applyFilter('time', null)}
					class="rounded-full px-2.5 py-1 text-xs font-medium transition-colors {selectedTime === null ? 'bg-gray-800 text-white' : 'border border-gray-200 bg-white text-gray-500 hover:bg-gray-50'}"
				>{$t('filter.all')}</button>
				{#each TIME_OPTIONS as opt}
					<button
						onclick={() => applyFilter('time', opt.value)}
						class="rounded-full px-2.5 py-1 text-xs font-medium transition-colors {selectedTime === opt.value ? 'bg-gray-800 text-white' : 'border border-gray-200 bg-white text-gray-500 hover:bg-gray-50'}"
					>{$t(opt.label)}</button>
				{/each}
			</div>
		</div>
	</div>

	{#if isLoading}
		<div class="space-y-3">
			{#each Array(5) as _}
				<SkeletonCard />
			{/each}
		</div>
	{:else if news.length === 0}
		<p class="text-gray-500">{$t('status.no_results')}</p>
	{:else}
		<div class="space-y-3">
			{#each news as item (item.id)}
				<NewsCard news={item} />
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

<ErrorModal open={errorOpen} errorCode={errorCode} messageKey={errorMessageKey} onClose={() => (errorOpen = false)} onRetry={() => { errorOpen = false; loadNews(); }} />
<QuotaExceededModal open={quotaOpen} feature={quotaFeature} limit={quotaLimit} resetTime={quotaResetTime} onClose={() => (quotaOpen = false)} />
