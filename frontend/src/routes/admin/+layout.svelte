<script lang="ts">
	import { initI18n } from '$lib/i18n';
	import { isLoading, t } from 'svelte-i18n';
	import { authStore } from '$lib/stores/auth';
	import { onMount } from 'svelte';

	initI18n();
	onMount(() => {
		authStore.initialize();
	});

	let { children } = $props();

	const menuItems = [
		{ href: '/admin', labelKey: 'admin.layout.home' },
		{ href: '/admin/users', labelKey: 'admin.layout.users' },
		{ href: '/admin/subscriptions', labelKey: 'admin.layout.subscriptions' },
		{ href: '/admin/sources', labelKey: 'admin.layout.sources' },
		{ href: '/admin/ai-config', labelKey: 'admin.layout.ai_config' },
		{ href: '/admin/settings', labelKey: 'admin.layout.settings' },
		{ href: '/admin/audit', labelKey: 'admin.layout.audit' }
	];
</script>

{#if $isLoading}
	<div class="flex h-screen items-center justify-center">
		<p class="text-gray-500">{$t('status.loading')}</p>
	</div>
{:else if !authStore.isAuthenticated || !['admin', 'operator'].includes(authStore.user?.role ?? '')}
	<div class="flex h-screen items-center justify-center">
		<div class="text-center">
			<h1 class="text-2xl font-bold text-gray-900">{$t('admin.layout.access_denied')}</h1>
			<p class="mt-2 text-gray-600">{$t('admin.layout.access_denied_message')}</p>
			<a href="/" class="mt-4 inline-block text-blue-600 hover:text-blue-800">{$t('admin.layout.back_home')}</a>
		</div>
	</div>
{:else}
	<div class="flex h-screen bg-gray-100">
		<aside class="w-64 bg-gray-900 text-white flex-shrink-0">
			<div class="p-6">
				<a href="/admin" class="text-xl font-bold">TrendScope Admin</a>
			</div>
			<nav class="mt-2">
				{#each menuItems as item}
					<a
						href={item.href}
						class="block px-6 py-3 text-sm text-gray-300 hover:bg-gray-800 hover:text-white transition-colors"
					>
						{$t(item.labelKey)}
					</a>
				{/each}
			</nav>
			<div class="mt-auto p-6 border-t border-gray-800">
				<p class="text-xs text-gray-500">{authStore.user?.email}</p>
				<p class="text-xs text-gray-400 mt-1">{authStore.user?.role}</p>
			</div>
		</aside>

		<div class="flex-1 flex flex-col overflow-hidden">
			<header class="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
				<h1 class="text-lg font-semibold text-gray-900">{$t('admin.layout.title')}</h1>
				<div class="flex items-center gap-4">
					<a href="/" class="text-sm text-gray-600 hover:text-gray-900">{$t('admin.layout.back_to_app')}</a>
					<button
						onclick={() => authStore.logout()}
						class="text-sm text-gray-600 hover:text-gray-900"
					>
						{$t('nav.sidebar.logout')}
					</button>
				</div>
			</header>

			<main class="flex-1 overflow-y-auto p-6">
				{@render children()}
			</main>
		</div>
	</div>
{/if}
