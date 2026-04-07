<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { apiRequest, ApiRequestError } from '$lib/api';
	import type {
		TrendListResponse,
		TrendItem,
		NewsListResponse,
		NewsItem,
		DashboardSummaryResponse,
	} from '$lib/api';
	import TrendCard from '../components/TrendCard.svelte';
	import NewsCard from '../components/NewsCard.svelte';
	import SkeletonCard from '../components/SkeletonCard.svelte';
	import StatCard from '../components/StatCard.svelte';
	import EarlyBadge from '../components/EarlyBadge.svelte';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';
	import TrendMap from '../components/TrendMap.svelte';
	import CategoryChart from '$lib/components/dashboard/CategoryChart.svelte';
	import SourceChart from '$lib/components/dashboard/SourceChart.svelte';
	import KeywordCloud from '$lib/components/dashboard/KeywordCloud.svelte';
	import Sparkline from '$lib/components/dashboard/Sparkline.svelte';
	import {
		TrendingUp,
		Newspaper,
		ArrowRight,
		Zap,
		Activity,
	} from 'lucide-svelte';

	let topTrends = $state<TrendItem[]>([]);
	let latestNews = $state<NewsItem[]>([]);
	let earlyTrends = $state<TrendItem[]>([]);
	let summary = $state<DashboardSummaryResponse | null>(null);
	let isLoading = $state(true);

	let errorOpen = $state(false);
	let errorCode = $state('');
	let errorMessageKey = $state('');

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

	onMount(async () => {
		await loadDashboard();
		isLoading = false;
	});
</script>

<div class="space-y-8">
	<div>
		<h1 class="text-2xl sm:text-3xl font-bold text-gray-900">{$t('page.home.title')}</h1>
		<p class="mt-1 text-sm sm:text-base text-gray-600">{$t('page.home.description')}</p>
	</div>

	{#if isLoading}
		<div class="space-y-3">
			{#each Array(3) as _}
				<SkeletonCard />
			{/each}
		</div>
	{:else}
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
				<KeywordCloud keywords={keywordCounts} />
			{/if}

			<!-- Early Trends -->
			{#if earlyTrends.length > 0}
				<div data-tour="early-trends" class="rounded-lg border border-gray-200 bg-white p-4 sm:p-5">
					<div class="flex items-center gap-2 mb-2">
						<Zap size={18} class="text-amber-500" />
						<h3 class="text-sm font-semibold text-gray-900">
							{$t('dashboard.early_trends')}
						</h3>
					</div>
					<p class="text-xs text-gray-500 mb-3">
						{$t('dashboard.early_trends.desc')}
					</p>
					<div class="space-y-2">
						{#each earlyTrends as trend (trend.id)}
							<a
								href="/trends/{trend.id}"
								class="block rounded-md border border-gray-100 bg-gray-50 p-3 hover:bg-amber-50 hover:border-amber-200 transition-colors"
							>
								<div class="flex items-center justify-between gap-2">
									<span class="text-sm font-medium text-gray-900 truncate flex-1">
										{trend.title}
									</span>
									<EarlyBadge score={trend.early_trend_score} />
								</div>
								<div class="mt-2 h-1.5 bg-gray-200 rounded-full overflow-hidden">
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
				<div class="rounded-lg border border-gray-200 bg-white p-4 sm:p-5">
					<TrendMap trendId={topTrends[0].id} />
				</div>
			{/if}
		</div>

		<!-- Hot Trends -->
		<section data-tour="hot-trends">
			<div class="flex items-center justify-between mb-3">
				<div class="flex items-center gap-2">
					<TrendingUp size={20} class="text-red-500" />
					<h2 class="text-lg font-bold text-gray-900">{$t('dashboard.hot_trends')}</h2>
				</div>
				<a href="/trends" class="flex items-center gap-1 text-sm text-blue-600 hover:underline">
					{$t('dashboard.view_all')}
					<ArrowRight size={14} />
				</a>
			</div>

			{#if topTrends.length === 0}
				<p class="text-gray-500 text-sm">{$t('status.no_results')}</p>
			{:else}
				<div class="space-y-3">
					{#each topTrends as trend, i (trend.id)}
						<div class="flex items-start gap-3">
							<span class="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-sm font-bold mt-3 {i < 3 ? 'bg-red-500 text-white' : 'bg-gray-200 text-gray-600'}">
								{i + 1}
							</span>
							<div class="flex-1 min-w-0">
								<div class="flex items-center gap-2">
									<div class="flex-1 min-w-0">
										<TrendCard {trend} />
									</div>
									<Sparkline
										values={[trend.score * 0.6, trend.score * 0.75, trend.score * 0.85, trend.score * 0.9, trend.score]}
										color={trend.direction === 'rising' ? '#22c55e' : trend.direction === 'declining' ? '#ef4444' : '#3b82f6'}
									/>
								</div>
								{#if trend.summary}
									<p class="mt-1 ml-0 text-xs text-gray-500 line-clamp-2">{trend.summary}</p>
								{/if}
							</div>
						</div>
					{/each}
				</div>
			{/if}
		</section>

		<!-- Latest News -->
		<section>
			<div class="flex items-center justify-between mb-3">
				<div class="flex items-center gap-2">
					<Newspaper size={20} class="text-blue-500" />
					<h2 class="text-lg font-bold text-gray-900">{$t('dashboard.latest_news')}</h2>
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
	{/if}
</div>

<ErrorModal open={errorOpen} errorCode={errorCode} messageKey={errorMessageKey} onClose={() => (errorOpen = false)} onRetry={() => { errorOpen = false; loadDashboard(); }} />
