<script lang="ts">
	import '../app.css';
	import { initI18n } from '$lib/i18n';
	import { isLoading, t } from 'svelte-i18n';

	initI18n();

	let { children } = $props();
</script>

{#if $isLoading}
	<div class="flex h-screen items-center justify-center">
		<p class="text-gray-500">{$t('status.loading')}</p>
	</div>
{:else}
	<div class="min-h-screen bg-gray-50">
		<nav class="bg-white border-b border-gray-200">
			<div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
				<div class="flex h-16 items-center justify-between">
					<div class="flex items-center gap-8">
						<a href="/" class="text-xl font-bold text-gray-900">TrendScope</a>
						<div class="hidden sm:flex items-center gap-4">
							<a href="/trends" class="text-sm text-gray-600 hover:text-gray-900">{$t('nav.sidebar.trends')}</a>
							<a href="/news" class="text-sm text-gray-600 hover:text-gray-900">{$t('nav.sidebar.news')}</a>
						</div>
					</div>
					<div class="flex items-center gap-4">
						<a href="/auth/login" class="text-sm text-gray-600 hover:text-gray-900">{$t('nav.sidebar.login')}</a>
					</div>
				</div>
			</div>
		</nav>

		<main class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
			{@render children()}
		</main>
	</div>
{/if}
