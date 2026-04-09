<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount, onDestroy } from 'svelte';
	import { adminRequest } from '$lib/api/admin';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';

	interface PipelineStats {
		collected: number;
		spam_filtered: number;
		clustered: number;
		trends_created: number;
		filter_reasons: { ad: number; obituary: number; other: number };
	}

	interface TrendItem {
		id: string;
		title: string;
		score: number;
		burst_score: number;
		article_count: number;
		category: string;
		locale: string;
		created_at: string;
	}

	let stats = $state<PipelineStats | null>(null);
	let trends = $state<TrendItem[]>([]);
	let statsLoading = $state(true);
	let trendsLoading = $state(true);
	let hiddenIds = $state<Set<string>>(new Set());
	let errorOpen = $state(false);
	let errorCode = $state('');

	async function fetchStats(): Promise<void> {
		try {
			stats = await adminRequest<PipelineStats>('/trend-quality/pipeline-stats');
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		} finally {
			statsLoading = false;
		}
	}

	async function fetchTopTrends(): Promise<void> {
		try {
			const res = await adminRequest<{ trends: TrendItem[] }>('/trend-quality/top-trends');
			trends = res.trends;
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		} finally {
			trendsLoading = false;
		}
	}

	async function hideTrend(id: string): Promise<void> {
		try {
			await adminRequest(`/trend-quality/hide/${id}`, { method: 'POST' });
			hiddenIds = new Set([...hiddenIds, id]);
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		}
	}

	let statsInterval: ReturnType<typeof setInterval>;
	let trendsInterval: ReturnType<typeof setInterval>;

	onMount(() => {
		fetchStats();
		fetchTopTrends();
		statsInterval = setInterval(fetchStats, 30_000);
		trendsInterval = setInterval(fetchTopTrends, 60_000);
	});

	onDestroy(() => {
		clearInterval(statsInterval);
		clearInterval(trendsInterval);
	});
</script>

<div class="max-w-5xl">
	<div class="flex items-center justify-between mb-6">
		<h2 class="text-2xl font-bold text-gray-900 dark:text-gray-100">
			{$t('admin.trend_quality.title')}
		</h2>
		<span class="text-xs text-gray-400 dark:text-gray-500">{$t('admin.trend_quality.auto_refresh')}</span>
	</div>

	<!-- Pipeline Stats -->
	<section class="mb-8 bg-white dark:bg-gray-800 rounded-lg shadow p-5">
		<h3 class="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-4">
			{$t('admin.trend_quality.section_pipeline')}
		</h3>

		{#if statsLoading}
			<p class="text-gray-400 dark:text-gray-500 text-sm">Loading...</p>
		{:else if stats}
			<div class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-4">
				<div class="bg-blue-50 dark:bg-blue-900/30 rounded-lg p-4 text-center">
					<p class="text-2xl font-bold text-blue-600 dark:text-blue-400">{stats.collected}</p>
					<p class="text-xs text-gray-600 dark:text-gray-400 mt-1">{$t('admin.trend_quality.collected')}</p>
				</div>
				<div class="bg-red-50 dark:bg-red-900/30 rounded-lg p-4 text-center">
					<p class="text-2xl font-bold text-red-600 dark:text-red-400">{stats.spam_filtered}</p>
					<p class="text-xs text-gray-600 dark:text-gray-400 mt-1">{$t('admin.trend_quality.spam_filtered')}</p>
				</div>
				<div class="bg-yellow-50 dark:bg-yellow-900/30 rounded-lg p-4 text-center">
					<p class="text-2xl font-bold text-yellow-600 dark:text-yellow-400">{stats.clustered}</p>
					<p class="text-xs text-gray-600 dark:text-gray-400 mt-1">{$t('admin.trend_quality.clustered')}</p>
				</div>
				<div class="bg-green-50 dark:bg-green-900/30 rounded-lg p-4 text-center">
					<p class="text-2xl font-bold text-green-600 dark:text-green-400">{stats.trends_created}</p>
					<p class="text-xs text-gray-600 dark:text-gray-400 mt-1">{$t('admin.trend_quality.trends_created')}</p>
				</div>
			</div>

			<!-- Filter reasons bar -->
			{#if stats.spam_filtered > 0}
				<div class="flex gap-2 text-xs">
					{#each [
						{ key: 'filter_ad', count: stats.filter_reasons.ad },
						{ key: 'filter_obituary', count: stats.filter_reasons.obituary },
						{ key: 'filter_other', count: stats.filter_reasons.other }
					] as reason}
						{#if reason.count > 0}
							<span class="px-2 py-1 bg-gray-100 dark:bg-gray-700 rounded text-gray-600 dark:text-gray-300">
								{$t('admin.trend_quality.' + reason.key)}: {reason.count}
							</span>
						{/if}
					{/each}
				</div>
			{/if}
		{/if}
	</section>

	<!-- Top Trends Table -->
	<section class="mb-8 bg-white dark:bg-gray-800 rounded-lg shadow p-5">
		<h3 class="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-4">
			{$t('admin.trend_quality.section_top')}
		</h3>

		{#if trendsLoading}
			<p class="text-gray-400 dark:text-gray-500 text-sm">Loading...</p>
		{:else}
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="text-left text-xs text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
							<th class="pb-2 pr-3 w-8">{$t('admin.trend_quality.col_rank')}</th>
							<th class="pb-2 pr-3">{$t('admin.trend_quality.col_title')}</th>
							<th class="pb-2 pr-3 text-right w-16">{$t('admin.trend_quality.col_score')}</th>
							<th class="pb-2 pr-3 text-right w-16">{$t('admin.trend_quality.col_burst')}</th>
							<th class="pb-2 pr-3 text-right w-14">{$t('admin.trend_quality.col_articles')}</th>
							<th class="pb-2 pr-3 w-24">{$t('admin.trend_quality.col_category')}</th>
							<th class="pb-2 w-20 text-right">{$t('admin.trend_quality.col_actions')}</th>
						</tr>
					</thead>
					<tbody>
						{#each trends as trend, i}
							<tr class="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-750">
								<td class="py-2 pr-3 text-gray-400 dark:text-gray-500 font-mono text-xs">{i + 1}</td>
								<td class="py-2 pr-3 text-gray-800 dark:text-gray-200 max-w-xs truncate" title={trend.title}>
									{trend.title}
								</td>
								<td class="py-2 pr-3 text-right font-semibold text-blue-600 dark:text-blue-400">
									{trend.score.toFixed(1)}
								</td>
								<td class="py-2 pr-3 text-right text-orange-500 dark:text-orange-400">
									{trend.burst_score.toFixed(2)}
								</td>
								<td class="py-2 pr-3 text-right text-gray-600 dark:text-gray-400">
									{trend.article_count}
								</td>
								<td class="py-2 pr-3">
									<span class="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 rounded text-xs text-gray-600 dark:text-gray-300">
										{trend.category}
									</span>
								</td>
								<td class="py-2 text-right">
									{#if hiddenIds.has(trend.id)}
										<span class="text-xs text-gray-400 dark:text-gray-500">
											{$t('admin.trend_quality.hidden')}
										</span>
									{:else}
										<button
											class="text-xs text-red-500 hover:text-red-700 dark:hover:text-red-400"
											onclick={() => hideTrend(trend.id)}
										>
											{$t('admin.trend_quality.hide')}
										</button>
									{/if}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</section>
</div>

<ErrorModal
	open={errorOpen}
	errorCode={errorCode}
	messageKey="error.server"
	onClose={() => (errorOpen = false)}
	onRetry={() => { fetchStats(); fetchTopTrends(); }}
/>
