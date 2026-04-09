<script lang="ts">
	import { t } from 'svelte-i18n';
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	import { apiRequest, ApiRequestError, PlanGateRequestError } from '$lib/api';
	import type { InsightResponse, InsightContent } from '$lib/api';
	import { authStore } from '$lib/stores/auth.svelte';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';
	import PlanGate from '$lib/ui/PlanGate.svelte';
	import PageStateWrapper from '$lib/ui/PageStateWrapper.svelte';
	import { Copy, Check, ArrowLeft, Lightbulb } from 'lucide-svelte';

	let insight = $state<InsightResponse | null>(null);
	let isLoading = $state(true);
	let copiedKey = $state<string | null>(null);

	let errorOpen = $state(false);
	let errorCode = $state('');
	let errorMessageKey = $state('');

	let planGateOpen = $state(false);
	let requiredPlan = $state('pro');

	const groupId = $derived(page.params.id ?? '');
	const userRole = $derived(authStore.user?.role ?? 'general');
	const displayKeyword = $derived(insight?.keyword ?? '');

	async function loadInsight(): Promise<void> {
		try {
			const data = await apiRequest<InsightResponse>(
				`/trends/${encodeURIComponent(groupId)}/insights?role=${userRole}`
			);
			insight = data;
		} catch (error) {
			if (error instanceof PlanGateRequestError) {
				requiredPlan = error.requiredPlan;
				planGateOpen = true;
			} else if (error instanceof ApiRequestError) {
				errorCode = error.errorCode;
				errorMessageKey = error.status === 401 ? 'error.auth_required' : 'error.server';
				errorOpen = true;
			} else {
				errorCode = 'ERR_NETWORK';
				errorMessageKey = 'error.network';
				errorOpen = true;
			}
		}
	}

	async function copyText(key: string, text: string): Promise<void> {
		await navigator.clipboard.writeText(text);
		copiedKey = key;
		setTimeout(() => { copiedKey = null; }, 2000);
	}

	function getSections(content: InsightContent): { key: string; label: string; items: string[] }[] {
		if ('ad_opportunities' in content) {
			return [
				{ key: 'ad_opportunities', label: $t('insights.marketer.actions'), items: content.ad_opportunities },
			];
		}
		if ('title_drafts' in content) {
			return [
				{ key: 'title_drafts', label: $t('insights.creator.titles'), items: content.title_drafts },
				{ key: 'seo_keywords', label: $t('insights.creator.hashtags'), items: content.seo_keywords },
			];
		}
		if ('consumer_reactions' in content) {
			return [
				{ key: 'consumer_reactions', label: $t('insights.owner.sentiment'), items: content.consumer_reactions },
				{ key: 'product_hints', label: $t('insights.owner.product'), items: content.product_hints },
				{ key: 'market_ops', label: $t('insights.owner.opportunity'), items: content.market_ops },
			];
		}
		if ('sns_drafts' in content) {
			return [
				{ key: 'sns_drafts', label: $t('insights.common.sns_draft'), items: content.sns_drafts },
				{ key: 'engagement_methods', label: $t('insights.creator.actions'), items: content.engagement_methods },
			];
		}
		return [];
	}

	onMount(async () => {
		await loadInsight();
		isLoading = false;
	});
</script>

