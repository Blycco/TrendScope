<script lang="ts">
	import { t } from 'svelte-i18n';
	import { authStore } from '$lib/stores/auth.svelte';
	import { apiRequest, ApiRequestError } from '$lib/api';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';
	import { Check } from 'lucide-svelte';

	let errorOpen = $state(false);
	let errorCode = $state('');
	let errorMessageKey = $state('');
	let loadingPlan = $state<string | null>(null);

	const plans = [
		{
			key: 'free',
			nameKey: 'pricing.free',
			price: 0,
			features: [
				'pricing.feature.trend_feed',
				'pricing.feature.news_feed',
				'pricing.feature.basic_insights',
			],
		},
		{
			key: 'pro',
			nameKey: 'pricing.pro',
			price: 9900,
			features: [
				'pricing.feature.trend_feed',
				'pricing.feature.news_feed',
				'pricing.feature.advanced_insights',
				'pricing.feature.keyword_tracker',
				'pricing.feature.quota_10x',
			],
		},
		{
			key: 'business',
			nameKey: 'pricing.business',
			price: 29900,
			features: [
				'pricing.feature.trend_feed',
				'pricing.feature.news_feed',
				'pricing.feature.advanced_insights',
				'pricing.feature.keyword_tracker',
				'pricing.feature.quota_unlimited',
				'pricing.feature.admin_panel',
				'pricing.feature.api_access',
			],
		},
	] as const;

	async function handleUpgrade(planKey: string): Promise<void> {
		loadingPlan = planKey;
		try {
			const data = await apiRequest<{ checkout_url: string }>('/subscriptions/checkout', {
				method: 'POST',
				body: { plan: planKey },
			});
			window.location.href = data.checkout_url;
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
			loadingPlan = null;
		}
	}

	function isCurrentPlan(planKey: string): boolean {
		return authStore.user?.plan === planKey;
	}
</script>

<div class="space-y-8">
	<div class="text-center">
		<h1 class="text-2xl sm:text-3xl font-bold text-gray-900">{$t('pricing.title')}</h1>
	</div>

	<div class="grid grid-cols-1 gap-4 sm:gap-6 md:grid-cols-3 px-1 sm:px-0">
		{#each plans as plan}
			<div
				class="relative rounded-xl border border-gray-200 bg-white p-4 sm:p-6 shadow-sm flex flex-col"
				class:ring-2={plan.key === 'pro'}
				class:ring-blue-500={plan.key === 'pro'}
			>
				{#if isCurrentPlan(plan.key)}
					<span class="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-green-500 px-3 py-1 text-xs font-semibold text-white">
						{$t('pricing.current_plan')}
					</span>
				{/if}

				<div class="mb-4">
					<h2 class="text-xl font-bold text-gray-900">{$t(plan.nameKey)}</h2>
					<div class="mt-2">
						{#if plan.price === 0}
							<span class="text-2xl sm:text-3xl font-bold text-gray-900">₩0</span>
						{:else}
							<span class="text-2xl sm:text-3xl font-bold text-gray-900">₩{plan.price.toLocaleString()}</span>
							<span class="text-sm text-gray-500">{$t('pricing.per_month')}</span>
						{/if}
					</div>
				</div>

				<ul class="mb-4 sm:mb-6 space-y-1.5 sm:space-y-2 flex-1">
					{#each plan.features as featureKey}
						<li class="flex items-center gap-2 text-sm text-gray-700">
							<Check size={16} class="shrink-0 text-green-500" />
							{$t(featureKey)}
						</li>
					{/each}
				</ul>

				{#if isCurrentPlan(plan.key)}
					<button
						disabled
						class="w-full rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-400 cursor-not-allowed"
					>
						{$t('pricing.current_plan')}
					</button>
				{:else}
					<button
						onclick={() => handleUpgrade(plan.key)}
						disabled={loadingPlan === plan.key}
						class="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
					>
						{#if loadingPlan === plan.key}
							{$t('status.loading')}
						{:else}
							{$t('pricing.cta_upgrade')}
						{/if}
					</button>
				{/if}
			</div>
		{/each}
	</div>
</div>

<ErrorModal
	open={errorOpen}
	errorCode={errorCode}
	messageKey={errorMessageKey}
	onClose={() => (errorOpen = false)}
/>
