<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { apiRequest, ApiRequestError, QuotaExceededRequestError, PlanGateRequestError } from '$lib/api';
	import type { TrendListResponse, TrendItem } from '$lib/api';
	import { createPaginationStore } from '$lib/stores/pagination.svelte';
	import { createFilterStore } from '$lib/stores/filters.svelte';
	import { createCacheStore } from '$lib/stores/cache.svelte';
	import { personalizationStore } from '$lib/stores/personalization.svelte';
	import type { FetchFn } from '$lib/stores/pagination.svelte';
	import TrendCard from '../../components/TrendCard.svelte';
	import SkeletonCard from '../../components/SkeletonCard.svelte';
	import TrendMap from '$lib/components/TrendMap.svelte';
	import MetaTrendsSection from '$lib/components/MetaTrendsSection.svelte';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';
	import QuotaExceededModal from '$lib/ui/QuotaExceededModal.svelte';
	import PlanGate from '$lib/ui/PlanGate.svelte';
	import FilterButton from '$lib/ui/FilterButton.svelte';
	import MultiSelect from '$lib/components/MultiSelect.svelte';
	import PageStateWrapper from '$lib/ui/PageStateWrapper.svelte';
	import LoadMoreButton from '$lib/ui/LoadMoreButton.svelte';
	import EmptyState from '$lib/ui/EmptyState.svelte';
	import { Download, Share2 } from 'lucide-svelte';

	interface PersonalizationSettings {
		category_weights: { tech: number; finance: number; entertainment: number; lifestyle: number };
		locale_ratio: number;
	}

	const ALL_CATEGORIES = ['tech', 'economy', 'entertainment', 'lifestyle', 'politics', 'sports', 'society'] as const;

	const TIME_OPTIONS = [
		{ label: 'filter.time.1h', value: 1 },
		{ label: 'filter.time.6h', value: 6 },
		{ label: 'filter.time.24h', value: 24 },
		{ label: 'filter.time.7d', value: 168 },
		{ label: 'filter.time.30d', value: 720 },
	] as const;

	const DIRECTION_OPTIONS = ['rising', 'growing', 'steady', 'declining'] as const;
	const SORT_OPTIONS = ['score', 'burst_score', 'article_count', 'created_at'] as const;

	const pagination = createPaginationStore<TrendItem>();
	const filters = createFilterStore({
		category: null as string | null,
		locale: null as string | null,
		since: null as number | null,
		direction: null as string | null,
		sort: 'score' as string,
	});
	const cache = createCacheStore<TrendListResponse>(5 * 60 * 1000);

	let personalization = $state<PersonalizationSettings | null>(null);

	let errorOpen = $state(false);
	let errorCode = $state('');
	let errorMessageKey = $state('');

	let quotaOpen = $state(false);
	let quotaFeature = $state('');
	let quotaLimit = $state(0);
	let quotaResetTime = $state('');

	let planGateOpen = $state(false);
	let planGateRequired = $state('pro');

	let isExportingCsv = $state(false);
	let isExportingPdf = $state(false);
	let isSharing = $state(false);

	const topTrendId = $derived(pagination.items.length > 0 ? pagination.items[0].id : null);

	// Multi-select helpers: comma-sep string ↔ string[]
	const selectedCategories = $derived(
		filters.values.category ? filters.values.category.split(',').filter(Boolean) : []
	);
	const selectedDirections = $derived(
		filters.values.direction ? filters.values.direction.split(',').filter(Boolean) : []
	);
	const selectedSort = $derived([filters.values.sort]);

	// Client-side direction filter on loaded items
	const displayedItems = $derived(
		selectedDirections.length === 0
			? pagination.items
			: pagination.items.filter((t) => selectedDirections.includes(t.growth_type ?? ''))
	);

	function getLocaleParam(): string | null {
		const filterLocale = filters.values.locale;
		if (filterLocale) return filterLocale;
		if (!personalization) return null;
		if (personalization.locale_ratio < 0.3) return 'en';
		if (personalization.locale_ratio > 0.7) return 'ko';
		return null;
	}

	function buildCacheKey(cursor?: string): string {
		return JSON.stringify({
			cursor,
			locale: getLocaleParam(),
			category: filters.values.category,
			since: filters.values.since,
			sort: filters.values.sort,
		});
	}

	const fetchTrends: FetchFn<TrendItem> = async (cursor?: string) => {
		const cacheKey = buildCacheKey(cursor);
		const cached = cache.get(cacheKey);
		if (cached) return cached;

		const params = new URLSearchParams({ limit: '20' });
		if (cursor) params.set('cursor', cursor);
		const locale = getLocaleParam();
		if (locale) params.set('locale', locale);
		if (filters.values.category) params.set('category', filters.values.category);
		if (filters.values.since) params.set('since', String(filters.values.since));
		if (filters.values.sort && filters.values.sort !== 'score') params.set('sort', filters.values.sort);

		const data = await apiRequest<TrendListResponse>(`/trends?${params.toString()}`);
		cache.set(cacheKey, data);
		return data;
	};

	async function loadTrends(): Promise<void> {
		try {
			await pagination.load(fetchTrends);
		} catch (error) {
			handleError(error);
		}
	}

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

	function showPlanGate(plan: string): void {
		planGateRequired = plan;
		planGateOpen = true;
	}

	async function exportTrends(format: 'csv' | 'pdf'): Promise<void> {
		if (format === 'csv') {
			isExportingCsv = true;
		} else {
			isExportingPdf = true;
		}
		try {
			const response = await fetch(
				`${import.meta.env.VITE_API_BASE_URL ?? '/api/v1'}/trends/export?format=${format}`,
				{
					headers: {
						Authorization: `Bearer ${localStorage.getItem('access_token') ?? ''}`,
					},
				}
			);
			if (response.status === 402 || response.status === 403) {
				const body = await response.json().catch(() => ({}));
				showPlanGate(body.required_plan ?? 'pro');
				return;
			}
			if (!response.ok) {
				errorCode = 'ERR_EXPORT';
				errorMessageKey = 'error.server';
				errorOpen = true;
				return;
			}
			const blob = await response.blob();
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = `trends.${format}`;
			a.click();
			URL.revokeObjectURL(url);
		} catch {
			errorCode = 'ERR_NETWORK';
			errorMessageKey = 'error.network';
			errorOpen = true;
		} finally {
			isExportingCsv = false;
			isExportingPdf = false;
		}
	}

	async function shareTrends(): Promise<void> {
		if (isSharing) return;
		isSharing = true;
		try {
			const snapshot = pagination.items.slice(0, 20).map((t) => ({
				id: t.id,
				title: t.title,
				category: t.category,
				summary: t.summary,
				score: t.score,
				early_trend_score: t.early_trend_score,
				keywords: t.keywords,
				created_at: t.created_at,
			}));
			const data = await apiRequest<{ share_url: string }>('/trends/share', {
				method: 'POST',
				body: JSON.stringify({ payload: { trends: snapshot } }),
			});
			const fullUrl = `${window.location.origin}${data.share_url}?utm_source=trendscope&utm_medium=share&utm_campaign=trend_share`;
			await navigator.clipboard.writeText(fullUrl);
			errorCode = '';
			errorMessageKey = 'trends.share.copied';
			errorOpen = true;
		} catch (error) {
			if (error instanceof PlanGateRequestError) {
				showPlanGate(error.requiredPlan);
			} else if (error instanceof ApiRequestError) {
				errorCode = error.errorCode;
				errorMessageKey = 'trends.share.error';
				errorOpen = true;
			} else {
				errorCode = 'ERR_NETWORK';
				errorMessageKey = 'error.network';
				errorOpen = true;
			}
		} finally {
			isSharing = false;
		}
	}

	async function loadMore(): Promise<void> {
		try {
			await pagination.loadMore(fetchTrends);
		} catch (error) {
			handleError(error);
		}
	}

	function applyFilter(type: 'category' | 'locale' | 'since' | 'sort', value: string | number | null): void {
		if (type === 'category') filters.set('category', value as string | null);
		else if (type === 'locale') filters.set('locale', value as string | null);
		else if (type === 'since') filters.set('since', value as number | null);
		else if (type === 'sort') filters.set('sort', (value as string) ?? 'score');
		pagination.reset();
		cache.clear();
		loadTrends();
	}

	function applyMultiFilter(type: 'category' | 'direction', values: string[]): void {
		const joined = values.length > 0 ? values.join(',') : null;
		if (type === 'category') filters.set('category', joined);
		else if (type === 'direction') filters.set('direction', joined);
		if (type === 'category') {
			// Category affects backend query → reload
			pagination.reset();
			cache.clear();
			loadTrends();
		}
		// direction is client-side only → no reload needed
	}

	function resetAllFilters(): void {
		filters.reset();
		pagination.reset();
		cache.clear();
		loadTrends();
	}

	// Active filter tags for display
	interface FilterTag { key: 'category' | 'direction'; value: string; label: string; }
	const activeTags = $derived<FilterTag[]>([
		...selectedCategories.map((v) => ({
			key: 'category' as const,
			value: v,
			label: $t(`filter.category.${v}`),
		})),
		...selectedDirections.map((v) => ({
			key: 'direction' as const,
			value: v,
			label: $t(`filter.direction.${v}`),
		})),
	]);

	function removeTag(tag: FilterTag): void {
		if (tag.key === 'category') {
			const next = selectedCategories.filter((v) => v !== tag.value);
			applyMultiFilter('category', next);
		} else {
			const next = selectedDirections.filter((v) => v !== tag.value);
			applyMultiFilter('direction', next);
		}
	}

	onMount(async () => {
		if (personalizationStore.settings) {
			personalization = personalizationStore.settings;
		} else {
			try {
				const data = await apiRequest<PersonalizationSettings>('/personalization');
				personalization = data;
				personalizationStore.set(data);
			} catch {
				// Non-critical — proceed without personalization
			}
		}
		await loadTrends();
	});

	let lastSeenVersion = personalizationStore.version;
	$effect(() => {
		const current = personalizationStore.version;
		if (current !== lastSeenVersion) {
			lastSeenVersion = current;
			personalization = personalizationStore.settings;
			pagination.reset();
			cache.clear();
			loadTrends();
		}
	});
