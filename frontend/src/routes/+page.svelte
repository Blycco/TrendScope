<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount, onDestroy } from 'svelte';
	import { apiRequest, ApiRequestError } from '$lib/api';
	import type {
		TrendListResponse,
		TrendItem,
		NewsListResponse,
		NewsItem,
		DashboardSummaryResponse,
	} from '$lib/api';
	import TrendCard from '../components/TrendCard.svelte';
	import BentoTrendGrid from '$lib/components/BentoTrendGrid.svelte';
	import NewsCard from '../components/NewsCard.svelte';
	import SkeletonCard from '../components/SkeletonCard.svelte';
	import StatCard from '../components/StatCard.svelte';
	import EarlyBadge from '../components/EarlyBadge.svelte';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';
	import PageStateWrapper from '$lib/ui/PageStateWrapper.svelte';
	import TrendMap from '$lib/components/TrendMap.svelte';
	import CategoryChart from '$lib/components/dashboard/CategoryChart.svelte';
	import SourceChart from '$lib/components/dashboard/SourceChart.svelte';
	import KeywordCloud from '$lib/components/dashboard/KeywordCloud.svelte';
	import Sparkline from '$lib/components/dashboard/Sparkline.svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import {
		TrendingUp,
		Newspaper,
		ArrowRight,
		Zap,
		Activity,
		User,
	} from 'lucide-svelte';

	const roleSectionTitle = $derived.by(() => {
		const role = authStore.user?.role;
		if (role === 'marketer') return $t('dashboard.role_section.title.marketer');
		if (role === 'creator') return $t('dashboard.role_section.title.creator');
		if (role === 'business_owner') return $t('dashboard.role_section.title.business_owner');
		if (role === 'general') return $t('dashboard.role_section.title.general');
		return null;
	});

	let topTrends = $state<TrendItem[]>([]);
	let latestNews = $state<NewsItem[]>([]);
	let earlyTrends = $state<TrendItem[]>([]);
	let summary = $state<DashboardSummaryResponse | null>(null);
	let isLoading = $state(true);

	let errorOpen = $state(false);
	let errorCode = $state('');
	let errorMessageKey = $state('');

	let eventSource: EventSource | null = null;
	let newTrendCount = $state(0);
	let showBanner = $state(false);
	let bannerTimer: ReturnType<typeof setTimeout> | null = null;

	let isDashboardEmpty = $derived(
		!isLoading && topTrends.length === 0 && latestNews.length === 0 && earlyTrends.length === 0 && summary === null
	);

	let keywordCounts = $derived.by(() => {
		const counts = new Map<string, number>();
		for (const trend of topTrends) {
			for (const kw of trend.keywords) {
				counts.set(kw, (counts.get(kw) || 0) + 1);
			}
		}
		return [...counts.entries()]
			.sort((a, b) => b[1] - a[1])
			.slice(0, 20);
	});

	let hotKeywords = $derived.by(() => {
		const hot = new Set<string>();
		for (const trend of topTrends) {
			if ((trend.burst_score ?? 0) > 0.7) {
				for (const kw of trend.keywords) hot.add(kw);
			}
		}
		return hot;
	});

	let newKeywords = $derived.by(() => {
		const threshold = Date.now() - 24 * 60 * 60 * 1000;
		const newKws = new Set<string>();
		for (const trend of topTrends) {
			if (new Date(trend.created_at).getTime() > threshold) {
				for (const kw of trend.keywords) newKws.add(kw);
			}
		}
		return newKws;
	});

	async function loadDashboard(): Promise<void> {
		try {
			const [trendsData, newsData, earlyData, summaryData] = await Promise.all([
				apiRequest<TrendListResponse>('/trends?limit=5'),
				apiRequest<NewsListResponse>('/news?limit=5'),
				apiRequest<TrendListResponse>('/trends/early?limit=5'),
				apiRequest<DashboardSummaryResponse>('/dashboard/summary'),
			]);
			topTrends = trendsData.items;
			latestNews = newsData.items;
			earlyTrends = earlyData.items;
			summary = summaryData;
		} catch (error) {
			if (error instanceof ApiRequestError) {
				errorCode = error.errorCode;
				errorMessageKey = 'error.server';
			} else {
				errorCode = 'ERR_NETWORK';
				errorMessageKey = 'error.network';
			}
			errorOpen = true;
		}
	}

	function connectSSE(): void {
		if (typeof EventSource === 'undefined') return; // SSR guard
		eventSource = new EventSource('/api/v1/live/trends');
		eventSource.onmessage = () => {
			newTrendCount += 1;
			showBanner = true;
			if (bannerTimer) clearTimeout(bannerTimer);
			bannerTimer = setTimeout(() => {
				showBanner = false;
			}, 5000);
		};
		eventSource.onerror = () => {
			// delegate reconnect to the browser's built-in EventSource retry
		};
	}

	onMount(async () => {
		await loadDashboard();
		isLoading = false;
		connectSSE();
	});

	onDestroy(() => {
		eventSource?.close();
		if (bannerTimer) clearTimeout(bannerTimer);
	});
