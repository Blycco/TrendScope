<script lang="ts">
	import { initI18n } from '$lib/i18n';
	import { isLoading, t } from 'svelte-i18n';
	import { authStore } from '$lib/stores/auth.svelte';
	import { afterNavigate } from '$app/navigation';
	import { onMount } from 'svelte';
	import { adminRequest } from '$lib/api/admin';
	import { Menu, X } from 'lucide-svelte';

	initI18n();

	let alertCount = $state(0);
	let sidebarOpen = $state(false);

	onMount(() => {
		authStore.initialize();
		loadAlertCount();
	});

	afterNavigate(() => {
		sidebarOpen = false;
	});

	async function loadAlertCount() {
		try {
			const res = await adminRequest<{ active_count: number }>('/quota-alerts/count');
			alertCount = res.active_count;
		} catch {
			alertCount = 0;
		}
	}

	let { children } = $props();

	const menuItems = [
		{ href: '/admin', labelKey: 'admin.layout.home' },
		{ href: '/admin/users', labelKey: 'admin.layout.users' },
		{ href: '/admin/subscriptions', labelKey: 'admin.layout.subscriptions' },
		{ href: '/admin/sources', labelKey: 'admin.layout.sources' },
		{ href: '/admin/ai-config', labelKey: 'admin.layout.ai_config' },
		{ href: '/admin/settings', labelKey: 'admin.layout.settings' },
		{ href: '/admin/audit', labelKey: 'admin.layout.audit' },
		{ href: '/admin/quota-alerts', labelKey: 'admin.layout.quota_alerts' }
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
		<!-- Mobile sidebar overlay -->
		{#if sidebarOpen}
			<div
				class="fixed inset-0 z-40 bg-black/50 md:hidden"
				onclick={() => (sidebarOpen = false)}
				onkeydown={(e) => e.key === 'Escape' && (sidebarOpen = false)}
				role="button"
				tabindex="-1"
				aria-label={$t('nav.mobile.close')}
			></div>
		{/if}

		<!-- Sidebar -->
		<aside
			class="fixed inset-y-0 left-0 z-50 w-64 bg-gray-900 text-white flex-shrink-0 transform transition-transform duration-200 ease-in-out md:relative md:translate-x-0 {sidebarOpen ? 'translate-x-0' : '-translate-x-full'}"
		>
			<div class="flex items-center justify-between p-6">
				<a href="/admin" class="text-xl font-bold">{$t('admin.layout.brand')}</a>
				<button
					onclick={() => (sidebarOpen = false)}
					class="md:hidden p-1 text-gray-400 hover:text-white"
					aria-label={$t('nav.mobile.close')}
				>
					<X size={20} />
				</button>
			</div>
			<nav class="mt-2">
				{#each menuItems as item}
					<a
						href={item.href}
						class="flex items-center gap-2 px-6 py-3 text-sm text-gray-300 hover:bg-gray-800 hover:text-white transition-colors"
					>
						{$t(item.labelKey)}
						{#if item.href === '/admin/quota-alerts' && alertCount > 0}
							<span class="inline-flex items-center justify-center w-5 h-5 text-xs font-bold text-white bg-red-500 rounded-full">{alertCount}</span>
						{/if}
					</a>
				{/each}
			</nav>
			<div class="mt-auto p-6 border-t border-gray-800">
				<p class="text-xs text-gray-500">{authStore.user?.email}</p>
				<p class="text-xs text-gray-400 mt-1">{authStore.user?.role}</p>
			</div>
		</aside>

		<div class="flex-1 flex flex-col overflow-hidden">
			<header class="bg-white border-b border-gray-200 px-4 sm:px-6 py-4 flex items-center justify-between">
				<div class="flex items-center gap-3">
					<button
						onclick={() => (sidebarOpen = true)}
						class="md:hidden p-1.5 text-gray-600 hover:text-gray-900"
						aria-label={$t('nav.mobile.menu')}
					>
						<Menu size={22} />
					</button>
					<h1 class="text-lg font-semibold text-gray-900">{$t('admin.layout.title')}</h1>
				</div>
				<div class="flex items-center gap-4">
					<a href="/" class="text-sm text-gray-600 hover:text-gray-900">{$t('admin.layout.back_to_app')}</a>
					<button
						onclick={() => authStore.logout()}
						class="hidden sm:inline text-sm text-gray-600 hover:text-gray-900"
					>
						{$t('nav.sidebar.logout')}
					</button>
				</div>
			</header>

			<main class="flex-1 overflow-y-auto p-4 sm:p-6">
				{@render children()}
			</main>
		</div>
	</div>
{/if}
