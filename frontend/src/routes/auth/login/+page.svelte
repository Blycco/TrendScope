<script lang="ts">
	import { t } from 'svelte-i18n';
	import { goto } from '$app/navigation';
	import { authStore } from '$lib/stores/auth.svelte';
	import { ApiRequestError } from '$lib/api';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';

	let email = $state('');
	let password = $state('');
	let errorOpen = $state(false);
	let errorCode = $state('');
	let errorMessageKey = $state('');
	let isSubmitting = $state(false);

	async function handleSubmit(e: Event) {
		e.preventDefault();
		isSubmitting = true;
		errorOpen = false;

		try {
			await authStore.login(email, password);
			await goto('/');
		} catch (error) {
			if (error instanceof ApiRequestError) {
				errorCode = error.errorCode;
				errorMessageKey =
					error.status === 401
						? 'error.invalid_credentials'
						: 'error.server';
			} else {
				errorCode = 'ERR_NETWORK';
				errorMessageKey = 'error.network';
			}
			errorOpen = true;
		} finally {
			isSubmitting = false;
		}
	}
</script>

<div class="mx-auto max-w-sm">
	<h1 class="text-2xl font-bold text-gray-900 mb-6">{$t('page.auth.login.title')}</h1>

	<form onsubmit={handleSubmit} class="space-y-4">
		<div>
			<label for="email" class="block text-sm font-medium text-gray-700">{$t('label.email')}</label>
			<input
				id="email"
				type="email"
				bind:value={email}
				required
				class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
			/>
		</div>

		<div>
			<label for="password" class="block text-sm font-medium text-gray-700">{$t('label.password')}</label>
			<input
				id="password"
				type="password"
				bind:value={password}
				required
				class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
			/>
		</div>

		<button
			type="submit"
			disabled={isSubmitting}
			class="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
		>
			{$t('button.login')}
		</button>
	</form>

	<div class="mt-4 space-y-2 text-center text-sm">
		<a href="/auth/forgot-password" class="text-blue-600 hover:underline">{$t('button.forgot_password')}</a>
		<p class="text-gray-500">
			<a href="/auth/register" class="text-blue-600 hover:underline">{$t('button.register')}</a>
		</p>
	</div>

	<div class="mt-6 space-y-3">
		<a
			href="/api/v1/auth/oauth/google/start"
			class="flex w-full items-center justify-center gap-2 rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
		>
			{$t('button.google_login')}
		</a>
		<a
			href="/api/v1/auth/oauth/kakao/start"
			class="flex w-full items-center justify-center gap-2 rounded-md border border-gray-300 bg-yellow-300 px-4 py-2 text-sm font-medium text-gray-900 hover:bg-yellow-400"
		>
			{$t('button.kakao_login')}
		</a>
	</div>
</div>

<ErrorModal open={errorOpen} errorCode={errorCode} messageKey={errorMessageKey} onClose={() => (errorOpen = false)} />
