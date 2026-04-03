<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { apiRequest, ApiRequestError, QuotaExceededRequestError, PlanGateRequestError } from '$lib/api';
	import type { TrendListResponse, TrendItem } from '$lib/api';
	import TrendCard from '../../components/TrendCard.svelte';
	import SkeletonCard from '../../components/SkeletonCard.svelte';
	import TrendMap from '$lib/components/TrendMap.svelte';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';
	import QuotaExceededModal from '$lib/ui/QuotaExceededModal.svelte';
	import PlanGate from '$lib/ui/PlanGate.svelte';
	import { Download, Share2 } from 'lucide-svelte';

	interface PersonalizationSettings {
		category_weights: { tech: number; finance: number; entertainment: number; lifestyle: number };
		locale_ratio: number;
	}

	const ALL_CATEGORIES = ['tech', 'economy', 'entertainment', 'lifestyle', 'politics', 'sports', 'society'] as const;
	type Category = (typeof ALL_CATEGORIES)[number];

	const TIME_OPTIONS = [
		{ label: 'filter.time.1h', value: 1 },
		{ label: 'filter.time.6h', value: 6 },
		{ label: 'filter.time.24h', value: 24 },
		{ label: 'filter.time.7d', value: 168 },
		{ label: 'filter.time.30d', value: 720 },
	] as const;

	let trends = $state<TrendItem[]>([]);
	let nextCursor = $state<string | null>(null);
	let isLoading = $state(true);
	let isLoadingMore = $state(false);
	let personalization = $state<PersonalizationSettings | null>(null);
	let selectedCategory = $state<string | null>(null);
	let selectedTime = $state<number | null>(null);
	let selectedLocale = $state<string | null>(null);

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

	// ID of the top trend to use for TrendMap
	const topTrendId = $derived(trends.length > 0 ? trends[0].id : null);

	function getLocaleParam(): string | null {
		if (selectedLocale) return selectedLocale;
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
			if (selectedCategory) params.set('category', selectedCategory);
			if (selectedTime) params.set('since', String(selectedTime));

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
			// Fetch as blob for file download
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
			const data = await apiRequest<{ share_url: string }>('/trends/share', { method: 'POST' });
			await navigator.clipboard.writeText(data.share_url);
			// Brief success indicator via error modal (re-using with success message would need a toast,
			// but UX spec says use modals for all user messages — show inline instead)
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
	<div class="flex flex-wrap items-center justify-between gap-3">
		<div class="flex items-center gap-3">
			<h1 class="text-2xl font-bold text-gray-900">{$t('page.trends.title')}</h1>
			{#if personalization}
				<span class="inline-flex items-center rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-medium text-blue-700">
					{$t('trends.personalized_badge')}
				</span>
			{/if}
		</div>

		<!-- Export / Share toolbar -->
		<div class="flex items-center gap-2">
			<button
				onclick={() => exportTrends('csv')}
				disabled={isExportingCsv}
				class="flex items-center gap-1.5 rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
			>
				<Download size={14} />
				{$t('trends.export.csv')}
			</button>
			<button
				onclick={() => exportTrends('pdf')}
				disabled={isExportingPdf}
				class="flex items-center gap-1.5 rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
			>
				<Download size={14} />
				{$t('trends.export.pdf')}
			</button>
			<button
				onclick={shareTrends}
				disabled={isSharing}
				class="flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
			>
				<Share2 size={14} />
				{$t('trends.share.button')}
			</button>
		</div>
	</div>

	<!-- Locale filter -->
	<div class="flex gap-2 flex-wrap">
		<button
			onclick={() => { selectedLocale = null; trends = []; nextCursor = null; loadTrends(); }}
			class="rounded-full px-3 py-1 text-xs font-medium transition-colors {selectedLocale === null ? 'bg-indigo-600 text-white' : 'border border-gray-200 bg-white text-gray-600 hover:bg-gray-50'}"
		>{$t('filter.all')}</button>
		<button
			onclick={() => { selectedLocale = 'ko'; trends = []; nextCursor = null; loadTrends(); }}
			class="rounded-full px-3 py-1 text-xs font-medium transition-colors {selectedLocale === 'ko' ? 'bg-indigo-600 text-white' : 'border border-gray-200 bg-white text-gray-600 hover:bg-gray-50'}"
		>{$t('filter.locale.domestic')}</button>
		<button
			onclick={() => { selectedLocale = 'en'; trends = []; nextCursor = null; loadTrends(); }}
			class="rounded-full px-3 py-1 text-xs font-medium transition-colors {selectedLocale === 'en' ? 'bg-indigo-600 text-white' : 'border border-gray-200 bg-white text-gray-600 hover:bg-gray-50'}"
		>{$t('filter.locale.international')}</button>
	</div>

	<!-- Category filter -->
	<div class="flex gap-2 flex-wrap">
		<button
			onclick={() => { selectedCategory = null; trends = []; nextCursor = null; loadTrends(); }}
			class="rounded-full px-3 py-1 text-xs font-medium transition-colors {selectedCategory === null ? 'bg-blue-600 text-white' : 'border border-gray-200 bg-white text-gray-600 hover:bg-gray-50'}"
		>{$t('filter.all')}</button>
		{#each ALL_CATEGORIES as cat}
			<button
				onclick={() => { selectedCategory = cat; trends = []; nextCursor = null; loadTrends(); }}
				class="rounded-full px-3 py-1 text-xs font-medium transition-colors {selectedCategory === cat ? 'bg-blue-600 text-white' : 'border border-gray-200 bg-white text-gray-600 hover:bg-gray-50'}"
			>{$t(`filter.category.${cat}`)}</button>
		{/each}
	</div>

	<!-- Time filter -->
	<div class="flex gap-2 flex-wrap">
		<button
			onclick={() => { selectedTime = null; trends = []; nextCursor = null; loadTrends(); }}
			class="rounded-full px-2.5 py-1 text-xs font-medium transition-colors {selectedTime === null ? 'bg-gray-800 text-white' : 'border border-gray-200 bg-white text-gray-500 hover:bg-gray-50'}"
		>{$t('filter.all')}</button>
		{#each TIME_OPTIONS as opt}
			<button
				onclick={() => { selectedTime = opt.value; trends = []; nextCursor = null; loadTrends(); }}
				class="rounded-full px-2.5 py-1 text-xs font-medium transition-colors {selectedTime === opt.value ? 'bg-gray-800 text-white' : 'border border-gray-200 bg-white text-gray-500 hover:bg-gray-50'}"
			>{$t(opt.label)}</button>
		{/each}
	</div>

	{#if isLoading}
		<div class="space-y-3">
			{#each Array(5) as _}
				<SkeletonCard />
			{/each}
		</div>
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

	{#if topTrendId && !isLoading}
		<TrendMap trendId={topTrendId} />
	{/if}
</div>

<PlanGate open={planGateOpen} requiredPlan={planGateRequired} onClose={() => (planGateOpen = false)} />
<ErrorModal open={errorOpen} errorCode={errorCode} messageKey={errorMessageKey} onClose={() => (errorOpen = false)} onRetry={() => { errorOpen = false; loadTrends(); }} />
<QuotaExceededModal open={quotaOpen} feature={quotaFeature} limit={quotaLimit} resetTime={quotaResetTime} onClose={() => (quotaOpen = false)} />
