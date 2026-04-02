<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { apiRequest, ApiRequestError } from '$lib/api';
	import type { TrendListResponse, TrendItem, NewsListResponse, NewsItem } from '$lib/api';
	import TrendCard from '../components/TrendCard.svelte';
	import NewsCard from '../components/NewsCard.svelte';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';
	import { TrendingUp, Newspaper, ArrowRight } from 'lucide-svelte';

	let topTrends = $state<TrendItem[]>([]);
	let latestNews = $state<NewsItem[]>([]);
	let isLoading = $state(true);

	let errorOpen = $state(false);
	let errorCode = $state('');
	let errorMessageKey = $state('');

	// Category stats derived from trends
	let categoryStats = $derived(() => {
		const counts: Record<string, number> = {};
		for (const trend of topTrends) {
			counts[trend.category] = (counts[trend.category] || 0) + 1;
		}
		return counts;
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
		<h1 class="text-3xl font-bold text-gray-900">{$t('page.home.title')}</h1>
		<p class="mt-1 text-gray-600">{$t('page.home.description')}</p>
	</div>

	{#if isLoading}
		<p class="text-gray-500">{$t('status.loading')}</p>
	{:else}
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
						<div class="flex items-center gap-3">
							<span class="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-sm font-bold {i < 3 ? 'bg-red-500 text-white' : 'bg-gray-200 text-gray-600'}">
								{i + 1}
							</span>
							<div class="flex-1">
								<TrendCard {trend} />
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
