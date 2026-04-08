<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { apiRequest, ApiRequestError, QuotaExceededRequestError } from '$lib/api';
	import type { NewsListResponse, NewsItem } from '$lib/api';
	import { createPaginationStore } from '$lib/stores/pagination.svelte';
	import { createFilterStore } from '$lib/stores/filters.svelte';
	import { createCacheStore } from '$lib/stores/cache.svelte';
	import type { FetchFn } from '$lib/stores/pagination.svelte';
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

	const pagination = createPaginationStore<NewsItem>();
	const filters = createFilterStore({
		category: null as string | null,
		source_type: null as string | null,
		since: null as number | null,
		locale: null as string | null,
	});
	const cache = createCacheStore<NewsListResponse>(5 * 60 * 1000);

	let errorOpen = $state(false);
	let errorCode = $state('');
	let errorMessageKey = $state('');

	let quotaOpen = $state(false);
	let quotaFeature = $state('');
	let quotaLimit = $state(0);
	let quotaResetTime = $state('');

	function buildCacheKey(cursor?: string): string {
		return JSON.stringify({
			cursor,
			category: filters.values.category,
			source_type: filters.values.source_type,
			since: filters.values.since,
			locale: filters.values.locale,
		});
	}

	const fetchNews: FetchFn<NewsItem> = async (cursor?: string) => {
		const cacheKey = buildCacheKey(cursor);
		const cached = cache.get(cacheKey);
		if (cached) return cached;

		const params = new URLSearchParams({ limit: '20' });
		if (cursor) params.set('cursor', cursor);
		if (filters.values.category) params.set('category', filters.values.category);
		if (filters.values.source_type) params.set('source_type', filters.values.source_type);
		if (filters.values.since) params.set('since', String(filters.values.since));
		if (filters.values.locale) params.set('locale', filters.values.locale);

		const data = await apiRequest<NewsListResponse>(`/news?${params.toString()}`);
		cache.set(cacheKey, data);
		return data;
	};

	function handleError(error: unknown): void {
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

	async function loadNews(): Promise<void> {
		try {
			await pagination.load(fetchNews);
		} catch (error) {
			handleError(error);
		}
	}

	function applyFilter(type: 'category' | 'source_type' | 'since' | 'locale', value: string | number | null): void {
		filters.set(type, value);
		pagination.reset();
		cache.clear();
		loadNews();
	}

	async function loadMore(): Promise<void> {
		try {
			await pagination.loadMore(fetchNews);
		} catch (error) {
			handleError(error);
		}
	}

	onMount(async () => {
		await loadNews();
	});
</script>

<div class="space-y-3 sm:space-y-4">
	<h1 class="text-xl sm:text-2xl font-bold text-gray-900 dark:text-gray-100">{$t('page.news.title')}</h1>

	<!-- Filters -->
	<div class="space-y-2 sm:space-y-3">
		<!-- Locale filter -->
		<div class="flex gap-1.5 sm:gap-2 flex-wrap">
			<FilterButton
				label={$t('filter.all')}
				active={filters.values.locale === null}
				onclick={() => applyFilter('locale', null)}
			/>
			<FilterButton
				label={$t('filter.locale.domestic')}
				active={filters.values.locale === 'ko'}
				onclick={() => applyFilter('locale', 'ko')}
			/>
			<FilterButton
				label={$t('filter.locale.international')}
				active={filters.values.locale === 'en'}
				onclick={() => applyFilter('locale', 'en')}
			/>
		</div>

		<!-- Category filter -->
		<div class="flex gap-1.5 sm:gap-2 flex-wrap">
			<FilterButton
				label={$t('filter.all')}
				active={filters.values.category === null}
				activeClass="bg-blue-600 text-white"
				onclick={() => applyFilter('category', null)}
			/>
			{#each ALL_CATEGORIES as cat}
				<FilterButton
					label={$t(`filter.category.${cat}`)}
					active={filters.values.category === cat}
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
					active={filters.values.source_type === null}
					activeClass="bg-green-600 text-white"
					onclick={() => applyFilter('source_type', null)}
				/>
				{#each SOURCE_TYPES as src}
					<FilterButton
						label={$t(`filter.source.${src}`)}
						active={filters.values.source_type === src}
						activeClass="bg-green-600 text-white"
						onclick={() => applyFilter('source_type', src)}
					/>
				{/each}
			</div>

			<div class="flex gap-1.5 sm:gap-2 flex-wrap">
				<FilterButton
					label={$t('filter.all')}
					active={filters.values.since === null}
					activeClass="bg-gray-800 text-white"
					onclick={() => applyFilter('since', null)}
				/>
				{#each TIME_OPTIONS as opt}
					<FilterButton
						label={$t(opt.label)}
						active={filters.values.since === opt.value}
						activeClass="bg-gray-800 text-white"
						onclick={() => applyFilter('since', opt.value)}
					/>
				{/each}
			</div>
		</div>
	</div>

	<PageStateWrapper isLoading={pagination.isLoading} isEmpty={pagination.items.length === 0 && !pagination.isLoading}>
		{#snippet loading()}
			<div class="space-y-3">
				{#each Array(5) as _}
					<SkeletonCard />
				{/each}
			</div>
		{/snippet}

		{#snippet children()}
			<div class="space-y-3">
				{#each pagination.items as item (item.id)}
					<NewsCard news={item} />
				{/each}
			</div>

			<LoadMoreButton hasMore={pagination.hasMore} isLoading={pagination.isLoadingMore} onclick={loadMore} />
		{/snippet}
	</PageStateWrapper>
</div>

<ErrorModal open={errorOpen} errorCode={errorCode} messageKey={errorMessageKey} onClose={() => (errorOpen = false)} onRetry={() => { errorOpen = false; loadNews(); }} />
<QuotaExceededModal open={quotaOpen} feature={quotaFeature} limit={quotaLimit} resetTime={quotaResetTime} onClose={() => (quotaOpen = false)} />
