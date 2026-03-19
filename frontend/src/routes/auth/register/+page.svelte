<script lang="ts">
	import { t } from 'svelte-i18n';
	import { goto } from '$app/navigation';
	import { apiRequest, ApiRequestError } from '$lib/api';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';

	let email = $state('');
	let password = $state('');
	let passwordConfirm = $state('');
	let displayName = $state('');
	let errorOpen = $state(false);
	let errorCode = $state('');
	let errorMessageKey = $state('');
	let isSubmitting = $state(false);

	async function handleSubmit(e: Event) {
		e.preventDefault();

		if (password !== passwordConfirm) {
			errorCode = 'ERR_VALIDATION';
			errorMessageKey = 'error.server';
			errorOpen = true;
			return;
		}

		isSubmitting = true;
		errorOpen = false;

		try {
			await apiRequest('/auth/register', {
				method: 'POST',
				body: { email, password, display_name: displayName || null },
				auth: false
			});
			await goto('/auth/login');
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
			isSubmitting = false;
		}
	}
</script>

<div class="mx-auto max-w-sm">
	<h1 class="text-2xl font-bold text-gray-900 mb-6">{$t('page.auth.register.title')}</h1>

	<form onsubmit={handleSubmit} class="space-y-4">
		<div>
			<label for="displayName" class="block text-sm font-medium text-gray-700">{$t('label.name')}</label>
			<input
				id="displayName"
				type="text"
				bind:value={displayName}
				class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
			/>
		</div>

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

		<div>
			<label for="passwordConfirm" class="block text-sm font-medium text-gray-700">{$t('label.password_confirm')}</label>
			<input
				id="passwordConfirm"
				type="password"
				bind:value={passwordConfirm}
				required
				class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
			/>
		</div>

		<button
			type="submit"
			disabled={isSubmitting}
			class="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
		>
			{$t('button.register')}
		</button>
	</form>

	<div class="mt-4 text-center text-sm text-gray-500">
		<a href="/auth/login" class="text-blue-600 hover:underline">{$t('button.login')}</a>
	</div>
</div>

<ErrorModal open={errorOpen} errorCode={errorCode} messageKey={errorMessageKey} onClose={() => (errorOpen = false)} />
