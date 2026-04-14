<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { apiRequest, ApiRequestError } from '$lib/api';
	import { authStore } from '$lib/stores/auth.svelte';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';
	import { CheckCircle2, Clock, XCircle } from 'lucide-svelte';

	interface CheckoutResult {
		provider: string;
		session_id: string;
		checkout_url: string;
		status: 'paid' | 'pending' | 'failed' | string;
	}

	let result = $state<CheckoutResult | null>(null);
	let isLoading = $state(true);
	let errorOpen = $state(false);
	let errorCode = $state('');
	let errorMessageKey = $state('');

	const sessionId = $derived($page.url.searchParams.get('session_id') ?? '');

	async function loadStatus(): Promise<void> {
		if (!sessionId) {
			errorCode = 'ERR_MISSING_SESSION';
			errorMessageKey = 'payment.callback.error.missing_session';
			errorOpen = true;
			isLoading = false;
			return;
		}
		try {
			result = await apiRequest<CheckoutResult>(
				`/payments/toss/checkout/${encodeURIComponent(sessionId)}`
			);
			if (result.status === 'paid') {
				await authStore.fetchUser();
			}
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
			isLoading = false;
		}
	}

	onMount(() => {
		loadStatus();
	});
</script>

<div class="mx-auto max-w-md py-12">
	{#if isLoading}
		<div class="text-center text-gray-500 dark:text-gray-400">
			<p>{$t('payment.callback.loading')}</p>
		</div>
	{:else if result}
		<div class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-8 text-center">
			{#if result.status === 'paid'}
				<div class="mx-auto mb-4 text-green-500"><CheckCircle2 size={48} /></div>
				<h1 class="text-xl font-bold text-gray-900 dark:text-gray-100">{$t('payment.callback.success.title')}</h1>
				<p class="mt-2 text-sm text-gray-600 dark:text-gray-400">{$t('payment.callback.success.desc')}</p>
				<a href="/settings" class="mt-6 inline-block rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
					{$t('payment.callback.view_plan')}
				</a>
			{:else if result.status === 'pending'}
				<div class="mx-auto mb-4 text-amber-500"><Clock size={48} /></div>
				<h1 class="text-xl font-bold text-gray-900 dark:text-gray-100">{$t('payment.callback.pending.title')}</h1>
				<p class="mt-2 text-sm text-gray-600 dark:text-gray-400">{$t('payment.callback.pending.desc')}</p>
				<div class="mt-6 flex justify-center gap-2">
					<button
						type="button"
						onclick={loadStatus}
						class="rounded-md border border-gray-200 dark:border-gray-700 px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
					>
						{$t('payment.callback.retry')}
					</button>
					<a href="/pricing" class="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
						{$t('payment.callback.back_to_pricing')}
					</a>
				</div>
			{:else}
				<div class="mx-auto mb-4 text-red-500"><XCircle size={48} /></div>
				<h1 class="text-xl font-bold text-gray-900 dark:text-gray-100">{$t('payment.callback.failed.title')}</h1>
				<p class="mt-2 text-sm text-gray-600 dark:text-gray-400">{$t('payment.callback.failed.desc')}</p>
				<a href="/pricing" class="mt-6 inline-block rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
					{$t('payment.callback.back_to_pricing')}
				</a>
			{/if}
			<p class="mt-6 text-xs text-gray-400 dark:text-gray-500">
				{$t('payment.callback.session_id')}: {result.session_id}
			</p>
		</div>
	{/if}
</div>

<ErrorModal open={errorOpen} errorCode={errorCode} messageKey={errorMessageKey} onClose={() => (errorOpen = false)} />
