<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { authStore } from '$lib/stores/auth';
	import { apiRequest, ApiRequestError } from '$lib/api';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';
	import PlanGate from '$lib/ui/PlanGate.svelte';
	import { X } from 'lucide-svelte';

	type Tab = 'account' | 'plan' | 'notifications' | 'security' | 'personalization';
	let activeTab = $state<Tab>('account');

	// Account tab
	let displayName = $state('');
	let isSavingAccount = $state(false);

	// Notification tab — channel toggles
	interface NotificationSettings {
		trend_alert: boolean;
		quota_warning: boolean;
		plan_expiry: boolean;
	}
	let notifSettings = $state<NotificationSettings>({
		trend_alert: false,
		quota_warning: false,
		plan_expiry: false,
	});
	let isLoadingNotif = $state(false);

	// Notification tab — keyword alerts
	interface KeywordAlert {
		id: string;
		keyword: string;
	}
	let keywordAlerts = $state<KeywordAlert[]>([]);
	let isLoadingKeywords = $state(false);
	let newKeyword = $state('');
	let isAddingKeyword = $state(false);
	let deletingKeywordId = $state<string | null>(null);
	let planGateOpen = $state(false);
	let planGateRequired = $state('pro');

	// Security tab (2FA)
	let twoFaSecret = $state('');
	let twoFaQrUrl = $state('');
	let twoFaCode = $state('');
	let twoFaEnabled = $state(false);
	let twoFaSuccess = $state(false);
	let isEnabling2fa = $state(false);
	let isVerifying2fa = $state(false);

	// Personalization tab
	interface PersonalizationSettings {
		category_weights: { tech: number; finance: number; entertainment: number; lifestyle: number };
		locale_ratio: number;
	}
	let personalization = $state<PersonalizationSettings>({
		category_weights: { tech: 1.0, finance: 1.0, entertainment: 1.0, lifestyle: 1.0 },
		locale_ratio: 0.5,
	});
	let isLoadingPersonalization = $state(false);
	let isSavingPersonalization = $state(false);

	// Shared error state
	let errorOpen = $state(false);
	let errorCode = $state('');
	let errorMessageKey = $state('');

	function showError(code: string, key: string): void {
		errorCode = code;
		errorMessageKey = key;
		errorOpen = true;
	}

	onMount(() => {
		displayName = authStore.user?.display_name ?? '';
		loadNotificationSettings();
		loadKeywordAlerts();
		loadPersonalization();
	});

	async function saveAccount(): Promise<void> {
		isSavingAccount = true;
		try {
			await apiRequest('/settings', {
				method: 'PUT',
				body: { display_name: displayName },
			});
			await authStore.fetchUser();
		} catch (error) {
			if (error instanceof ApiRequestError) {
				showError(error.errorCode, 'error.server');
			} else {
				showError('ERR_NETWORK', 'error.network');
			}
		} finally {
			isSavingAccount = false;
		}
	}

	async function loadNotificationSettings(): Promise<void> {
		isLoadingNotif = true;
		try {
			const data = await apiRequest<NotificationSettings>('/notifications/settings');
			notifSettings = data;
		} catch {
			// Non-critical — silently ignore; toggles start false
		} finally {
			isLoadingNotif = false;
		}
	}

	async function saveNotificationChannel(channel: keyof NotificationSettings, value: boolean): Promise<void> {
		notifSettings[channel] = value;
		try {
			await apiRequest('/notifications/settings', {
				method: 'PUT',
				body: notifSettings,
			});
		} catch (error) {
			// Revert on error
			notifSettings[channel] = !value;
			if (error instanceof ApiRequestError) {
				showError(error.errorCode, 'error.server');
			} else {
				showError('ERR_NETWORK', 'error.network');
			}
		}
	}

	async function enable2fa(): Promise<void> {
		isEnabling2fa = true;
		try {
			const data = await apiRequest<{ secret: string; qr_url: string }>('/auth/2fa/enable', {
				method: 'POST',
			});
			twoFaSecret = data.secret;
			twoFaQrUrl = data.qr_url;
		} catch (error) {
			if (error instanceof ApiRequestError) {
				showError(error.errorCode, 'error.server');
			} else {
				showError('ERR_NETWORK', 'error.network');
			}
		} finally {
			isEnabling2fa = false;
		}
	}

	async function verify2fa(): Promise<void> {
		isVerifying2fa = true;
		try {
			await apiRequest('/auth/2fa/verify', {
				method: 'POST',
				body: { code: twoFaCode },
			});
			twoFaEnabled = true;
			twoFaSuccess = true;
			twoFaQrUrl = '';
			twoFaSecret = '';
			twoFaCode = '';
		} catch (error) {
			if (error instanceof ApiRequestError) {
				showError(error.errorCode, 'error.server');
			} else {
				showError('ERR_NETWORK', 'error.network');
			}
		} finally {
			isVerifying2fa = false;
		}
	}

	async function loadKeywordAlerts(): Promise<void> {
		isLoadingKeywords = true;
		try {
			const data = await apiRequest<{ keywords: KeywordAlert[] }>('/notifications/keywords');
			keywordAlerts = data.keywords;
		} catch {
			// Non-critical — silently ignore
		} finally {
			isLoadingKeywords = false;
		}
	}

	async function addKeywordAlert(): Promise<void> {
		const kw = newKeyword.trim();
		if (!kw || isAddingKeyword) return;
		isAddingKeyword = true;
		try {
			const data = await apiRequest<KeywordAlert>('/notifications/keywords', {
				method: 'POST',
				body: { keyword: kw },
			});
			keywordAlerts = [...keywordAlerts, data];
			newKeyword = '';
		} catch (error) {
			if (error instanceof ApiRequestError) {
				if (error.errorCode === 'PLAN_GATE' || error.status === 402 || error.status === 403) {
					planGateRequired = 'pro';
					planGateOpen = true;
				} else {
					showError(error.errorCode, 'notification.keywords.error.add');
				}
			} else {
				showError('ERR_NETWORK', 'error.network');
			}
		} finally {
			isAddingKeyword = false;
		}
	}

	async function deleteKeywordAlert(id: string): Promise<void> {
		deletingKeywordId = id;
		try {
			await apiRequest(`/notifications/keywords/${id}`, { method: 'DELETE' });
			keywordAlerts = keywordAlerts.filter((k) => k.id !== id);
		} catch (error) {
			if (error instanceof ApiRequestError) {
				showError(error.errorCode, 'notification.keywords.error.delete');
			} else {
				showError('ERR_NETWORK', 'error.network');
			}
		} finally {
			deletingKeywordId = null;
		}
	}

	async function loadPersonalization(): Promise<void> {
		isLoadingPersonalization = true;
		try {
			const data = await apiRequest<PersonalizationSettings>('/personalization');
			personalization = data;
		} catch {
			// Non-critical — silently ignore
		} finally {
			isLoadingPersonalization = false;
		}
	}

	async function savePersonalization(): Promise<void> {
		isSavingPersonalization = true;
		try {
			await apiRequest('/personalization', { method: 'PUT', body: personalization });
		} catch (error) {
			if (error instanceof ApiRequestError) {
				showError(error.errorCode, 'error.server');
			} else {
				showError('ERR_NETWORK', 'error.network');
			}
		} finally {
			isSavingPersonalization = false;
		}
	}

	const tabs: { key: Tab; labelKey: string }[] = [
		{ key: 'account', labelKey: 'settings.tab.account' },
		{ key: 'plan', labelKey: 'settings.tab.plan' },
		{ key: 'notifications', labelKey: 'settings.tab.notifications' },
		{ key: 'security', labelKey: 'settings.tab.security' },
		{ key: 'personalization', labelKey: 'settings.tab.personalization' },
	];
