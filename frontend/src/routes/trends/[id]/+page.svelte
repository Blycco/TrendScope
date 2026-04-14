<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { apiRequest, ApiRequestError, PlanGateRequestError, QuotaExceededRequestError } from '$lib/api';
	import type { ForecastResponse, ForecastPoint } from '$lib/api';
	import EarlyBadge from '../../../components/EarlyBadge.svelte';
	import DirectionBadge from '../../../components/DirectionBadge.svelte';
	import TrendChart from '../../../components/TrendChart.svelte';
	import AspectSentimentChart from '$lib/components/AspectSentimentChart.svelte';
	import KeywordTimeline from '$lib/components/KeywordTimeline.svelte';
	import KeywordGraph from '$lib/components/KeywordGraph.svelte';
	import SentimentChart from '$lib/components/SentimentChart.svelte';
	import ForecastChart from '$lib/components/ForecastChart.svelte';
	import BurstGauge from '$lib/components/BurstGauge.svelte';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';
	import PlanGate from '$lib/ui/PlanGate.svelte';
	import SuccessToast from '$lib/ui/SuccessToast.svelte';
	import QuotaExceededModal from '$lib/ui/QuotaExceededModal.svelte';
	import { ExternalLink, ArrowLeft, Lightbulb, Share2, Bookmark } from 'lucide-svelte';

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
		burst_score?: number;
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
	let planGateUpgradeUrl = $state('/pricing');

	let articleTab = $state<'all' | 'by_source'>('all');
	let expandedSources = $state<Set<string>>(new Set());

	let scrapId = $state<string | null>(null);
	let scrapToggling = $state(false);
	let successOpen = $state(false);
	let successMessageKey = $state('toast.success.default');
	let quotaOpen = $state(false);
	let quotaFeature = $state('');
	let quotaLimit = $state(0);
	let quotaResetTime = $state('');

	const burstScore = $derived(detail ? (detail.burst_score ?? detail.score / 100) : 0);

	const articlesBySource = $derived.by(() => {
		if (!detail) return new Map<string, TrendArticle[]>();
		const map = new Map<string, TrendArticle[]>();
		for (const a of detail.articles) {
			const src = a.source ?? 'Unknown';
			if (!map.has(src)) map.set(src, []);
			map.get(src)!.push(a);
		}
		return map;
	});

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
				planGateUpgradeUrl = error.upgradeUrl ?? '/pricing';
				planGateOpen = true;
			}
			forecastData = [];
		} finally {
			isForecastLoading = false;
		}
	}

	async function loadScrapState(): Promise<void> {
		try {
			const data = await apiRequest<{ items: Array<{ id: string; item_type: string; item_id: string }>; total: number }>(
				'/scraps?limit=100'
			);
			const found = data.items?.find((s) => s.item_type === 'trend' && s.item_id === groupId);
			scrapId = found?.id ?? null;
		} catch {
			scrapId = null;
		}
	}

	async function toggleScrap(): Promise<void> {
		if (!detail || scrapToggling) return;
		scrapToggling = true;
		try {
			if (scrapId) {
				await apiRequest(`/scraps/${scrapId}`, { method: 'DELETE' });
				scrapId = null;
				successMessageKey = 'toast.scrap.removed';
				successOpen = true;
			} else {
				const created = await apiRequest<{ id: string }>('/scraps', {
					method: 'POST',
					body: { item_type: 'trend', item_id: detail.id },
				});
				scrapId = created.id;
				successMessageKey = 'toast.scrap.added';
				successOpen = true;
			}
		} catch (error) {
			if (error instanceof QuotaExceededRequestError) {
				quotaFeature = error.quotaType;
				quotaLimit = error.limit;
				quotaResetTime = error.resetAt;
				quotaOpen = true;
			} else if (error instanceof PlanGateRequestError) {
				planGateRequired = error.requiredPlan;
				planGateUpgradeUrl = error.upgradeUrl ?? '/pricing';
				planGateOpen = true;
			} else if (error instanceof ApiRequestError) {
				errorCode = error.errorCode;
				errorMessageKey = 'error.server';
				errorOpen = true;
			} else {
				errorCode = 'ERR_NETWORK';
				errorMessageKey = 'error.network';
				errorOpen = true;
			}
		} finally {
			scrapToggling = false;
		}
	}

	async function handleShare(): Promise<void> {
		if (navigator.share && detail) {
			await navigator.share({ title: detail.title, url: window.location.href });
		} else {
			await navigator.clipboard.writeText(window.location.href);
		}
	}

	onMount(() => {
		loadDetail();
		loadForecast();
		loadScrapState();
	});

	const formattedDate = $derived(
		detail ? new Date(detail.created_at).toLocaleDateString('ko-KR', {
			year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit'
		}) : ''
	);
</script>

