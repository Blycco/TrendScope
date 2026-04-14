<script lang="ts">
	import '../app.css';
	import { initI18n } from '$lib/i18n';
	import { isLoading, t } from 'svelte-i18n';
	import { authStore } from '$lib/stores/auth.svelte';
	import { themeStore } from '$lib/stores/theme.svelte';
	import { page } from '$app/stores';
	import { afterNavigate } from '$app/navigation';
	import { onMount } from 'svelte';
	import { Menu, X } from 'lucide-svelte';
	import OnboardingTour from '$lib/ui/OnboardingTour.svelte';
	import ThemeToggle from '$lib/ui/ThemeToggle.svelte';

	initI18n();
	onMount(() => {
		authStore.initialize();
		themeStore.initialize();
	});

	const TOUR_STEPS = [
		{ target: 'stat-cards', titleKey: 'tour.step.stats.title', descriptionKey: 'tour.step.stats.desc', position: 'bottom' as const },
		{ target: 'category-chart', titleKey: 'tour.step.categories.title', descriptionKey: 'tour.step.categories.desc', position: 'bottom' as const },
		{ target: 'top-keywords', titleKey: 'tour.step.keywords.title', descriptionKey: 'tour.step.keywords.desc', position: 'bottom' as const },
		{ target: 'early-trends', titleKey: 'tour.step.early.title', descriptionKey: 'tour.step.early.desc', position: 'bottom' as const },
		{ target: 'hot-trends', titleKey: 'tour.step.hot_trends.title', descriptionKey: 'tour.step.hot_trends.desc', position: 'top' as const },
		{ target: 'nav-links', titleKey: 'tour.step.nav.title', descriptionKey: 'tour.step.nav.desc', position: 'bottom' as const },
	];
	const showTour = $derived($page.url.pathname === '/' && authStore.isAuthenticated && !!authStore.user?.role);

	let { children } = $props();

	const isAdmin = $derived($page.url.pathname.startsWith('/admin'));
	let mobileMenuOpen = $state(false);

	afterNavigate(() => {
		mobileMenuOpen = false;
	});
</script>

