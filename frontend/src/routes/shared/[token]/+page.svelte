<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { formatDate } from '$lib/utils/locale';
	import EarlyBadge from '../../../components/EarlyBadge.svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import { TrendingUp, ArrowRight } from 'lucide-svelte';

	interface SharedTrendItem {
		id: string;
		title: string;
		category: string;
		summary: string | null;
		score: number;
		early_trend_score: number;
		keywords: string[];
		created_at: string;
	}

	interface SharedLinkData {
		token: string;
		payload: { trends: SharedTrendItem[] };
		expires_at: string;
		created_at: string;
	}

	let data = $state<SharedLinkData | null>(null);
	let isLoading = $state(true);
	let errorStatus = $state<'not_found' | 'expired' | 'error' | null>(null);

	onMount(async () => {
		const token = $page.params.token;
		try {
			const apiBase = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';
			const response = await fetch(`${apiBase}/shared/${token}`);
			if (response.status === 404) {
				errorStatus = 'not_found';
				return;
			}
			if (!response.ok) {
				errorStatus = 'error';
				return;
			}
			const json: SharedLinkData = await response.json();
			if (new Date(json.expires_at) < new Date()) {
				errorStatus = 'expired';
				return;
			}
			data = json;
		} catch {
			errorStatus = 'error';
		} finally {
			isLoading = false;
		}
	});

	const sharedAt = $derived(
		data ? formatDate(data.created_at, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''
	);

	const expiresAt = $derived(
		data ? formatDate(data.expires_at, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''
	);

	const trends = $derived(data?.payload?.trends ?? []);
</script>

<svelte:head>
	<title>{$t('shared.page_title')} — TrendScope</title>
</svelte:head>

<div class="mx-auto max-w-3xl space-y-6 px-4 py-8">
	{#if isLoading}
		<div class="flex items-center justify-center py-20">
			<div class="h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent"></div>
		</div>
	{:else if errorStatus === 'not_found'}
		<div class="rounded-lg border border-gray-200 bg-white p-8 text-center">
			<p class="text-lg font-semibold text-gray-900">{$t('shared.not_found')}</p>
			<p class="mt-2 text-sm text-gray-500">{$t('shared.not_found_desc')}</p>
		</div>
	{:else if errorStatus === 'expired'}
		<div class="rounded-lg border border-gray-200 bg-white p-8 text-center">
			<p class="text-lg font-semibold text-gray-900">{$t('shared.expired')}</p>
			<p class="mt-2 text-sm text-gray-500">{$t('shared.expired_desc')}</p>
		</div>
	{:else if errorStatus === 'error'}
		<div class="rounded-lg border border-gray-200 bg-white p-8 text-center">
			<p class="text-lg font-semibold text-gray-900">{$t('shared.error')}</p>
			<p class="mt-2 text-sm text-gray-500">{$t('shared.error_desc')}</p>
		</div>
	{:else if data}
		<div>
			<h1 class="text-2xl font-bold text-gray-900">{$t('shared.title')}</h1>
			<div class="mt-2 flex flex-wrap gap-4 text-sm text-gray-500">
				<span>{$t('shared.shared_at')}: {sharedAt}</span>
				<span>{$t('shared.expires_at')}: {expiresAt}</span>
			</div>
		</div>

		<div class="space-y-3">
			{#each trends as trend (trend.id)}
				<div class="rounded-lg border border-gray-200 bg-white p-4">
					<div class="flex items-start justify-between">
						<div class="flex-1">
							<div class="flex items-center gap-2">
								<span class="text-base font-semibold text-gray-900">{trend.title}</span>
								<EarlyBadge score={trend.early_trend_score} />
							</div>
							<div class="mt-2 flex flex-wrap gap-1.5">
								{#each trend.keywords as keyword}
									<span class="inline-flex rounded-md bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
										{keyword}
									</span>
								{/each}
							</div>
						</div>
						<div class="ml-4 text-right">
							<p class="text-sm font-medium text-gray-900">{trend.score.toFixed(1)}</p>
							<p class="text-xs text-gray-500">{$t('trend.score')}</p>
						</div>
					</div>
					<div class="mt-3 flex items-center gap-4 text-xs text-gray-500">
						<span>{$t('trend.category')}: {trend.category}</span>
						<span>{$t('trend.first_seen')}: {formatDate(trend.created_at, { year: 'numeric', month: 'short', day: 'numeric' })}</span>
					</div>
				</div>
			{/each}
		</div>

		{#if trends.length === 0}
			<p class="text-center text-gray-500">{$t('status.no_results')}</p>
		{/if}

		<div class="text-center text-sm text-gray-400">
			<p>{$t('shared.powered_by')}</p>
		</div>

		<!-- CTA banner for non-logged-in users -->
		{#if !authStore.isAuthenticated}
			<div class="rounded-xl border border-blue-200 dark:border-blue-800 bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-950/30 dark:to-indigo-950/30 p-6 text-center">
				<div class="flex justify-center mb-3">
					<TrendingUp size={28} class="text-blue-500" />
				</div>
				<h3 class="text-base font-bold text-gray-900 dark:text-gray-100 mb-1">
					{$t('share.cta.title')}
				</h3>
				<p class="text-sm text-gray-600 dark:text-gray-400 mb-4">
					{$t('share.cta.desc')}
				</p>
				<div class="flex items-center justify-center gap-3">
					<a
						href="/auth/register"
						class="inline-flex items-center gap-1.5 rounded-md bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700"
					>
						{$t('share.cta.start')}
						<ArrowRight size={14} />
					</a>
					<a
						href="/"
						class="inline-flex items-center rounded-md border border-gray-300 dark:border-gray-600 px-4 py-2.5 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
					>
						{$t('share.cta.browse')}
					</a>
				</div>
			</div>
		{/if}
	{/if}
</div>
