<script lang="ts">
	import '../app.css';
	import { initI18n } from '$lib/i18n';
	import { isLoading, t } from 'svelte-i18n';
	import { authStore } from '$lib/stores/auth.svelte';
	import { page } from '$app/stores';
	import { onMount } from 'svelte';
	import { Menu, X } from 'lucide-svelte';

	initI18n();
	onMount(() => authStore.initialize());

	let { children } = $props();

	const isAdmin = $derived($page.url.pathname.startsWith('/admin'));
	let mobileMenuOpen = $state(false);

	// Close mobile menu on route change
	$effect(() => {
		void $page.url.pathname;
		mobileMenuOpen = false;
	});
</script>

{#if $isLoading}
	<div class="flex h-screen items-center justify-center">
		<p class="text-gray-500">{$t('status.loading')}</p>
	</div>
{:else if isAdmin}
	{@render children()}
{:else}
	<div class="min-h-screen bg-gray-50">
		<nav class="bg-white border-b border-gray-200">
			<div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
				<div class="flex h-16 items-center justify-between">
					<div class="flex items-center gap-4 sm:gap-8">
						<!-- Mobile hamburger -->
						<button
							onclick={() => (mobileMenuOpen = !mobileMenuOpen)}
							class="sm:hidden p-1.5 -ml-1.5 rounded-md text-gray-600 hover:bg-gray-100"
							aria-label={$t('nav.menu')}
						>
							{#if mobileMenuOpen}
								<X size={22} />
							{:else}
								<Menu size={22} />
							{/if}
						</button>

						<a href="/" class="text-xl font-bold text-gray-900">TrendScope</a>

						<!-- Desktop nav links -->
						<div class="hidden sm:flex items-center gap-4">
							<a href="/trends" class="text-sm text-gray-600 hover:text-gray-900">
								{$t('nav.sidebar.trends')}
							</a>
							<a href="/news" class="text-sm text-gray-600 hover:text-gray-900">
								{$t('nav.sidebar.news')}
							</a>
							<a href="/content" class="text-sm text-gray-600 hover:text-gray-900">
								{$t('nav.content')}
							</a>
						</div>
					</div>

					<div class="flex items-center gap-3 sm:gap-4">
						{#if authStore.isAuthenticated}
							<span class="text-sm text-gray-600 truncate max-w-[120px] hidden sm:inline">
								{authStore.user?.display_name ?? authStore.user?.email}
							</span>
							<button
								onclick={() => authStore.logout()}
								class="text-sm text-gray-600 hover:text-gray-900"
							>
								{$t('nav.sidebar.logout')}
							</button>
						{:else}
							<a href="/auth/login" class="text-sm text-gray-600 hover:text-gray-900">
								{$t('nav.sidebar.login')}
							</a>
						{/if}
					</div>
				</div>
			</div>

			<!-- Mobile menu dropdown -->
			{#if mobileMenuOpen}
				<div class="sm:hidden border-t border-gray-200 bg-white">
					<div class="px-4 py-3 space-y-1">
						<a href="/trends" class="block rounded-md px-3 py-2 text-sm text-gray-700 hover:bg-gray-100">
							{$t('nav.sidebar.trends')}
						</a>
						<a href="/news" class="block rounded-md px-3 py-2 text-sm text-gray-700 hover:bg-gray-100">
							{$t('nav.sidebar.news')}
						</a>
						<a href="/content" class="block rounded-md px-3 py-2 text-sm text-gray-700 hover:bg-gray-100">
							{$t('nav.content')}
						</a>
					</div>
					{#if authStore.isAuthenticated}
						<div class="border-t border-gray-100 px-4 py-3">
							<p class="text-sm text-gray-500 truncate">
								{authStore.user?.display_name ?? authStore.user?.email}
							</p>
						</div>
					{/if}
				</div>
			{/if}
		</nav>

		<main class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
			{@render children()}
		</main>
	</div>
{/if}
