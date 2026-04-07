<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { apiRequest, ApiRequestError, QuotaExceededRequestError } from '$lib/api';
	import type { NewsListResponse, NewsItem } from '$lib/api';
	import NewsCard from '../../components/NewsCard.svelte';
	import SkeletonCard from '../../components/SkeletonCard.svelte';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';
	import QuotaExceededModal from '$lib/ui/QuotaExceededModal.svelte';
	import FilterButton from '$lib/ui/FilterButton.svelte';
	import PageStateWrapper from '$lib/ui/PageStateWrapper.svelte';
	import LoadMoreButton from '$lib/ui/LoadMoreButton.svelte';

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
			<FilterButton
				label={$t('filter.all')}
				active={selectedLocale === null}
				onclick={() => applyFilter('locale', null)}
			/>
			<FilterButton
				label={$t('filter.locale.domestic')}
				active={selectedLocale === 'ko'}
				onclick={() => applyFilter('locale', 'ko')}
			/>
			<FilterButton
				label={$t('filter.locale.international')}
				active={selectedLocale === 'en'}
				onclick={() => applyFilter('locale', 'en')}
			/>
		</div>

		<!-- Category filter -->
		<div class="flex gap-1.5 sm:gap-2 flex-wrap">
			<FilterButton
				label={$t('filter.all')}
				active={selectedCategory === null}
				activeClass="bg-blue-600 text-white"
				onclick={() => applyFilter('category', null)}
			/>
			{#each ALL_CATEGORIES as cat}
				<FilterButton
					label={$t(`filter.category.${cat}`)}
					active={selectedCategory === cat}
					activeClass="bg-blue-600 text-white"
					onclick={() => applyFilter('category', cat)}
				/>
			{/each}
		</div>

		<!-- Source type + Time filters -->
		<div class="flex gap-2 sm:gap-4 flex-wrap">
			<div class="flex gap-1.5 sm:gap-2 flex-wrap">
				<FilterButton
					label={$t('filter.all')}
					active={selectedSourceType === null}
					activeClass="bg-green-600 text-white"
					onclick={() => applyFilter('source', null)}
				/>
				{#each SOURCE_TYPES as src}
					<FilterButton
						label={$t(`filter.source.${src}`)}
						active={selectedSourceType === src}
						activeClass="bg-green-600 text-white"
						onclick={() => applyFilter('source', src)}
					/>
				{/each}
			</div>

			<div class="flex gap-1.5 sm:gap-2 flex-wrap">
				<FilterButton
					label={$t('filter.all')}
					active={selectedTime === null}
					activeClass="bg-gray-800 text-white"
					onclick={() => applyFilter('time', null)}
				/>
				{#each TIME_OPTIONS as opt}
					<FilterButton
						label={$t(opt.label)}
						active={selectedTime === opt.value}
						activeClass="bg-gray-800 text-white"
						onclick={() => applyFilter('time', opt.value)}
					/>
				{/each}
			</div>
		</div>
	</div>

	<PageStateWrapper {isLoading} isEmpty={news.length === 0 && !isLoading}>
		{#snippet loading()}
			<div class="space-y-3">
				{#each Array(5) as _}
					<SkeletonCard />
				{/each}
			</div>
		{/snippet}

		{#snippet children()}
			<div class="space-y-3">
				{#each news as item (item.id)}
					<NewsCard news={item} />
				{/each}
			</div>

			<LoadMoreButton hasMore={nextCursor !== null} isLoading={isLoadingMore} onclick={loadMore} />
		{/snippet}
	</PageStateWrapper>
</div>

<ErrorModal open={errorOpen} errorCode={errorCode} messageKey={errorMessageKey} onClose={() => (errorOpen = false)} onRetry={() => { errorOpen = false; loadNews(); }} />
<QuotaExceededModal open={quotaOpen} feature={quotaFeature} limit={quotaLimit} resetTime={quotaResetTime} onClose={() => (quotaOpen = false)} />