</script>

<div class="space-y-6">
	<h1 class="text-2xl font-bold text-gray-900">{$t('settings.title')}</h1>

	<!-- Tab nav -->
	<div class="border-b border-gray-200">
		<nav class="-mb-px flex gap-6">
			{#each tabs as tab}
				<button
					onclick={() => (activeTab = tab.key)}
					class="border-b-2 pb-3 text-sm font-medium transition-colors"
					class:border-blue-600={activeTab === tab.key}
					class:text-blue-600={activeTab === tab.key}
					class:border-transparent={activeTab !== tab.key}
					class:text-gray-500={activeTab !== tab.key}
				>
					{$t(tab.labelKey)}
				</button>
			{/each}
		</nav>
	</div>

	<!-- Account tab -->
	{#if activeTab === 'account'}
		<div class="max-w-md space-y-4">
			<div>
				<label class="block text-sm font-medium text-gray-700 mb-1" for="display-name">
					{$t('settings.account.display_name')}
				</label>
				<input
					id="display-name"
					type="text"
					bind:value={displayName}
					class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
				/>
			</div>
			<div>
				<label class="block text-sm font-medium text-gray-700 mb-1">
					{$t('label.email')}
				</label>
				<input
					type="email"
					value={authStore.user?.email ?? ''}
					readonly
					class="w-full rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-500"
				/>
			</div>
			<button
				onclick={saveAccount}
				disabled={isSavingAccount}
				class="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
			>
				{#if isSavingAccount}
					{$t('status.loading')}
				{:else}
					{$t('button.save')}
				{/if}
			</button>
		</div>
	{/if}

	<!-- Plan tab -->
	{#if activeTab === 'plan'}
		<div class="max-w-md space-y-4">
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<p class="text-sm text-gray-500">{$t('settings.plan.current_plan')}</p>
				<p class="mt-1 text-lg font-semibold capitalize text-gray-900">{authStore.user?.plan ?? '-'}</p>
			</div>
			<a
				href="/pricing"
				class="inline-block rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
			>
				{$t('settings.plan.view_pricing')}
			</a>
		</div>
	{/if}

	<!-- Notifications tab -->
	{#if activeTab === 'notifications'}
		<div class="max-w-md space-y-6">
			<!-- Channel toggles -->
			<div class="space-y-3">
				{#if isLoadingNotif}
					<p class="text-sm text-gray-500">{$t('status.loading')}</p>
				{:else}
					{#each (['trend_alert', 'quota_warning', 'plan_expiry'] as const) as channel}
						<div class="flex items-center justify-between rounded-lg border border-gray-200 bg-white p-4">
							<span class="text-sm font-medium text-gray-900">{$t(`settings.notifications.${channel}`)}</span>
							<button
								role="switch"
								aria-checked={notifSettings[channel]}
								onclick={() => saveNotificationChannel(channel, !notifSettings[channel])}
								class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors"
								class:bg-blue-600={notifSettings[channel]}
								class:bg-gray-200={!notifSettings[channel]}
							>
								<span
									class="inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform"
									class:translate-x-6={notifSettings[channel]}
									class:translate-x-1={!notifSettings[channel]}
								></span>
							</button>
						</div>
					{/each}
				{/if}
			</div>

			<!-- Keyword alerts -->
			<div class="space-y-3">
				<div>
					<h2 class="text-sm font-semibold text-gray-900">{$t('notification.keywords.title')}</h2>
					<p class="text-xs text-gray-500 mt-0.5">{$t('notification.keywords.description')}</p>
					<p class="text-xs text-gray-400 mt-0.5">
						{$t('notification.keywords.limit_pro')} · {$t('notification.keywords.limit_business')}
					</p>
				</div>

				<!-- Add keyword input -->
				<div class="flex gap-2">
					<input
						type="text"
						bind:value={newKeyword}
						placeholder={$t('notification.keywords.add_placeholder')}
						onkeydown={(e) => e.key === 'Enter' && addKeywordAlert()}
						class="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
					/>
					<button
						onclick={addKeywordAlert}
						disabled={!newKeyword.trim() || isAddingKeyword}
						class="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
					>
						{$t('notification.keywords.add_button')}
					</button>
				</div>

				<!-- Keyword list -->
				{#if isLoadingKeywords}
					<p class="text-sm text-gray-500">{$t('status.loading')}</p>
				{:else if keywordAlerts.length === 0}
					<p class="text-sm text-gray-400">{$t('notification.keywords.empty')}</p>
				{:else}
					<ul class="space-y-2">
						{#each keywordAlerts as kw}
							<li class="flex items-center justify-between rounded-lg border border-gray-200 bg-white px-4 py-2.5">
								<span class="text-sm text-gray-800">{kw.keyword}</span>
								<button
									onclick={() => deleteKeywordAlert(kw.id)}
									disabled={deletingKeywordId === kw.id}
									class="text-gray-400 hover:text-red-500 disabled:opacity-50"
									aria-label={$t('button.delete')}
								>
									<X size={16} />
								</button>
							</li>
						{/each}
					</ul>
				{/if}
			</div>
		</div>
	{/if}

	<!-- Personalization tab -->
	{#if activeTab === 'personalization'}
		<div class="max-w-md space-y-6">
			<h2 class="text-base font-semibold text-gray-900">{$t('settings.personalization.title')}</h2>

			{#if isLoadingPersonalization}
				<p class="text-sm text-gray-500">{$t('status.loading')}</p>
			{:else}
				<div class="space-y-4">
					<h3 class="text-sm font-medium text-gray-700">{$t('settings.personalization.category_weights')}</h3>
					{#each (['tech', 'finance', 'entertainment', 'lifestyle'] as const) as cat}
						<div class="space-y-1">
							<div class="flex justify-between text-sm">
								<label class="text-gray-700" for="slider-{cat}">{$t(`settings.personalization.category_${cat}`)}</label>
								<span class="text-gray-500">{personalization.category_weights[cat].toFixed(1)}</span>
							</div>
							<input
								id="slider-{cat}"
								type="range"
								min="0.5"
								max="2.0"
								step="0.1"
								bind:value={personalization.category_weights[cat]}
								class="w-full accent-blue-600"
							/>
						</div>
					{/each}
				</div>

				<div class="space-y-2">
					<h3 class="text-sm font-medium text-gray-700">{$t('settings.personalization.locale_ratio')}</h3>
					<div class="flex justify-between text-xs text-gray-500">
						<span>{$t('settings.personalization.locale_overseas')}</span>
						<span>{$t('settings.personalization.locale_domestic')}</span>
					</div>
					<input
						type="range"
						min="0.0"
						max="1.0"
						step="0.1"
						bind:value={personalization.locale_ratio}
						class="w-full accent-blue-600"
					/>
					<p class="text-xs text-gray-400 text-right">{personalization.locale_ratio.toFixed(1)}</p>
				</div>

				<button
					onclick={savePersonalization}
					disabled={isSavingPersonalization}
					class="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
				>
					{#if isSavingPersonalization}
						{$t('status.loading')}
					{:else}
						{$t('button.save')}
					{/if}
				</button>
			{/if}
		</div>
	{/if}

	<!-- Security tab -->
	{#if activeTab === 'security'}
		<div class="max-w-md space-y-4">
			<h2 class="text-base font-semibold text-gray-900">{$t('settings.security.2fa_title')}</h2>

			{#if twoFaSuccess}
				<p class="text-sm text-green-600">{$t('settings.security.2fa_success')}</p>
			{:else if twoFaQrUrl}
				<div class="space-y-4">
					<p class="text-sm text-gray-600">{$t('settings.security.2fa_scan_qr')}</p>
					<img src={twoFaQrUrl} alt="2FA QR code" class="h-48 w-48 rounded border border-gray-200" />
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1" for="totp-code">
							{$t('settings.security.2fa_code_label')}
						</label>
						<input
							id="totp-code"
							type="text"
							bind:value={twoFaCode}
							maxlength={6}
							class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
						/>
					</div>
					<button
						onclick={verify2fa}
						disabled={isVerifying2fa || twoFaCode.length < 6}
						class="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
					>
						{#if isVerifying2fa}
							{$t('status.loading')}
						{:else}
							{$t('settings.security.2fa_verify')}
						{/if}
					</button>
				</div>
			{:else}
				<button
					onclick={enable2fa}
					disabled={isEnabling2fa || twoFaEnabled}
					class="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
				>
					{#if isEnabling2fa}
						{$t('status.loading')}
					{:else}
						{$t('settings.security.2fa_enable')}
					{/if}
				</button>
			{/if}
		</div>
	{/if}
</div>

<PlanGate
	open={planGateOpen}
	requiredPlan={planGateRequired}
	onClose={() => (planGateOpen = false)}
/>

<ErrorModal
	open={errorOpen}
	errorCode={errorCode}
	messageKey={errorMessageKey}
	onClose={() => (errorOpen = false)}
/>