</script>

<div class="space-y-6">
	<div class="flex flex-wrap items-center justify-between gap-2 sm:gap-3">
		<div class="flex items-center gap-2 sm:gap-3">
			<h1 class="text-xl sm:text-2xl font-bold text-gray-900 dark:text-gray-100">{$t('page.trends.title')}</h1>
			{#if personalization}
				<span class="inline-flex items-center rounded-full bg-blue-50 dark:bg-blue-900/20 px-2.5 py-0.5 text-xs font-medium text-blue-700 dark:text-blue-400">
					{$t('trends.personalized_badge')}
				</span>
			{/if}
		</div>

		<!-- Export / Share toolbar -->
		<div class="flex items-center gap-1.5 sm:gap-2">
			<button
				onclick={() => exportTrends('csv')}
				disabled={isExportingCsv}
				class="flex items-center gap-1 sm:gap-1.5 rounded-md border border-gray-300 dark:border-gray-600 px-2 py-1.5 sm:px-3 text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50"
			>
				<Download size={14} />
				<span class="hidden sm:inline">{$t('trends.export.csv')}</span>
				<span class="sm:hidden">CSV</span>
			</button>
			<button
				onclick={() => exportTrends('pdf')}
				disabled={isExportingPdf}
				class="flex items-center gap-1 sm:gap-1.5 rounded-md border border-gray-300 dark:border-gray-600 px-2 py-1.5 sm:px-3 text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50"
			>
				<Download size={14} />
				<span class="hidden sm:inline">{$t('trends.export.pdf')}</span>
				<span class="sm:hidden">PDF</span>
			</button>
			<button
				onclick={shareTrends}
				disabled={isSharing}
				class="flex items-center gap-1 sm:gap-1.5 rounded-md bg-blue-600 px-2 py-1.5 sm:px-3 text-xs sm:text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
			>
				<Share2 size={14} />
				{$t('trends.share.button')}
			</button>
		</div>
	</div>

	<!-- Filters -->
	<div class="space-y-2 sm:space-y-3">
		<!-- Row 1: Locale (pills) + MultiSelect dropdowns + Sort -->
		<div class="flex flex-wrap items-center gap-2">
			<!-- Locale pills -->
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

			<span class="h-4 w-px bg-gray-300 dark:bg-gray-600 mx-1"></span>

			<!-- Category MultiSelect -->
			<MultiSelect
				options={ALL_CATEGORIES.map((c) => ({ value: c, label: $t(`filter.category.${c}`) }))}
				bind:selected={
					() => selectedCategories,
					(v) => applyMultiFilter('category', v)
				}
				placeholder={$t('filter.category.label')}
				label={$t('filter.category.label')}
				multiple={true}
			/>

			<!-- Direction MultiSelect -->
			<MultiSelect
				options={DIRECTION_OPTIONS.map((d) => ({ value: d, label: $t(`filter.direction.${d}`) }))}
				bind:selected={
					() => selectedDirections,
					(v) => applyMultiFilter('direction', v)
				}
				placeholder={$t('filter.direction.label')}
				label={$t('filter.direction.label')}
				multiple={true}
			/>

			<!-- Period MultiSelect (single) -->
			<MultiSelect
				options={TIME_OPTIONS.map((o) => ({ value: String(o.value), label: $t(o.label) }))}
				bind:selected={
					() => filters.values.since ? [String(filters.values.since)] : [],
					(v) => applyFilter('since', v.length > 0 ? Number(v[0]) : null)
				}
				placeholder={$t('filter.period.label')}
				multiple={false}
			/>

			<!-- Sort MultiSelect (single) -->
			<MultiSelect
				options={SORT_OPTIONS.map((s) => ({ value: s, label: $t(`filter.sort.${s}`) }))}
				bind:selected={
					() => selectedSort,
					(v) => applyFilter('sort', v[0] ?? 'score')
				}
				placeholder={$t('filter.sort.label')}
				multiple={false}
			/>

			<!-- Reset all -->
			{#if activeTags.length > 0 || filters.values.since || filters.values.sort !== 'score'}
				<button
					class="text-xs text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 underline"
					onclick={resetAllFilters}
				>
					{$t('filter.reset_all')}
				</button>
			{/if}
		</div>

		<!-- Active filter tags -->
		{#if activeTags.length > 0}
			<div class="flex flex-wrap gap-1.5">
				{#each activeTags as tag (tag.key + ':' + tag.value)}
					<span class="inline-flex items-center gap-1 rounded-full bg-blue-100 dark:bg-blue-900/30 px-2.5 py-1 text-xs font-medium text-blue-700 dark:text-blue-300">
						{tag.label}
						<button
							class="ml-0.5 rounded-full hover:bg-blue-200 dark:hover:bg-blue-800"
							onclick={() => removeTag(tag)}
							aria-label="Remove filter"
						>
							<svg class="h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
								<path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/>
							</svg>
						</button>
					</span>
				{/each}
			</div>
		{/if}
	</div>

	<PageStateWrapper isLoading={pagination.isLoading} isEmpty={pagination.items.length === 0 && !pagination.isLoading}>
		{#snippet loading()}
			<div class="space-y-3">
				{#each Array(5) as _}
					<SkeletonCard />
				{/each}
			</div>
		{/snippet}

		{#snippet empty()}
			<EmptyState variant="no_results" onResetFilters={resetAllFilters} />
		{/snippet}

		{#snippet children()}
			<div class="space-y-3">
				{#each displayedItems as trend (trend.id)}
					<TrendCard {trend} />
				{/each}
			</div>

			<LoadMoreButton hasMore={pagination.hasMore} isLoading={pagination.isLoadingMore} onclick={loadMore} />
		{/snippet}
	</PageStateWrapper>

	{#if topTrendId && !pagination.isLoading}
		<TrendMap trendId={topTrendId} />
	{/if}

	{#if !pagination.isLoading}
		<MetaTrendsSection locale={filters.values.locale ?? undefined} />
	{/if}
</div>

<PlanGate open={planGateOpen} requiredPlan={planGateRequired} onClose={() => (planGateOpen = false)} />
<ErrorModal open={errorOpen} errorCode={errorCode} messageKey={errorMessageKey} onClose={() => (errorOpen = false)} onRetry={() => { errorOpen = false; loadTrends(); }} />
<QuotaExceededModal open={quotaOpen} feature={quotaFeature} limit={quotaLimit} resetTime={quotaResetTime} onClose={() => (quotaOpen = false)} />
