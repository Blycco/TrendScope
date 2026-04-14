<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { apiRequest, ApiRequestError, PlanGateRequestError } from '$lib/api';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';
	import PlanGate from '$lib/ui/PlanGate.svelte';
	import PageStateWrapper from '$lib/ui/PageStateWrapper.svelte';
	import EmptyState from '$lib/ui/EmptyState.svelte';
	import EarlyBadge from '../../../components/EarlyBadge.svelte';
	import PlanBadge from '$lib/ui/PlanBadge.svelte';
	import { Zap } from 'lucide-svelte';

	interface EarlyTrend {
		id: string;
		title: string;
		category: string;
		score: number;
		early_trend_score: number;
		keywords: string[];
		created_at: string;
	}

	interface EarlyListResponse {
		items: EarlyTrend[];
		next_cursor: string | null;
		total: number;
	}

	let items = $state<EarlyTrend[]>([]);
	let isLoading = $state(true);
	let cursor = $state<string | null>(null);
	let isLoadingMore = $state(false);

	let errorOpen = $state(false);
	let errorCode = $state('');
	let errorMessageKey = $state('');
	let planGateOpen = $state(false);
	let planGateRequired = $state('pro');
	let planGateUpgradeUrl = $state('/pricing');

	async function loadEarly(append = false): Promise<void> {
		if (append) {
			isLoadingMore = true;
		} else {
			isLoading = true;
		}
		try {
			const qs = new URLSearchParams({ limit: '20' });
			if (append && cursor) qs.set('cursor', cursor);
			const data = await apiRequest<EarlyListResponse>(`/trends/early/pro?${qs.toString()}`);
			items = append ? [...items, ...data.items] : data.items;
			cursor = data.next_cursor;
		} catch (error) {
			if (error instanceof PlanGateRequestError) {
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
			isLoading = false;
			isLoadingMore = false;
		}
	}

	onMount(() => {
		loadEarly();
	});
</script>

<div class="space-y-6">
	<div>
		<div class="flex items-center gap-2">
			<Zap size={20} class="text-amber-500" />
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{$t('early_trends.title')}</h1>
			<PlanBadge plan="pro" />
		</div>
		<p class="mt-1 text-sm text-gray-500 dark:text-gray-400">{$t('early_trends.desc')}</p>
	</div>

	<PageStateWrapper {isLoading} isEmpty={!isLoading && items.length === 0}>
		{#snippet empty()}
			<EmptyState titleKey="early_trends.empty.title" descriptionKey="early_trends.empty.desc" />
		{/snippet}
		{#snippet children()}
			<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
				{#each items as item (item.id)}
					<a
						href="/trends/{item.id}"
						class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 hover:border-blue-500 transition-colors"
					>
						<div class="flex items-start justify-between gap-2">
							<h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 line-clamp-2">{item.title}</h3>
							<EarlyBadge score={item.early_trend_score} />
						</div>
						<p class="mt-2 text-xs text-gray-500 dark:text-gray-400">{item.category}</p>
						{#if item.keywords.length > 0}
							<div class="mt-2 flex flex-wrap gap-1">
								{#each item.keywords.slice(0, 4) as kw}
									<span class="inline-flex items-center rounded-full bg-gray-100 dark:bg-gray-700 px-2 py-0.5 text-xs text-gray-600 dark:text-gray-300">
										#{kw}
									</span>
								{/each}
							</div>
						{/if}
					</a>
				{/each}
			</div>

			{#if cursor}
				<div class="mt-6 flex justify-center">
					<button
						type="button"
						onclick={() => loadEarly(true)}
						disabled={isLoadingMore}
						class="rounded-md border border-gray-200 dark:border-gray-700 px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50"
					>
						{isLoadingMore ? $t('status.loading') : $t('early_trends.load_more')}
					</button>
				</div>
			{/if}
		{/snippet}
	</PageStateWrapper>
</div>

<ErrorModal open={errorOpen} errorCode={errorCode} messageKey={errorMessageKey} onClose={() => (errorOpen = false)} />
<PlanGate open={planGateOpen} requiredPlan={planGateRequired} upgradeUrl={planGateUpgradeUrl} onClose={() => (planGateOpen = false)} />
