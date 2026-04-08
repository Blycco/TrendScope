<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { adminRequest } from '$lib/api/admin';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';
	import PageStateWrapper from '$lib/ui/PageStateWrapper.svelte';

	interface AIConfigResponse {
		primary_model: string | null;
		fallback_model: string | null;
		api_key_set: boolean;
		settings: Record<string, unknown>;
	}

	interface AIConfigTestResponse {
		success: boolean;
		response_time_ms: number | null;
		error: string | null;
	}

	let primaryModel = $state('');
	let fallbackModel = $state('');
	let apiKeySet = $state(false);
	let loading = $state(true);
	let testing = $state(false);
	let testResult = $state<AIConfigTestResponse | null>(null);
	let errorOpen = $state(false);
	let errorCode = $state('');

	const modelOptions = [
		'gemini-2.0-flash',
		'gemini-1.5-flash',
		'gpt-4o-mini',
		'gpt-4o',
		'claude-3-haiku'
	];

	async function fetchConfig(): Promise<void> {
		try {
			loading = true;
			const data = await adminRequest<AIConfigResponse>('/ai-config');
			primaryModel = data.primary_model ?? '';
			fallbackModel = data.fallback_model ?? '';
			apiKeySet = data.api_key_set;
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		} finally {
			loading = false;
		}
	}

	async function saveConfig(): Promise<void> {
		try {
			await adminRequest('/ai-config', {
				method: 'PATCH',
				body: {
					primary_model: primaryModel || null,
					fallback_model: fallbackModel || null
				}
			});
			await fetchConfig();
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		}
	}

	async function testConnection(): Promise<void> {
		try {
			testing = true;
			testResult = null;
			testResult = await adminRequest<AIConfigTestResponse>('/ai-config/test', {
				method: 'POST'
			});
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		} finally {
			testing = false;
		}
	}

	onMount(() => {
		fetchConfig();
	});
</script>

<div>
	<h2 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-6">{$t('admin.ai_config.title')}</h2>

	<PageStateWrapper isLoading={loading} isEmpty={false}>
		{#snippet children()}
		<div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 max-w-lg">
			<div class="space-y-4">
				<div>
					<label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{$t('admin.ai_config.primary_model')}</label>
					<select bind:value={primaryModel} class="w-full rounded-md border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 px-3 py-2 text-sm">
						<option value="">-- {$t('admin.ai_config.select_model')} --</option>
						{#each modelOptions as model}
							<option value={model}>{model}</option>
						{/each}
					</select>
				</div>

				<div>
					<label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{$t('admin.ai_config.fallback_model')}</label>
					<select bind:value={fallbackModel} class="w-full rounded-md border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 px-3 py-2 text-sm">
						<option value="">-- {$t('admin.ai_config.select_model')} --</option>
						{#each modelOptions as model}
							<option value={model}>{model}</option>
						{/each}
					</select>
				</div>

				<div class="flex items-center gap-2 text-sm">
					<span class="text-gray-600 dark:text-gray-400">{$t('admin.ai_config.api_key_status')}:</span>
					<span class="{apiKeySet ? 'text-green-600' : 'text-red-600'}">
						{apiKeySet ? $t('admin.ai_config.api_key_set') : $t('admin.ai_config.api_key_not_set')}
					</span>
				</div>

				<div class="flex gap-3 pt-4">
					<button
						onclick={saveConfig}
						class="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
					>
						{$t('button.save')}
					</button>
					<button
						onclick={testConnection}
						disabled={testing}
						class="rounded-md border border-gray-300 dark:border-gray-600 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50"
					>
						{testing ? $t('status.loading') : $t('admin.ai_config.test_connection')}
					</button>
				</div>

				{#if testResult}
					<div class="mt-4 p-3 rounded-md {testResult.success ? 'bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-800' : 'bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800'}">
						<p class="text-sm {testResult.success ? 'text-green-800 dark:text-green-400' : 'text-red-800 dark:text-red-400'}">
							{testResult.success ? $t('admin.ai_config.test_success') : $t('admin.ai_config.test_failed')}
						</p>
						{#if testResult.response_time_ms != null}
							<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">{$t('admin.ai_config.response_time')}: {testResult.response_time_ms.toFixed(1)}ms</p>
						{/if}
						{#if testResult.error}
							<p class="text-xs text-red-600 mt-1">{testResult.error}</p>
						{/if}
					</div>
				{/if}
			</div>
		</div>
		{/snippet}
	</PageStateWrapper>
</div>

<ErrorModal open={errorOpen} {errorCode} onClose={() => (errorOpen = false)} onRetry={fetchConfig} />
