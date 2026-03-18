<script lang="ts">
	import { t } from 'svelte-i18n';
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	import { apiRequest, ApiRequestError, PlanGateRequestError } from '$lib/api';
	import type { InsightResponse } from '$lib/api';
	import { authStore } from '$lib/stores/auth';
	import ActionPointCard from '../../../../components/ActionPointCard.svelte';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';
	import PlanGate from '$lib/ui/PlanGate.svelte';

	let insight = $state<InsightResponse | null>(null);
	let isLoading = $state(true);

	let errorOpen = $state(false);
	let errorCode = $state('');
	let errorMessageKey = $state('');

	let planGateOpen = $state(false);
	let requiredPlan = $state('pro');

	const keyword = $derived(page.params.id ?? '');
	const userRole = $derived(authStore.user?.role ?? 'general');

	async function loadInsight(): Promise<void> {
		try {
			const data = await apiRequest<InsightResponse>(
				`/trends/${encodeURIComponent(keyword)}/insights?role=${userRole}`
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

	onMount(async () => {
		await loadInsight();
		isLoading = false;
	});
</script>

<div class="space-y-6">
	<div>
		<a href="/trends" class="text-sm text-blue-600 hover:underline">&larr; {$t('page.trends.title')}</a>
		<h1 class="mt-2 text-2xl font-bold text-gray-900">{$t('page.insights.title')}</h1>
		<p class="text-gray-600">{keyword}</p>
	</div>

	{#if isLoading}
		<p class="text-gray-500">{$t('status.loading')}</p>
	{:else if insight}
		<ActionPointCard {insight} />
	{:else if !planGateOpen && !errorOpen}
		<p class="text-gray-500">{$t('status.no_results')}</p>
	{/if}
</div>

<ErrorModal open={errorOpen} errorCode={errorCode} messageKey={errorMessageKey} onClose={() => (errorOpen = false)} onRetry={() => { errorOpen = false; loadInsight(); }} />
<PlanGate open={planGateOpen} requiredPlan={requiredPlan} onClose={() => (planGateOpen = false)} />