<div class="space-y-6">
	<div>
		<a href="/trends/{groupId}" class="inline-flex items-center gap-1 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300">
			<ArrowLeft size={14} />
			{$t('nav.sidebar.trends')}
		</a>
		<div class="mt-2 flex items-center gap-2">
			<Lightbulb size={20} class="text-blue-500" />
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{$t('page.insights.title')}</h1>
		</div>
		{#if displayKeyword}
			<p class="mt-1 text-gray-600 dark:text-gray-400 text-sm">{displayKeyword}</p>
		{/if}
	</div>

	<PageStateWrapper {isLoading} isEmpty={!isLoading && insight === null && !planGateOpen && !errorOpen}>
		{#snippet children()}
			{#if insight}
				<div class="space-y-4">
					<!-- Role header -->
					{#if insight.degraded}
						<div class="rounded-md bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800 px-4 py-2 text-xs text-amber-700 dark:text-amber-400">
							AI 응답 품질이 낮아 기본 인사이트를 제공합니다.
						</div>
					{/if}

					<!-- Insight sections with copy buttons -->
					{#each getSections(insight.content) as section (section.key)}
						<div class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-5">
							<div class="flex items-center justify-between mb-3">
								<h3 class="text-sm font-semibold text-gray-800 dark:text-gray-200">{section.label}</h3>
								<button
									type="button"
									onclick={() => copyText(section.key, section.items.join('\n'))}
									class="flex items-center gap-1 text-xs text-gray-400 dark:text-gray-500 hover:text-blue-600 dark:hover:text-blue-400 transition-colors px-2 py-1 rounded hover:bg-gray-50 dark:hover:bg-gray-700"
								>
									{#if copiedKey === section.key}
										<Check size={12} class="text-green-500" />
										<span class="text-green-500">{$t('insights.copied')}</span>
									{:else}
										<Copy size={12} />
										{$t('insights.copy')}
									{/if}
								</button>
							</div>
							<ul class="space-y-2">
								{#each section.items as item, i}
									<li class="flex items-start gap-2 group">
										<span class="flex-shrink-0 w-5 h-5 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 text-xs flex items-center justify-center font-medium mt-0.5">
											{i + 1}
										</span>
										<div class="flex-1 flex items-start justify-between gap-2">
											<p class="text-sm text-gray-700 dark:text-gray-300">{item}</p>
											<button
												type="button"
												onclick={() => copyText(`${section.key}_${i}`, item)}
												class="flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity text-gray-300 hover:text-blue-500 dark:text-gray-600 dark:hover:text-blue-400"
											>
												{#if copiedKey === `${section.key}_${i}`}
													<Check size={12} class="text-green-500" />
												{:else}
													<Copy size={12} />
												{/if}
											</button>
										</div>
									</li>
								{/each}
							</ul>
						</div>
					{/each}

					<!-- Creator timing info -->
					{#if 'timing' in insight.content && insight.content.timing}
						<div class="rounded-lg border border-purple-100 dark:border-purple-800 bg-purple-50 dark:bg-purple-950/20 p-4">
							<p class="text-xs font-semibold text-purple-700 dark:text-purple-400 mb-1">{$t('insights.creator.timing')}</p>
							<p class="text-sm text-purple-700 dark:text-purple-300">{insight.content.timing}</p>
						</div>
					{/if}

					<!-- SNS Draft copy block for creator/general -->
					{#if 'sns_drafts' in insight.content && insight.content.sns_drafts.length > 0}
						<div class="rounded-lg border border-green-100 dark:border-green-800 bg-green-50 dark:bg-green-950/20 p-4">
							<div class="flex items-center justify-between mb-2">
								<p class="text-xs font-semibold text-green-700 dark:text-green-400">{$t('insights.common.sns_draft')}</p>
								<button
									type="button"
									onclick={() => copyText('sns_all', insight!.content && 'sns_drafts' in insight!.content ? insight!.content.sns_drafts.join('\n\n') : '')}
									class="flex items-center gap-1 text-xs text-green-600 dark:text-green-400 hover:underline"
								>
									{#if copiedKey === 'sns_all'}
										<Check size={12} />
										{$t('insights.copied')}
									{:else}
										<Copy size={12} />
										{$t('insights.copy')}
									{/if}
								</button>
							</div>
							{#each insight.content.sns_drafts as draft}
								<p class="text-sm text-green-800 dark:text-green-200 mb-2 leading-relaxed">{draft}</p>
							{/each}
						</div>
					{/if}

					<!-- Source URLs -->
					{#if 'source_urls' in insight.content && (insight.content as { source_urls: string[] }).source_urls.length > 0}
						<div class="rounded-lg border border-gray-100 dark:border-gray-800 bg-gray-50 dark:bg-gray-900/50 p-4">
							<p class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">Sources</p>
							<div class="flex flex-wrap gap-2">
								{#each (insight.content as { source_urls: string[] }).source_urls as url, i}
									<a
										href={url}
										target="_blank"
										rel="noopener noreferrer"
										class="text-xs text-blue-600 dark:text-blue-400 hover:underline"
									>
										[{i + 1}]
									</a>
								{/each}
							</div>
						</div>
					{/if}

					<p class="text-xs text-gray-400 dark:text-gray-500 text-right">
						{$t('insight.generated_at', { values: { date: new Date(insight.generated_at).toLocaleString() } })}
						{insight.cached ? ' (캐시됨)' : ''}
					</p>
				</div>
			{/if}
		{/snippet}
	</PageStateWrapper>
</div>

<ErrorModal open={errorOpen} errorCode={errorCode} messageKey={errorMessageKey} onClose={() => (errorOpen = false)} onRetry={() => { errorOpen = false; loadInsight(); }} />
<PlanGate open={planGateOpen} requiredPlan={requiredPlan} onClose={() => (planGateOpen = false)} />
