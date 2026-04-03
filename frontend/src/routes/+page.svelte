<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { apiRequest, ApiRequestError } from '$lib/api';
	import type { TrendListResponse, TrendItem, NewsListResponse, NewsItem } from '$lib/api';
	import TrendCard from '../components/TrendCard.svelte';
	import NewsCard from '../components/NewsCard.svelte';
	import SkeletonCard from '../components/SkeletonCard.svelte';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';
	import { TrendingUp, Newspaper, ArrowRight, BarChart3, Lightbulb } from 'lucide-svelte';

	let topTrends = $state<TrendItem[]>([]);
	let latestNews = $state<NewsItem[]>([]);
	let isLoading = $state(true);

	let errorOpen = $state(false);
	let errorCode = $state('');
	let errorMessageKey = $state('');

	const CATEGORY_COLORS: Record<string, string> = {
		tech: 'bg-blue-500',
		economy: 'bg-green-500',
		entertainment: 'bg-purple-500',
		lifestyle: 'bg-pink-500',
		politics: 'bg-red-500',
		sports: 'bg-orange-500',
		society: 'bg-teal-500',
	};

	// Category stats derived from trends
	let categoryStats = $derived(() => {
		const counts: Record<string, number> = {};
		for (const trend of topTrends) {
			counts[trend.category] = (counts[trend.category] || 0) + 1;
		}
		return Object.entries(counts).sort((a, b) => b[1] - a[1]);
	});

	async function loadDashboard(): Promise<void> {
		try {
			const [trendsData, newsData] = await Promise.all([
				apiRequest<TrendListResponse>('/trends?limit=5'),
				apiRequest<NewsListResponse>('/news?limit=5'),
			]);
			topTrends = trendsData.items;
			latestNews = newsData.items;
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
		<!-- Category Distribution + Insight Preview -->
		{#if topTrends.length > 0}
			<div class="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-6">
				<!-- Category Distribution -->
				<div class="rounded-lg border border-gray-200 bg-white p-4 sm:p-5">
					<div class="flex items-center gap-2 mb-3">
						<BarChart3 size={18} class="text-indigo-500" />
						<h3 class="text-sm font-semibold text-gray-900">{$t('dashboard.category_distribution')}</h3>
					</div>
					<div class="space-y-2">
						{#each categoryStats() as [category, count]}
							{@const total = topTrends.length}
							{@const pct = Math.round((count / total) * 100)}
							<div class="flex items-center gap-2">
								<span class="text-xs text-gray-600 w-20 truncate">{$t(`filter.category.${category}`)}</span>
								<div class="flex-1 h-5 bg-gray-100 rounded-full overflow-hidden">
									<div
										class="h-full rounded-full {CATEGORY_COLORS[category] ?? 'bg-gray-400'} transition-all duration-300"
										style="width: {pct}%"
									></div>
								</div>
								<span class="text-xs font-medium text-gray-700 w-10 text-right">{pct}%</span>
							</div>
						{/each}
					</div>
				</div>

				<!-- Insight Preview -->
				<div class="rounded-lg border border-gray-200 bg-white p-4 sm:p-5">
					<div class="flex items-center gap-2 mb-3">
						<Lightbulb size={18} class="text-amber-500" />
						<h3 class="text-sm font-semibold text-gray-900">{$t('dashboard.insight_preview')}</h3>
					</div>
					<p class="text-xs text-gray-500 mb-3">{$t('dashboard.insight_preview.desc')}</p>
					<div class="space-y-2">
						{#each topTrends.slice(0, 3) as trend (trend.id)}
							<a
								href="/trends/{trend.id}/insights"
								class="block rounded-md border border-gray-100 bg-gray-50 p-3 hover:bg-blue-50 hover:border-blue-200 transition-colors"
							>
								<div class="flex items-center justify-between">
									<span class="text-sm font-medium text-gray-900 truncate flex-1">{trend.title}</span>
									<ArrowRight size={14} class="text-gray-400 shrink-0 ml-2" />
								</div>
								{#if trend.summary}
									<p class="mt-1 text-xs text-gray-500 line-clamp-2">{trend.summary}</p>
								{/if}
							</a>
						{/each}
					</div>
				</div>
			</div>
		{/if}

		<!-- Hot Trends -->
		<section>
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
								<TrendCard {trend} />
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
