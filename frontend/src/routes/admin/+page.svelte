<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { adminRequest } from '$lib/api/admin';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';

	let totalUsers = $state(0);
	let activeSubscriptions = $state(0);
	let apiUsageCount = $state(0);
	let todayTrends = $state(0);
	let alertCount = $state(0);
	let loading = $state(true);
	let errorOpen = $state(false);
	let errorCode = $state('');

	interface AnalyticsData {
		metric: string;
		data: Record<string, unknown>;
	}

	async function fetchAnalytics(): Promise<void> {
		try {
			loading = true;
			const [users, revenue, trends, apiUsage] = await Promise.all([
				adminRequest<AnalyticsData>('/analytics/users'),
				adminRequest<AnalyticsData>('/analytics/revenue'),
				adminRequest<AnalyticsData>('/analytics/trends'),
				adminRequest<AnalyticsData>('/analytics/api_usage')
			]);
			totalUsers = (users.data.total as number) ?? 0;
			activeSubscriptions = (revenue.data.active_subscriptions as number) ?? 0;
			todayTrends = (trends.data.today as number) ?? 0;
			apiUsageCount = (apiUsage.data.users_with_api_usage as number) ?? 0;
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		} finally {
			loading = false;
		}
	}

	async function fetchAlertCount(): Promise<void> {
		try {
			const res = await adminRequest<{ active_count: number }>('/quota-alerts/count');
			alertCount = res.active_count;
		} catch {
			alertCount = 0;
		}
	}

	onMount(() => {
		fetchAnalytics();
		fetchAlertCount();
	});

	const cards = $derived([
		{ labelKey: 'admin.home.total_users', value: totalUsers },
		{ labelKey: 'admin.home.active_subscriptions', value: activeSubscriptions },
		{ labelKey: 'admin.home.api_usage', value: apiUsageCount },
		{ labelKey: 'admin.home.today_trends', value: todayTrends }
	]);
</script>

<div>
	{#if alertCount > 0}
		<div class="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 flex items-center justify-between">
			<span class="text-sm text-red-800">{$t('admin.quota_alerts.banner', { values: { count: alertCount } })}</span>
			<a href="/admin/quota-alerts" class="text-sm font-medium text-red-600 hover:text-red-800 underline">{$t('admin.quota_alerts.view_all')}</a>
		</div>
	{/if}

	<h2 class="text-2xl font-bold text-gray-900 mb-6">{$t('admin.home.title')}</h2>

	{#if loading}
		<p class="text-gray-500">{$t('status.loading')}</p>
	{:else}
		<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
			{#each cards as card}
				<div class="bg-white rounded-lg shadow p-6">
					<p class="text-sm text-gray-500">{$t(card.labelKey)}</p>
					<p class="mt-2 text-3xl font-bold text-gray-900">{card.value}</p>
				</div>
			{/each}
		</div>
	{/if}
</div>

<ErrorModal
	open={errorOpen}
	{errorCode}
	onClose={() => (errorOpen = false)}
	onRetry={fetchAnalytics}
/>
