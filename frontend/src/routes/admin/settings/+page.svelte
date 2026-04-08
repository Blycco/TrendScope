<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { adminRequest } from '$lib/api/admin';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';
	import PageStateWrapper from '$lib/ui/PageStateWrapper.svelte';

	interface SettingItem {
		key: string;
		value: unknown;
		default_value: unknown;
		updated_at: string | null;
	}

	interface SettingsResponse {
		settings: SettingItem[];
	}

	let settings = $state<SettingItem[]>([]);
	let editValues = $state<Record<string, string>>({});
	let loading = $state(true);
	let errorOpen = $state(false);
	let errorCode = $state('');
	let resetConfirm = $state(false);

	async function fetchSettings(): Promise<void> {
		try {
			loading = true;
			const data = await adminRequest<SettingsResponse>('/settings');
			settings = data.settings;
			editValues = {};
			for (const s of data.settings) {
				editValues[s.key] = typeof s.value === 'string' ? s.value : JSON.stringify(s.value);
			}
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		} finally {
			loading = false;
		}
	}

	async function saveSettings(): Promise<void> {
		try {
			const updates: Record<string, unknown> = {};
			for (const s of settings) {
				const newVal = editValues[s.key];
				const oldVal = typeof s.value === 'string' ? s.value : JSON.stringify(s.value);
				if (newVal !== oldVal) {
					try {
						updates[s.key] = JSON.parse(newVal);
					} catch {
						updates[s.key] = newVal;
					}
				}
			}
			if (Object.keys(updates).length > 0) {
				await adminRequest('/settings', {
					method: 'PATCH',
					body: { settings: updates }
				});
				await fetchSettings();
			}
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		}
	}

	async function resetToDefaults(): Promise<void> {
		try {
			await adminRequest('/settings/reset', { method: 'POST' });
			resetConfirm = false;
			await fetchSettings();
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		}
	}

	onMount(() => {
		fetchSettings();
	});
</script>

<div>
	<div class="flex items-center justify-between mb-6">
		<h2 class="text-2xl font-bold text-gray-900">{$t('admin.settings.title')}</h2>
		<div class="flex gap-3">
			<button
				onclick={saveSettings}
				class="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
			>
				{$t('button.save')}
			</button>
			<button
				onclick={() => (resetConfirm = true)}
				class="rounded-md border border-red-300 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50"
			>
				{$t('admin.settings.reset_defaults')}
			</button>
		</div>
	</div>

	<PageStateWrapper isLoading={loading} isEmpty={!loading && settings.length === 0}>
		{#snippet children()}
			<div class="bg-white rounded-lg shadow divide-y divide-gray-200">
				{#each settings as setting}
					<div class="p-4">
						<div class="flex items-start justify-between gap-4">
							<div class="flex-1">
								<label class="block text-sm font-medium text-gray-900">{setting.key}</label>
								<p class="text-xs text-gray-400 mt-1">
									{$t('admin.settings.default')}: {typeof setting.default_value === 'string' ? setting.default_value : JSON.stringify(setting.default_value)}
								</p>
							</div>
							<div class="w-80">
								<input
									type="text"
									bind:value={editValues[setting.key]}
									class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
								/>
							</div>
						</div>
					</div>
				{/each}
			</div>
		{/snippet}
	</PageStateWrapper>
</div>

{#if resetConfirm}
	<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50" role="dialog" aria-modal="true">
		<div class="bg-white rounded-lg p-6 max-w-sm mx-4 shadow-xl">
			<h3 class="text-lg font-semibold">{$t('admin.settings.reset_confirm_title')}</h3>
			<p class="mt-2 text-sm text-gray-600">{$t('admin.settings.reset_confirm_message')}</p>
			<div class="mt-4 flex gap-3 justify-end">
				<button onclick={() => (resetConfirm = false)} class="rounded-md border px-4 py-2 text-sm">{$t('button.cancel')}</button>
				<button onclick={resetToDefaults} class="rounded-md bg-red-600 px-4 py-2 text-sm text-white hover:bg-red-700">{$t('admin.settings.reset_defaults')}</button>
			</div>
		</div>
	</div>
{/if}

<ErrorModal open={errorOpen} {errorCode} onClose={() => (errorOpen = false)} onRetry={fetchSettings} />
