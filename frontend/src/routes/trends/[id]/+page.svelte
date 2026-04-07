<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { apiRequest, ApiRequestError, PlanGateRequestError } from '$lib/api';
	import type { ForecastResponse, ForecastPoint } from '$lib/api';
	import EarlyBadge from '../../../components/EarlyBadge.svelte';
	import DirectionBadge from '../../../components/DirectionBadge.svelte';
	import TrendChart from '../../../components/TrendChart.svelte';
	import SentimentChart from '$lib/components/SentimentChart.svelte';
	import ForecastChart from '$lib/components/ForecastChart.svelte';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';
	import PlanGate from '$lib/ui/PlanGate.svelte';
	import { ExternalLink, ArrowLeft, Lightbulb, TrendingUp } from 'lucide-svelte';

	interface TrendArticle {
		id: string;
		title: string;
		url: string;
		source: string | null;
		publish_time: string | null;
		body_snippet: string | null;
	}

	interface TrendDetail {
		id: string;
		title: string;
		category: string;
		summary: string | null;
		score: number;
		early_trend_score: number;
		keywords: string[];
		created_at: string;
		direction: 'rising' | 'steady' | 'declining';
		articles: TrendArticle[];
	}

	const groupId = $derived($page.params.id);

	let detail = $state<TrendDetail | null>(null);
	let isLoading = $state(true);
	let errorOpen = $state(false);
	let errorCode = $state('');
	let errorMessageKey = $state('');

	let forecastData = $state<ForecastPoint[]>([]);
	let isForecastLoading = $state(false);
	let planGateOpen = $state(false);
	let planGateRequired = $state('pro');

	async function loadDetail(): Promise<void> {
		try {
			detail = await apiRequest<TrendDetail>(`/trends/${groupId}`);
		} catch (error) {
			if (error instanceof ApiRequestError) {
				errorCode = error.errorCode;
				errorMessageKey = 'error.server';
			} else {
				errorCode = 'ERR_NETWORK';
				errorMessageKey = 'error.network';
			}
			errorOpen = true;
		} finally {
			isLoading = false;
		}
	}

	async function loadForecast(): Promise<void> {
		isForecastLoading = true;
		try {
			const resp = await apiRequest<ForecastResponse>(`/forecast/${groupId}?horizon=365`);
			forecastData = resp.points;
		} catch (error) {
			if (error instanceof PlanGateRequestError) {
				planGateRequired = error.requiredPlan;
				planGateOpen = true;
			}
			forecastData = [];
		} finally {
			isForecastLoading = false;
		}
	}

	onMount(() => {
		loadDetail();
		loadForecast();
	});

	const formattedDate = $derived(
		detail ? new Date(detail.created_at).toLocaleDateString('ko-KR', {
			year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit'
		}) : ''
	);
</script>

<div class="space-y-6">
	<a href="/trends" class="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700">
		<ArrowLeft size={16} />
		{$t('nav.sidebar.trends')}
	</a>

	{#if isLoading}
		<p class="text-gray-500">{$t('status.loading')}</p>
	{:else if detail}
		<div class="rounded-lg border border-gray-200 bg-white p-6">
			<div class="flex items-start justify-between">
				<div class="flex-1">
					<div class="flex items-center gap-3">
						<h1 class="text-xl font-bold text-gray-900">{detail.title}</h1>
						<EarlyBadge score={detail.early_trend_score} />
						<DirectionBadge direction={detail.direction} />
					</div>
					<div class="mt-2 flex items-center gap-4 text-sm text-gray-500">
						<span>{$t('trend.category')}: {detail.category}</span>
						<span>{formattedDate}</span>
						<span>{$t('trend.score')}: {detail.score.toFixed(1)}</span>
					</div>
				</div>
				<a
					href="/trends/{detail.id}/insights"
					class="flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
				>
					<Lightbulb size={14} />
					{$t('trend.detail.insights')}
				</a>
			</div>

			{#if detail.summary}
				<div class="mt-4 rounded-md bg-gray-50 p-4">
					<p class="text-sm text-gray-700">{detail.summary}</p>
				</div>
			{/if}

			<div class="mt-4 flex flex-wrap gap-1.5">
				{#each detail.keywords as keyword}
					<span class="inline-flex rounded-md bg-blue-50 px-2 py-0.5 text-xs text-blue-700">
						{keyword}
					</span>
				{/each}
			</div>
		</div>

		<TrendChart groupId={detail.id} />

		<SentimentChart groupId={detail.id} />

		{#if isForecastLoading}
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<p class="text-sm text-gray-400">{$t('status.loading')}</p>
			</div>
		{:else if forecastData.length > 0}
			<ForecastChart data={forecastData} />
		{/if}

		<div>
			<h2 class="text-lg font-semibold text-gray-900 mb-3">
				{$t('trend.detail.articles')} ({detail.articles.length})
			</h2>
			<div class="space-y-2">
				{#each detail.articles as article (article.id)}
					<a
						href={article.url}
						target="_blank"
						rel="noopener noreferrer"
						class="flex items-start gap-3 rounded-lg border border-gray-200 bg-white p-4 hover:shadow-sm transition-shadow"
					>
						<div class="flex-1 min-w-0">
							<div class="flex items-center gap-2">
								<p class="text-sm font-medium text-gray-900 truncate">{article.title}</p>
								<ExternalLink size={12} class="text-gray-400 shrink-0" />
							</div>
							{#if article.body_snippet}
								<p class="mt-1 text-xs text-gray-500 line-clamp-2">{article.body_snippet}</p>
							{/if}
							<div class="mt-1.5 flex items-center gap-3 text-xs text-gray-400">
								{#if article.source}
									<span>{article.source}</span>
								{/if}
								{#if article.publish_time}
									<span>{new Date(article.publish_time).toLocaleDateString('ko-KR')}</span>
								{/if}
							</div>
						</div>
					</a>
				{/each}
			</div>
		</div>
	{:else}
		<p class="text-gray-500">{$t('status.no_results')}</p>
	{/if}
</div>

<PlanGate open={planGateOpen} requiredPlan={planGateRequired} onClose={() => (planGateOpen = false)} />
<ErrorModal open={errorOpen} errorCode={errorCode} messageKey={errorMessageKey} onClose={() => (errorOpen = false)} onRetry={() => { errorOpen = false; loadDetail(); }} />
