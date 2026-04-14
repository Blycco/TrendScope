<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { apiRequest, ApiRequestError, PlanGateRequestError } from '$lib/api';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';
	import PlanGate from '$lib/ui/PlanGate.svelte';
	import PageStateWrapper from '$lib/ui/PageStateWrapper.svelte';
	import { AlertTriangle, CheckCircle2, ArrowLeft } from 'lucide-svelte';

	interface BrandMention {
		text: string;
		label: string;
		score: number;
	}

	interface BrandMonitorResponse {
		brand_name: string;
		current_score: number;
		mean_24h: number;
		std_24h: number;
		z_score: number;
		alert_threshold: number;
		is_crisis: boolean;
		label: string;
		cached: boolean;
		mentions: BrandMention[];
	}

	const brandName = $derived(($page.params as Record<string, string>).name ?? '');
	let monitor = $state<BrandMonitorResponse | null>(null);
	let isLoading = $state(true);

	let errorOpen = $state(false);
	let errorCode = $state('');
	let errorMessageKey = $state('');
	let planGateOpen = $state(false);
	let planGateRequired = $state('business');
	let planGateUpgradeUrl = $state('/pricing');

	async function loadMonitor(): Promise<void> {
		isLoading = true;
		try {
			monitor = await apiRequest<BrandMonitorResponse>(
				`/brand/${encodeURIComponent(brandName)}/monitor`
			);
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
		}
	}

	function labelColor(label: string): string {
		if (label === 'positive') return 'text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/20';
		if (label === 'negative') return 'text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20';
		return 'text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-900/20';
	}

	onMount(() => {
		loadMonitor();
	});
</script>

<div class="space-y-6">
	<a href="/brand" class="inline-flex items-center gap-1 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200">
		<ArrowLeft size={16} />
		{$t('brand.back')}
	</a>

	<PageStateWrapper {isLoading} isEmpty={!isLoading && !monitor}>
		{#snippet children()}
			{#if monitor}
				<div>
					<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{monitor.brand_name}</h1>
					<p class="mt-1 text-sm text-gray-500 dark:text-gray-400">{$t('brand.monitor.desc')}</p>
				</div>

				{#if monitor.is_crisis}
					<div class="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 p-4 flex items-start gap-3">
						<AlertTriangle size={20} class="text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
						<div>
							<h2 class="text-sm font-semibold text-red-900 dark:text-red-100">{$t('brand.monitor.crisis_title')}</h2>
							<p class="mt-1 text-xs text-red-700 dark:text-red-300">{$t('brand.monitor.crisis_desc')}</p>
						</div>
					</div>
				{:else}
					<div class="rounded-lg border border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/20 p-4 flex items-start gap-3">
						<CheckCircle2 size={20} class="text-green-600 dark:text-green-400 flex-shrink-0 mt-0.5" />
						<div>
							<h2 class="text-sm font-semibold text-green-900 dark:text-green-100">{$t('brand.monitor.stable_title')}</h2>
							<p class="mt-1 text-xs text-green-700 dark:text-green-300">{$t('brand.monitor.stable_desc')}</p>
						</div>
					</div>
				{/if}

				<div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
					<div class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4">
						<p class="text-xs text-gray-500 dark:text-gray-400">{$t('brand.monitor.current_score')}</p>
						<p class="mt-1 text-xl font-bold text-gray-900 dark:text-gray-100">{monitor.current_score.toFixed(2)}</p>
					</div>
					<div class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4">
						<p class="text-xs text-gray-500 dark:text-gray-400">{$t('brand.monitor.mean_24h')}</p>
						<p class="mt-1 text-xl font-bold text-gray-900 dark:text-gray-100">{monitor.mean_24h.toFixed(2)}</p>
					</div>
					<div class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4">
						<p class="text-xs text-gray-500 dark:text-gray-400">{$t('brand.monitor.z_score')}</p>
						<p class="mt-1 text-xl font-bold" class:text-red-600={monitor.is_crisis} class:text-gray-900={!monitor.is_crisis} class:dark:text-red-400={monitor.is_crisis} class:dark:text-gray-100={!monitor.is_crisis}>
							{monitor.z_score.toFixed(2)}
						</p>
						<p class="text-xs text-gray-400 dark:text-gray-500">{$t('brand.monitor.threshold')}: {monitor.alert_threshold.toFixed(2)}</p>
					</div>
					<div class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4">
						<p class="text-xs text-gray-500 dark:text-gray-400">{$t('brand.monitor.label')}</p>
						<span class="mt-1 inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium {labelColor(monitor.label)}">
							{monitor.label}
						</span>
					</div>
				</div>

				{#if monitor.mentions.length > 0}
					<div>
						<h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">{$t('brand.monitor.mentions')}</h2>
						<div class="space-y-2">
							{#each monitor.mentions as mention, i (i)}
								<div class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-3 flex items-start justify-between gap-3">
									<p class="text-sm text-gray-700 dark:text-gray-300 flex-1">{mention.text}</p>
									<div class="flex-shrink-0 text-right">
										<span class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium {labelColor(mention.label)}">
											{mention.label}
										</span>
										<p class="mt-1 text-xs text-gray-400 dark:text-gray-500">{mention.score.toFixed(2)}</p>
									</div>
								</div>
							{/each}
						</div>
					</div>
				{/if}

				{#if monitor.cached}
					<p class="text-xs text-gray-400 dark:text-gray-500">{$t('brand.monitor.cached')}</p>
				{/if}
			{/if}
		{/snippet}
	</PageStateWrapper>
</div>

<ErrorModal open={errorOpen} errorCode={errorCode} messageKey={errorMessageKey} onClose={() => (errorOpen = false)} />
<PlanGate open={planGateOpen} requiredPlan={planGateRequired} upgradeUrl={planGateUpgradeUrl} onClose={() => (planGateOpen = false)} />
