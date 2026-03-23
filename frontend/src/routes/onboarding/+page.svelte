<script lang="ts">
	import { t } from 'svelte-i18n';
	import { goto } from '$app/navigation';
	import { apiRequest, ApiRequestError } from '$lib/api';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';
	import { authStore } from '$lib/stores/auth';
	import { onMount } from 'svelte';
	import { Check } from 'lucide-svelte';

	const TOTAL_STEPS = 3;

	type Role = 'marketer' | 'creator' | 'owner' | 'general';
	type Interest =
		| 'food'
		| 'fashion'
		| 'it'
		| 'beauty'
		| 'leisure'
		| 'finance'
		| 'sports'
		| 'entertainment';

	const roles: { key: Role; labelKey: string; descKey: string }[] = [
		{ key: 'marketer', labelKey: 'onboarding.role.marketer', descKey: 'onboarding.role.marketer.desc' },
		{ key: 'creator', labelKey: 'onboarding.role.creator', descKey: 'onboarding.role.creator.desc' },
		{ key: 'owner', labelKey: 'onboarding.role.owner', descKey: 'onboarding.role.owner.desc' },
		{ key: 'general', labelKey: 'onboarding.role.general', descKey: 'onboarding.role.general.desc' },
	];

	const interests: { key: Interest; labelKey: string }[] = [
		{ key: 'food', labelKey: 'onboarding.interest.food' },
		{ key: 'fashion', labelKey: 'onboarding.interest.fashion' },
		{ key: 'it', labelKey: 'onboarding.interest.it' },
		{ key: 'beauty', labelKey: 'onboarding.interest.beauty' },
		{ key: 'leisure', labelKey: 'onboarding.interest.leisure' },
		{ key: 'finance', labelKey: 'onboarding.interest.finance' },
		{ key: 'sports', labelKey: 'onboarding.interest.sports' },
		{ key: 'entertainment', labelKey: 'onboarding.interest.entertainment' },
	];

	let step = $state(1);
	let selectedRole = $state<Role | null>(null);
	let selectedInterests = $state<Set<Interest>>(new Set());
	// locale_ratio: 0.0 = all global, 1.0 = all domestic; default 0.7
	let localeRatio = $state(0.7);

	let isSubmitting = $state(false);
	let errorOpen = $state(false);
	let errorCode = $state('');
	let errorMessageKey = $state('');

	function showError(code: string, key: string): void {
		errorCode = code;
		errorMessageKey = key;
		errorOpen = true;
	}

	onMount(() => {
		// If user already has a role, redirect to dashboard
		if (authStore.user?.role && authStore.user.role !== '') {
			goto('/');
		}
	});

	function toggleInterest(key: Interest): void {
		const next = new Set(selectedInterests);
		if (next.has(key)) {
			next.delete(key);
		} else {
			next.add(key);
		}
		selectedInterests = next;
	}

	function canAdvance(): boolean {
		if (step === 1) return selectedRole !== null;
		if (step === 2) return selectedInterests.size >= 3;
		return true;
	}

	function handleNext(): void {
		if (!canAdvance()) return;
		if (step < TOTAL_STEPS) {
			step += 1;
		} else {
			handleComplete();
		}
	}

	function handleBack(): void {
		if (step > 1) step -= 1;
	}

	async function handleComplete(): Promise<void> {
		if (isSubmitting) return;
		isSubmitting = true;
		try {
			await apiRequest('/personalization/profile', {
				method: 'PUT',
				body: {
					role: selectedRole,
					interests: Array.from(selectedInterests),
					locale_ratio: localeRatio,
				},
			});
			await authStore.fetchUser();
			goto('/');
		} catch (error) {
			if (error instanceof ApiRequestError) {
				showError(error.errorCode, 'error.server');
			} else {
				showError('ERR_NETWORK', 'error.network');
			}
		} finally {
			isSubmitting = false;
		}
	}

	const domesticPct = $derived(Math.round(localeRatio * 100));
	const globalPct = $derived(100 - domesticPct);
</script>

