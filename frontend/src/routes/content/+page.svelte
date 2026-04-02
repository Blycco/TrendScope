<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { apiRequest, ApiRequestError, PlanGateRequestError } from '$lib/api';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';
	import PlanGate from '$lib/ui/PlanGate.svelte';
	import ContentIdeaCard from '$lib/components/ContentIdeaCard.svelte';
	import { authStore } from '$lib/stores/auth.svelte';

	interface ContentIdea {
		title: string;
		hook: string;
		platform: 'youtube' | 'instagram' | 'blog' | 'newsletter';
		difficulty: 'easy' | 'medium' | 'hard';
	}

	let keyword = $state('');
	let ideas = $state<ContentIdea[]>([]);
	let isLoading = $state(false);
	let cached = $state(false);
	let errorOpen = $state(false);
	let errorCode = $state('');
	let errorMessageKey = $state('');

	let planGateOpen = $state(false);
	let planGateRequired = $state('pro');

	const isFreePlan = $derived(authStore.user?.plan === 'free');

	function showError(code: string, key: string): void {
		errorCode = code;
		errorMessageKey = key;
		errorOpen = true;
	}

	async function generateIdeas(): Promise<void> {
		if (!keyword.trim()) return;
		isLoading = true;
		try {
			const res = await apiRequest<{ ideas: ContentIdea[]; cached: boolean }>(
				'/content/ideas',
				{ method: 'POST', body: { keyword } }
			);
			ideas = res.ideas;
			cached = res.cached;
		} catch (error) {
			if (error instanceof PlanGateRequestError) {
				planGateRequired = error.requiredPlan;
				planGateOpen = true;
			} else if (error instanceof ApiRequestError) {
				showError(error.errorCode, 'error.server');
			} else {
				showError('ERR_NETWORK', 'error.network');
			}
		} finally {
			isLoading = false;
		}
	}
</script>

<div class="space-y-6">
	<div class="flex items-center gap-3">
		<h1 class="text-2xl font-bold text-gray-900">{$t('content.title')}</h1>
		<span class="inline-flex items-center rounded-full bg-purple-100 px-2.5 py-0.5 text-xs font-medium text-purple-700">Pro+</span>
	</div>

	{#if isFreePlan}
		<div class="rounded-md bg-purple-50 border border-purple-200 p-4">
			<p class="text-sm text-purple-800">{$t('content.pro_only_notice')}</p>
		</div>
	{/if}

	<div class="flex items-center gap-3">
		<input
			type="text"
			bind:value={keyword}
			placeholder={$t('content.input_placeholder')}
			class="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
			onkeydown={(e) => { if (e.key === 'Enter') generateIdeas(); }}
		/>
		<button
			onclick={generateIdeas}
			disabled={isLoading || !keyword.trim()}
			class="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
		>
			{#if isLoading}
				{$t('status.loading')}
			{:else}
				{$t('content.generate')}
			{/if}
		</button>
	</div>

	{#if cached && ideas.length > 0}
		<span class="inline-flex items-center rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600">
			{$t('content.cached_badge')}
		</span>
	{/if}

	{#if ideas.length > 0}
		<div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
			{#each ideas as idea, i (i)}
				<ContentIdeaCard
					title={idea.title}
					hook={idea.hook}
					platform={idea.platform}
					difficulty={idea.difficulty}
				/>
			{/each}
		</div>
	{/if}
</div>

<PlanGate open={planGateOpen} requiredPlan={planGateRequired} onClose={() => (planGateOpen = false)} />
<ErrorModal
	open={errorOpen}
	errorCode={errorCode}
	messageKey={errorMessageKey}
	onClose={() => (errorOpen = false)}
/>