{#if $isLoading}
	<div class="flex h-screen items-center justify-center">
		<p class="text-gray-500 dark:text-gray-400">{$t('status.loading')}</p>
	</div>
{:else if isAdmin}
	{@render children()}
{:else}
	<div class="min-h-screen bg-gray-50 dark:bg-gray-950">
		<a
			href="#main-content"
			class="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:top-2 focus:left-2 focus:bg-white dark:focus:bg-gray-800 focus:px-4 focus:py-2 focus:rounded-md focus:shadow-lg focus:text-blue-700 dark:focus:text-blue-400 focus:font-medium focus:outline-none"
		>
			{$t('a11y.skip_to_main')}
		</a>
		<nav class="bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700">
			<div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
				<div class="flex h-16 items-center justify-between">
					<div class="flex items-center gap-8">
						<a href="/" class="text-xl font-bold text-gray-900 dark:text-gray-100">TrendScope</a>
						<div class="hidden sm:flex items-center gap-4" data-tour="nav-links">
							<a href="/trends" class="text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100" aria-current={$page.url.pathname === '/trends' || ($page.url.pathname.startsWith('/trends/') && !$page.url.pathname.startsWith('/trends/early')) ? 'page' : undefined}>{$t('nav.sidebar.trends')}</a>
							<a href="/trends/early" class="text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100" aria-current={$page.url.pathname.startsWith('/trends/early') ? 'page' : undefined}>{$t('nav.early_trends')}</a>
							<a href="/news" class="text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100" aria-current={$page.url.pathname.startsWith('/news') ? 'page' : undefined}>{$t('nav.sidebar.news')}</a>
							<a href="/content" class="text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100" aria-current={$page.url.pathname.startsWith('/content') ? 'page' : undefined}>{$t('nav.content')}</a>
							<a href="/compare" class="text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100" aria-current={$page.url.pathname.startsWith('/compare') ? 'page' : undefined}>{$t('nav.compare')}</a>
							<a href="/regional" class="text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100" aria-current={$page.url.pathname.startsWith('/regional') ? 'page' : undefined}>{$t('regional.title')}</a>
							<a href="/tracker" class="text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100" aria-current={$page.url.pathname.startsWith('/tracker') ? 'page' : undefined}>{$t('nav.sidebar.tracker')}</a>
							<a href="/scraps" class="text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100" aria-current={$page.url.pathname.startsWith('/scraps') ? 'page' : undefined}>{$t('nav.sidebar.scraps')}</a>
							<a href="/pricing" class="text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100" aria-current={$page.url.pathname.startsWith('/pricing') ? 'page' : undefined}>{$t('nav.pricing')}</a>
						</div>
					</div>
					<div class="flex items-center gap-4">
						<ThemeToggle />
						{#if authStore.isAuthenticated}
							<span class="hidden sm:inline text-sm text-gray-600 dark:text-gray-400">{authStore.user?.display_name ?? authStore.user?.email}</span>
							<button
								onclick={() => authStore.logout()}
								class="hidden sm:inline text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100"
							>
								{$t('nav.sidebar.logout')}
							</button>
						{:else}
							<a href="/auth/login" class="hidden sm:inline text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100">{$t('nav.sidebar.login')}</a>
						{/if}
						<button
							onclick={() => (mobileMenuOpen = !mobileMenuOpen)}
							class="sm:hidden p-1.5 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100"
							aria-label={mobileMenuOpen ? $t('nav.mobile.close') : $t('nav.mobile.menu')}
							aria-expanded={mobileMenuOpen}
						>
							{#if mobileMenuOpen}
								<X size={24} />
							{:else}
								<Menu size={24} />
							{/if}
						</button>
					</div>
				</div>
			</div>

			{#if mobileMenuOpen}
				<div class="sm:hidden border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
					<div class="px-4 py-3 space-y-1">
						<a href="/trends" class="block rounded-md px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800" aria-current={$page.url.pathname === '/trends' || ($page.url.pathname.startsWith('/trends/') && !$page.url.pathname.startsWith('/trends/early')) ? 'page' : undefined}>{$t('nav.sidebar.trends')}</a>
						<a href="/trends/early" class="block rounded-md px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800" aria-current={$page.url.pathname.startsWith('/trends/early') ? 'page' : undefined}>{$t('nav.early_trends')}</a>
						<a href="/news" class="block rounded-md px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800" aria-current={$page.url.pathname.startsWith('/news') ? 'page' : undefined}>{$t('nav.sidebar.news')}</a>
						<a href="/content" class="block rounded-md px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800" aria-current={$page.url.pathname.startsWith('/content') ? 'page' : undefined}>{$t('nav.content')}</a>
						<a href="/compare" class="block rounded-md px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800" aria-current={$page.url.pathname.startsWith('/compare') ? 'page' : undefined}>{$t('nav.compare')}</a>
						<a href="/regional" class="block rounded-md px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800" aria-current={$page.url.pathname.startsWith('/regional') ? 'page' : undefined}>{$t('regional.title')}</a>
						<a href="/tracker" class="block rounded-md px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800" aria-current={$page.url.pathname.startsWith('/tracker') ? 'page' : undefined}>{$t('nav.sidebar.tracker')}</a>
						<a href="/scraps" class="block rounded-md px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800" aria-current={$page.url.pathname.startsWith('/scraps') ? 'page' : undefined}>{$t('nav.sidebar.scraps')}</a>
						<a href="/pricing" class="block rounded-md px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800" aria-current={$page.url.pathname.startsWith('/pricing') ? 'page' : undefined}>{$t('nav.pricing')}</a>
						<a href="/settings" class="block rounded-md px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800">{$t('nav.sidebar.settings')}</a>
					</div>
					<div class="border-t border-gray-200 dark:border-gray-700 px-4 py-3">
						{#if authStore.isAuthenticated}
							<p class="px-3 text-xs text-gray-500 dark:text-gray-400">{authStore.user?.display_name ?? authStore.user?.email}</p>
							<button
								onclick={() => authStore.logout()}
								class="mt-1 block w-full rounded-md px-3 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
							>
								{$t('nav.sidebar.logout')}
							</button>
						{:else}
							<a href="/auth/login" class="block rounded-md px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800">{$t('nav.sidebar.login')}</a>
							<a href="/auth/register" class="block rounded-md px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800">{$t('nav.sidebar.register')}</a>
						{/if}
					</div>
				</div>
			{/if}
		</nav>

		<main id="main-content" class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
			{@render children()}
		</main>

		{#if showTour}
			<OnboardingTour steps={TOUR_STEPS} />
		{/if}
	</div>
{/if}
