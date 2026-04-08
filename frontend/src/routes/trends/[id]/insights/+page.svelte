<script lang="ts">
	import { t } from 'svelte-i18n';
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	import { apiRequest, ApiRequestError, PlanGateRequestError } from '$lib/api';
	import type { InsightResponse } from '$lib/api';
	import { authStore } from '$lib/stores/auth.svelte';
	import ActionPointCard from '../../../../components/ActionPointCard.svelte';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';
	import PlanGate from '$lib/ui/PlanGate.svelte';
	import PageStateWrapper from '$lib/ui/PageStateWrapper.svelte';

	let insight = $state<InsightResponse | null>(null);
	let isLoading = $state(true);

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

	onMount(async () => {
		await loadInsight();
		isLoading = false;
	});
</script>

<div class="space-y-6">
	<div>
		<a href="/trends/{groupId}" class="text-sm text-blue-600 hover:underline">&larr; {$t('nav.sidebar.trends')}</a>
		<h1 class="mt-2 text-2xl font-bold text-gray-900">{$t('page.insights.title')}</h1>
		{#if displayKeyword}
			<p class="text-gray-600">{displayKeyword}</p>
		{/if}
	</div>

	<PageStateWrapper {isLoading} isEmpty={!isLoading && insight === null && !planGateOpen && !errorOpen}>
		{#snippet children()}
			{#if insight}
				<ActionPointCard {insight} />
			{/if}
		{/snippet}
	</PageStateWrapper>
</div>

<ErrorModal open={errorOpen} errorCode={errorCode} messageKey={errorMessageKey} onClose={() => (errorOpen = false)} onRetry={() => { errorOpen = false; loadInsight(); }} />
<PlanGate open={planGateOpen} requiredPlan={requiredPlan} onClose={() => (planGateOpen = false)} />