</script>

<div class="space-y-8">
	<div>
		<h1 class="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-gray-100">{$t('page.home.title')}</h1>
		<p class="mt-1 text-sm sm:text-base text-gray-600 dark:text-gray-400">{$t('page.home.description')}</p>
	</div>

	{#if showBanner}
		<div class="mb-4 rounded-md bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 px-4 py-3 flex items-center justify-between">
			<p class="text-sm text-blue-700 dark:text-blue-400">
				{$t('live.new_trends', { values: { count: newTrendCount } })}
			</p>
			<button
				onclick={() => { showBanner = false; newTrendCount = 0; loadDashboard(); }}
				class="text-sm text-blue-600 dark:text-blue-400 hover:underline ml-4"
			>
				{$t('live.refresh')}
			</button>
		</div>
	{/if}

	<PageStateWrapper {isLoading} isEmpty={isDashboardEmpty}>
		{#snippet loading()}
			<div class="space-y-3">
				{#each Array(3) as _}
					<SkeletonCard />
				{/each}
			</div>
		{/snippet}

		{#snippet children()}
		<!-- Summary Stats -->
		{#if summary}
			<div data-tour="stat-cards" class="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4">
				<StatCard
					icon={TrendingUp}
					iconColor="text-red-500"
					label={$t('dashboard.total_trends')}
					value={summary.total_trends}
					subtext={$t('dashboard.last_24h')}
				/>
				<StatCard
					icon={Newspaper}
					iconColor="text-blue-500"
					label={$t('dashboard.total_news')}
					value={summary.total_news}
					subtext={$t('dashboard.last_24h')}
				/>
				<StatCard
					icon={Activity}
					iconColor="text-green-500"
					label={$t('dashboard.avg_score')}
					value={summary.avg_score}
				/>
				<StatCard
					icon={Zap}
					iconColor="text-amber-500"
					label={$t('dashboard.early_signals')}
					value={summary.early_signal_count}
				/>
			</div>
		{/if}

		<!-- Widget Grid -->
		<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6">
			{#if summary && Object.keys(summary.category_counts).length > 0}
				<CategoryChart categoryCounts={summary.category_counts} />
			{/if}

			{#if summary && Object.keys(summary.source_counts).length > 0}
				<SourceChart sourceCounts={summary.source_counts} />
			{/if}

			{#if keywordCounts.length > 0}
				<KeywordCloud keywords={keywordCounts} {hotKeywords} {newKeywords} />
			{/if}

			<!-- Early Trends -->
			{#if earlyTrends.length > 0}
				<div data-tour="early-trends" class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 sm:p-5">
					<div class="flex items-center gap-2 mb-2">
						<Zap size={18} class="text-amber-500" />
						<h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100">
							{$t('dashboard.early_trends')}
						</h3>
					</div>
					<p class="text-xs text-gray-500 dark:text-gray-400 mb-1">
						{$t('dashboard.early_trends.desc')}
					</p>
					<p class="text-xs text-amber-600 dark:text-amber-400 mb-3">
						{$t('dashboard.early_trends.desc2')}
					</p>
					<div class="space-y-2">
						{#each earlyTrends as trend (trend.id)}
							<a
								href="/trends/{trend.id}"
								class="block rounded-md border border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-700 p-3 hover:bg-amber-50 dark:hover:bg-amber-900/20 hover:border-amber-200 dark:hover:border-amber-700 transition-colors"
							>
								<div class="flex items-center justify-between gap-2">
									<span class="text-sm font-medium text-gray-900 dark:text-gray-100 truncate flex-1">
										{trend.title}
									</span>
									<EarlyBadge score={trend.early_trend_score} />
								</div>
								<div class="mt-2 h-1.5 bg-gray-200 dark:bg-gray-600 rounded-full overflow-hidden">
									<div
										class="h-full rounded-full transition-all duration-300"
										class:bg-red-500={trend.early_trend_score >= 0.8}
										class:bg-orange-400={trend.early_trend_score >= 0.5 && trend.early_trend_score < 0.8}
										class:bg-blue-400={trend.early_trend_score < 0.5}
										style="width: {Math.round(trend.early_trend_score * 100)}%"
									></div>
								</div>
							</a>
						{/each}
					</div>
				</div>
			{/if}

			<!-- Trend Map -->
			{#if topTrends.length > 0}
				<div class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 sm:p-5">
					<TrendMap trendId={topTrends[0].id} />
				</div>
			{/if}
		</div>

		<!-- Role-based recommendation section -->
		{#if authStore.isAuthenticated && roleSectionTitle}
			<section>
				<div class="flex items-center gap-2 mb-3">
					<User size={18} class="text-purple-500" />
					<h2 class="text-lg font-bold text-gray-900 dark:text-gray-100">{roleSectionTitle}</h2>
				</div>
				{#if topTrends.length > 0}
					<div class="space-y-3">
						{#each topTrends.slice(0, 3) as trend (trend.id)}
							<TrendCard {trend} />
						{/each}
					</div>
				{/if}
			</section>
		{:else if !authStore.isAuthenticated}
			<div class="rounded-lg border border-purple-100 dark:border-purple-800 bg-purple-50 dark:bg-purple-950/20 p-4 flex items-center justify-between gap-4">
				<div class="flex items-center gap-2">
					<User size={16} class="text-purple-500 flex-shrink-0" />
					<p class="text-sm text-purple-700 dark:text-purple-300">{$t('dashboard.role_section.cta')}</p>
				</div>
				<a href="/settings" class="text-sm font-medium text-purple-600 dark:text-purple-400 hover:underline flex-shrink-0">
					{$t('dashboard.role_section.cta_link')}
					<ArrowRight size={12} class="inline ml-0.5" />
				</a>
			</div>
		{/if}

		<!-- Hot Trends (Bento Grid) -->
		<section data-tour="hot-trends">
			<div class="flex items-center justify-between mb-3">
				<div class="flex items-center gap-2">
					<TrendingUp size={20} class="text-red-500" />
					<h2 class="text-lg font-bold text-gray-900 dark:text-gray-100">{$t('dashboard.hot_trends')}</h2>
				</div>
				<a href="/trends" class="flex items-center gap-1 text-sm text-blue-600 hover:underline">
					{$t('dashboard.view_all')}
					<ArrowRight size={14} />
				</a>
			</div>

			{#if topTrends.length === 0}
				<p class="text-gray-500 text-sm">{$t('status.no_results')}</p>
			{:else}
				<BentoTrendGrid trends={topTrends} />
			{/if}
		</section>

		<!-- Latest News -->
		<section>
			<div class="flex items-center justify-between mb-3">
				<div class="flex items-center gap-2">
					<Newspaper size={20} class="text-blue-500" />
					<h2 class="text-lg font-bold text-gray-900 dark:text-gray-100">{$t('dashboard.latest_news')}</h2>
				</div>
				<a href="/news" class="flex items-center gap-1 text-sm text-blue-600 hover:underline">
					{$t('dashboard.view_all')}
					<ArrowRight size={14} />
				</a>
			</div>

			{#if latestNews.length === 0}
				<p class="text-gray-500 text-sm">{$t('status.no_results')}</p>
			{:else}
				<div class="space-y-3">
					{#each latestNews as item (item.id)}
						<NewsCard news={item} />
					{/each}
				</div>
			{/if}
		</section>
		{/snippet}
	</PageStateWrapper>
</div>

<ErrorModal open={errorOpen} errorCode={errorCode} messageKey={errorMessageKey} onClose={() => (errorOpen = false)} onRetry={() => { errorOpen = false; loadDashboard(); }} />
