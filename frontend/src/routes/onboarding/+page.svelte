<script lang="ts">
	import { t } from 'svelte-i18n';
	import { goto } from '$app/navigation';
	import { apiRequest, ApiRequestError } from '$lib/api';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import { onMount } from 'svelte';
	import { Check, Bell, Tag } from 'lucide-svelte';

	const TOTAL_STEPS = 5;

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

	const popularKeywords = ['AI', '전기차', '숏폼', '친환경', 'K뷰티', '가성비', '헬스케어', '메타버스'];

	let step = $state(1);
	let selectedRole = $state<Role | null>(null);
	let selectedInterests = $state<Set<Interest>>(new Set());
	// locale_ratio: 0.0 = all global, 1.0 = all domestic; default 0.7
	let localeRatio = $state(0.7);

	// Step 3: keyword tracking
	let trackerKeyword = $state('');
	let trackerKeywords = $state<string[]>([]);

	// Step 4: notifications
	let notifSurge = $state(true);
	let notifWeekly = $state(true);

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

	function addTrackerKeyword(kw: string): void {
		const trimmed = kw.trim();
		if (!trimmed || trackerKeywords.includes(trimmed)) return;
		trackerKeywords = [...trackerKeywords, trimmed];
		trackerKeyword = '';
	}

	function removeTrackerKeyword(kw: string): void {
		trackerKeywords = trackerKeywords.filter((k) => k !== kw);
	}

	function canAdvance(): boolean {
		if (step === 1) return selectedRole !== null;
		if (step === 2) return selectedInterests.size >= 3;
		return true; // steps 3,4,5 are always advanceable (skippable)
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
			const categoryWeights: Record<string, number> = {};
			for (const key of selectedInterests) categoryWeights[key] = 2.0;

			await apiRequest('/settings', {
				method: 'PUT',
				body: {
					role: selectedRole,
					category_weights: categoryWeights,
				},
			});

			await apiRequest('/personalization', {
				method: 'PUT',
				body: {
					category_weights: categoryWeights,
					locale_ratio: localeRatio,
				},
			});

			// Step 3: save tracker keywords (best-effort)
			for (const kw of trackerKeywords) {
				try {
					await apiRequest('/notifications/keywords', { method: 'POST', body: { keyword: kw } });
				} catch { /* ignore individual failures */ }
			}

			// Step 4: save notification settings (best-effort)
			try {
				await apiRequest('/notifications/settings', {
					method: 'PUT',
					body: { type: 'surge_alert', channel: 'email', is_enabled: notifSurge },
				});
				await apiRequest('/notifications/settings', {
					method: 'PUT',
					body: { type: 'weekly_digest', channel: 'email', is_enabled: notifWeekly },
				});
			} catch { /* ignore */ }

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
				{#if step >= 3}
					<button type="button" onclick={handleNext} class="text-sm text-gray-400 hover:text-gray-600">
						{$t('onboarding.step3.skip')}
					</button>
				{/if}
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

			<!-- Step 3: Keyword tracking -->
			{#if step === 3}
				<div class="flex items-center gap-2 mb-1">
					<Tag size={18} class="text-blue-500" />
					<h1 class="text-xl font-bold text-gray-900">{$t('onboarding.step3.title')}</h1>
				</div>
				<p class="text-sm text-gray-500 mb-6">{$t('onboarding.step3.desc')}</p>

				<form onsubmit={(e) => { e.preventDefault(); addTrackerKeyword(trackerKeyword); }} class="flex gap-2 mb-4">
					<input
						type="text"
						bind:value={trackerKeyword}
						placeholder={$t('label.keyword')}
						class="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
					/>
					<button type="submit" class="rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700">
						{$t('tracker.add_keyword')}
					</button>
				</form>

				{#if trackerKeywords.length > 0}
					<div class="flex flex-wrap gap-2 mb-4">
						{#each trackerKeywords as kw}
							<span class="inline-flex items-center gap-1 rounded-full bg-blue-50 border border-blue-200 px-3 py-1 text-sm text-blue-700">
								#{kw}
								<button type="button" onclick={() => removeTrackerKeyword(kw)} class="text-blue-400 hover:text-blue-600 ml-1">×</button>
							</span>
						{/each}
					</div>
				{/if}

				<div>
					<p class="text-xs text-gray-400 mb-2">{$t('onboarding.step3.popular')}</p>
					<div class="flex flex-wrap gap-1.5">
						{#each popularKeywords as kw}
							<button
								type="button"
								onclick={() => addTrackerKeyword(kw)}
								disabled={trackerKeywords.includes(kw)}
								class="rounded-full border border-gray-200 px-3 py-1 text-xs text-gray-600 hover:border-blue-300 hover:text-blue-600 transition-colors disabled:opacity-40"
							>
								#{kw}
							</button>
						{/each}
					</div>
				</div>
			{/if}

			<!-- Step 4: Notifications -->
			{#if step === 4}
				<div class="flex items-center gap-2 mb-1">
					<Bell size={18} class="text-purple-500" />
					<h1 class="text-xl font-bold text-gray-900">{$t('onboarding.step4.title')}</h1>
				</div>
				<p class="text-sm text-gray-500 mb-6">{$t('onboarding.step4.title')}</p>

				<div class="space-y-3">
					<label class="flex items-center justify-between rounded-lg border border-gray-200 p-4 cursor-pointer hover:border-blue-200 transition-colors">
						<div>
							<p class="text-sm font-medium text-gray-900">{$t('onboarding.step4.surge_alert')}</p>
							<p class="text-xs text-gray-500 mt-0.5">{$t('tracker.keyword_card.alert_surge')}</p>
						</div>
						<input type="checkbox" bind:checked={notifSurge} class="w-4 h-4 accent-blue-600" />
					</label>
					<label class="flex items-center justify-between rounded-lg border border-gray-200 p-4 cursor-pointer hover:border-blue-200 transition-colors">
						<div>
							<p class="text-sm font-medium text-gray-900">{$t('onboarding.step4.weekly')}</p>
							<p class="text-xs text-gray-500 mt-0.5">{$t('tracker.keyword_card.alert_daily')}</p>
						</div>
						<input type="checkbox" bind:checked={notifWeekly} class="w-4 h-4 accent-blue-600" />
					</label>
				</div>
			{/if}

			<!-- Step 5: Locale ratio -->
			{#if step === 5}
				<h1 class="text-xl font-bold text-gray-900 mb-1">{$t('onboarding.step5.title')}</h1>
				<p class="text-sm text-gray-500 mb-6">{$t('onboarding.step5.description')}</p>

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