<!-- Fixed action bar (bottom) -->
{#if detail}
	<div class="fixed bottom-0 left-0 right-0 z-40 border-t border-gray-200 dark:border-gray-700 bg-white/95 dark:bg-gray-900/95 backdrop-blur-sm px-4 py-3 flex items-center justify-between md:hidden">
		<a
			href="/trends/{detail.id}/insights"
			class="flex items-center gap-1.5 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
		>
			<Lightbulb size={14} />
			{$t('trend.detail.insights')}
		</a>
		<div class="flex items-center gap-2">
			<button
				type="button"
				onclick={handleShare}
				class="rounded-md border border-gray-200 dark:border-gray-700 px-3 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800"
			>
				<Share2 size={14} />
			</button>
			<button
				type="button"
				onclick={toggleScrap}
				disabled={scrapToggling}
				aria-label={scrapId ? $t('trend.detail.scrap_remove') : $t('trend.detail.scrap_add')}
				aria-pressed={scrapId !== null}
				class="rounded-md border border-gray-200 dark:border-gray-700 px-3 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50 {scrapId ? 'text-blue-600 dark:text-blue-400' : 'text-gray-600 dark:text-gray-400'}"
			>
				<Bookmark size={14} fill={scrapId ? 'currentColor' : 'none'} />
			</button>
		</div>
	</div>
{/if}

<div class="space-y-6 pb-20 md:pb-0">
	<a href="/trends" class="inline-flex items-center gap-1 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300">
		<ArrowLeft size={16} />
		{$t('nav.sidebar.trends')}
	</a>

	{#if isLoading}
		<p class="text-gray-500">{$t('status.loading')}</p>
	{:else if detail}
		<!-- Header card -->
		<div class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-6">
			<div class="flex items-start justify-between gap-4">
				<div class="flex-1">
					<div class="flex items-center gap-3 flex-wrap">
						<h1 class="text-xl font-bold text-gray-900 dark:text-gray-100">{detail.title}</h1>
						<EarlyBadge score={detail.early_trend_score} />
						<DirectionBadge direction={detail.direction} />
					</div>
					<div class="mt-2 flex items-center gap-4 text-sm text-gray-500 dark:text-gray-400 flex-wrap">
						<span>{$t('trend.category')}: {detail.category}</span>
						<span>{formattedDate}</span>
						<span>{$t('trend.score')}: {detail.score.toFixed(1)}</span>
					</div>
				</div>
				<!-- Desktop action buttons -->
				<div class="hidden md:flex items-center gap-2 flex-shrink-0">
					<button type="button" onclick={handleShare} class="rounded-md border border-gray-200 dark:border-gray-700 px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 flex items-center gap-1.5">
						<Share2 size={14} />
						{$t('trend.detail.share')}
					</button>
					<a
						href="/trends/{detail.id}/insights"
						class="flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
					>
						<Lightbulb size={14} />
						{$t('trend.detail.insights')}
					</a>
				</div>
			</div>

			{#if detail.summary}
				<div class="mt-4 rounded-md bg-gray-50 dark:bg-gray-700 p-4">
					<p class="text-sm text-gray-700 dark:text-gray-300">{detail.summary}</p>
				</div>
			{/if}

			<div class="mt-4 flex flex-wrap gap-1.5">
				{#each detail.keywords as keyword}
					<span class="inline-flex rounded-md bg-blue-50 dark:bg-blue-900/20 px-2 py-0.5 text-xs text-blue-700 dark:text-blue-400">
						#{keyword}
					</span>
				{/each}
			</div>
		</div>

		<!-- "Why Now" + BurstGauge side by side -->
		<div class="grid grid-cols-1 md:grid-cols-3 gap-4">
			<div class="md:col-span-2 rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/20 p-5">
				<div class="flex items-center gap-2 mb-2">
					<Lightbulb size={16} class="text-amber-600 dark:text-amber-400" />
					<h2 class="text-sm font-semibold text-amber-800 dark:text-amber-300">{$t('trend.detail.why_now')}</h2>
				</div>
				<p class="text-xs text-amber-700 dark:text-amber-400 mb-3">{$t('trend.detail.why_now.desc')}</p>
				<div class="flex flex-wrap gap-1.5">
					{#each detail.keywords.slice(0, 5) as kw}
						<span class="bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 rounded-full px-2.5 py-0.5 text-xs font-medium">
							#{kw}
						</span>
					{/each}
				</div>
				{#if detail.direction === 'rising'}
					<p class="mt-3 text-xs text-amber-600 dark:text-amber-400 font-medium">
						📈 {$t('filter.direction.rising')} — {$t('dashboard.early_trends.desc2')}
					</p>
				{/if}
			</div>
			<div class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-5 flex flex-col items-center justify-center">
				<p class="text-xs text-gray-500 dark:text-gray-400 mb-2 font-medium">{$t('trend.detail.burst_score')}</p>
				<BurstGauge score={burstScore} />
			</div>
		</div>

		<!-- Trend Chart (first) -->
		<TrendChart groupId={detail.id} />

		<!-- Sentiment + Aspect -->
		<SentimentChart groupId={detail.id} />
		<AspectSentimentChart groupId={detail.id} />

		<!-- Keyword charts -->
		<KeywordTimeline groupId={detail.id} />
		<KeywordGraph groupId={detail.id} />

		<!-- Forecast (last chart) -->
		{#if isForecastLoading}
			<div class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4">
				<p class="text-sm text-gray-400">{$t('status.loading')}</p>
			</div>
		{:else if forecastData.length > 0}
			<ForecastChart data={forecastData} />
		{/if}

		<!-- Inline Insights preview -->
		<div class="rounded-lg border border-blue-100 dark:border-blue-800 bg-blue-50 dark:bg-blue-950/20 p-5">
			<div class="flex items-center justify-between mb-3">
				<div class="flex items-center gap-2">
					<Lightbulb size={16} class="text-blue-600 dark:text-blue-400" />
					<h2 class="text-sm font-semibold text-blue-800 dark:text-blue-200">{$t('trend.detail.insights')}</h2>
				</div>
				<a
					href="/trends/{detail.id}/insights"
					class="text-xs text-blue-600 dark:text-blue-400 hover:underline font-medium"
				>
					{$t('trend.detail.insights')} 전체 보기 →
				</a>
			</div>
			<p class="text-xs text-blue-600 dark:text-blue-400 mb-3">AI가 역할에 맞는 액션 인사이트를 제공합니다. Pro 플랜에서 이용 가능합니다.</p>
			<a
				href="/trends/{detail.id}/insights"
				class="inline-flex items-center gap-1.5 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
			>
				<Lightbulb size={14} />
				{$t('trend.detail.insights')} 보기
			</a>
		</div>

		<!-- Articles section with tabs -->
		<div>
			<div class="flex items-center justify-between mb-3">
				<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">
					{$t('trend.detail.articles')} ({detail.articles.length})
				</h2>
				<div class="flex rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
					<button
						type="button"
						class="px-3 py-1.5 text-xs font-medium transition-colors {articleTab === 'all' ? 'bg-blue-600 text-white' : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700'}"
						onclick={() => { articleTab = 'all'; }}
					>
						{$t('trend.detail.articles.tab_all')}
					</button>
					<button
						type="button"
						class="px-3 py-1.5 text-xs font-medium transition-colors {articleTab === 'by_source' ? 'bg-blue-600 text-white' : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700'}"
						onclick={() => { articleTab = 'by_source'; }}
					>
						{$t('trend.detail.articles.tab_by_source')}
					</button>
				</div>
			</div>

			{#if articleTab === 'all'}
				<div class="space-y-2">
					{#each detail.articles as article (article.id)}
						<a
							href={article.url}
							target="_blank"
							rel="noopener noreferrer"
							class="flex items-start gap-3 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 hover:shadow-sm transition-shadow"
						>
							<div class="flex-1 min-w-0">
								<div class="flex items-center gap-2">
									<p class="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{article.title}</p>
									<ExternalLink size={12} class="text-gray-400 shrink-0" />
								</div>
								{#if article.body_snippet}
									<p class="mt-1 text-xs text-gray-500 dark:text-gray-400 line-clamp-2">{article.body_snippet}</p>
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
			{:else}
				<div class="space-y-4">
					{#each [...articlesBySource.entries()] as [source, articles]}
						{@const isExpanded = expandedSources.has(source)}
						{@const COLLAPSE_THRESHOLD = 3}
						{@const shouldCollapse = articles.length > COLLAPSE_THRESHOLD && !isExpanded}
						{@const visibleArticles = shouldCollapse ? articles.slice(0, 1) : articles}
						<div>
							<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2 flex items-center gap-2">
								<span class="w-2 h-2 rounded-full bg-blue-500 inline-block"></span>
								{source} ({articles.length})
							</h3>
							<div class="space-y-2">
								{#each visibleArticles as article (article.id)}
									<a
										href={article.url}
										target="_blank"
										rel="noopener noreferrer"
										class="flex items-center gap-2 rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 hover:shadow-sm transition-shadow"
									>
										<p class="text-sm text-gray-900 dark:text-gray-100 truncate flex-1">{article.title}</p>
										<ExternalLink size={12} class="text-gray-400 shrink-0" />
									</a>
								{/each}
								{#if shouldCollapse}
									<button
										type="button"
										onclick={() => {
											const next = new Set(expandedSources);
											next.add(source);
											expandedSources = next;
										}}
										class="w-full text-xs text-blue-500 dark:text-blue-400 hover:underline py-1 text-left px-1"
									>
										외 {articles.length - 1}건 더보기
									</button>
								{/if}
							</div>
						</div>
					{/each}
				</div>
			{/if}
		</div>
	{:else}
		<p class="text-gray-500">{$t('status.no_results')}</p>
	{/if}
</div>

<PlanGate open={planGateOpen} requiredPlan={planGateRequired} upgradeUrl={planGateUpgradeUrl} onClose={() => (planGateOpen = false)} />
<ErrorModal open={errorOpen} errorCode={errorCode} messageKey={errorMessageKey} onClose={() => (errorOpen = false)} onRetry={() => { errorOpen = false; loadDetail(); }} />
<SuccessToast open={successOpen} messageKey={successMessageKey} onClose={() => (successOpen = false)} />
<QuotaExceededModal open={quotaOpen} feature={quotaFeature} limit={quotaLimit} resetTime={quotaResetTime} onClose={() => (quotaOpen = false)} />