<div class="min-h-screen bg-gray-50 flex items-center justify-center px-4">
	<div class="w-full max-w-xl">
		<!-- Progress indicator -->
		<div class="mb-8">
			<div class="flex items-center justify-between mb-2">
				<span class="text-sm text-gray-500">
					{$t('onboarding.step_of', { values: { current: step, total: TOTAL_STEPS } })}
				</span>
			</div>
			<div class="flex gap-2">
				{#each Array(TOTAL_STEPS) as _, i}
					<div
						class="h-1.5 flex-1 rounded-full transition-colors"
						class:bg-blue-600={i < step}
						class:bg-gray-200={i >= step}
					></div>
				{/each}
			</div>
		</div>

		<div class="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
			<!-- Step 1: Role selection -->
			{#if step === 1}
				<h1 class="text-xl font-bold text-gray-900 mb-1">{$t('onboarding.step1.title')}</h1>
				<p class="text-sm text-gray-500 mb-6">{$t('onboarding.step1.description')}</p>
				<div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
					{#each roles as role}
						<button
							onclick={() => (selectedRole = role.key)}
							class="flex flex-col gap-1 rounded-lg border p-4 text-left transition-colors"
							class:border-blue-600={selectedRole === role.key}
							class:bg-blue-50={selectedRole === role.key}
							class:border-gray-200={selectedRole !== role.key}
							class:hover:border-blue-300={selectedRole !== role.key}
						>
							<span class="text-sm font-semibold text-gray-900">{$t(role.labelKey)}</span>
							<span class="text-xs text-gray-500">{$t(role.descKey)}</span>
						</button>
					{/each}
				</div>
			{/if}

			<!-- Step 2: Interest selection -->
			{#if step === 2}
				<h1 class="text-xl font-bold text-gray-900 mb-1">{$t('onboarding.step2.title')}</h1>
				<p class="text-sm text-gray-500 mb-6">{$t('onboarding.step2.description')}</p>
				<div class="flex flex-wrap gap-2">
					{#each interests as interest}
						{@const selected = selectedInterests.has(interest.key)}
						<button
							onclick={() => toggleInterest(interest.key)}
							class="flex items-center gap-1.5 rounded-full border px-4 py-2 text-sm font-medium transition-colors"
							class:border-blue-600={selected}
							class:bg-blue-600={selected}
							class:text-white={selected}
							class:border-gray-200={!selected}
							class:text-gray-700={!selected}
							class:hover:border-blue-300={!selected}
						>
							{#if selected}
								<Check size={14} />
							{/if}
							{$t(interest.labelKey)}
						</button>
					{/each}
				</div>
				{#if selectedInterests.size > 0 && selectedInterests.size < 3}
					<p class="mt-3 text-xs text-red-500">{$t('onboarding.error.select_interests')}</p>
				{/if}
			{/if}

			<!-- Step 3: Locale ratio -->
			{#if step === 3}
				<h1 class="text-xl font-bold text-gray-900 mb-1">{$t('onboarding.step3.title')}</h1>
				<p class="text-sm text-gray-500 mb-6">{$t('onboarding.step3.description')}</p>

				<div class="space-y-4">
					<div class="flex justify-between text-sm font-medium">
						<span class="text-gray-700">{$t('onboarding.locale.domestic_label')}</span>
						<span class="text-gray-700">{$t('onboarding.locale.global_label')}</span>
					</div>
					<input
						type="range"
						min="0"
						max="1"
						step="0.1"
						bind:value={localeRatio}
						class="w-full accent-blue-600"
					/>
					<p class="text-center text-sm text-gray-500">
						{$t('onboarding.locale.ratio_hint', { values: { domestic: domesticPct, global: globalPct } })}
					</p>
				</div>
			{/if}

			<!-- Navigation -->
			<div class="mt-8 flex justify-between gap-3">
				{#if step > 1}
					<button
						onclick={handleBack}
						class="rounded-md border border-gray-300 px-5 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
					>
						{$t('onboarding.button.back')}
					</button>
				{:else}
					<div></div>
				{/if}

				<button
					onclick={handleNext}
					disabled={!canAdvance() || isSubmitting}
					class="rounded-md bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
				>
					{#if isSubmitting}
						{$t('status.loading')}
					{:else if step < TOTAL_STEPS}
						{$t('onboarding.button.next')}
					{:else}
						{$t('onboarding.button.complete')}
					{/if}
				</button>
			</div>
		</div>
	</div>
</div>

<ErrorModal
	open={errorOpen}
	errorCode={errorCode}
	messageKey={errorMessageKey}
	onClose={() => (errorOpen = false)}
/>
