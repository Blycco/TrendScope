<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount, onDestroy } from 'svelte';
	import { adminRequest } from '$lib/api/admin';

	interface QuotaAlert {
		id: string;
		service_name: string;
		error_type: string;
		status_code: number | null;
		detail: string | null;
		endpoint_url: string | null;
		is_dismissed: boolean;
		dismissed_by: string | null;
		dismissed_at: string | null;
		email_sent: boolean;
		created_at: string | null;
	}

	interface AlertListResponse {
		alerts: QuotaAlert[];
		total: number;
		page: number;
		page_size: number;
	}

	let alerts = $state<QuotaAlert[]>([]);
	let total = $state(0);
	let page = $state(1);
	let pageSize = $state(50);
	let filterService = $state('');
	let filterDismissed = $state<string>('false');
	let loading = $state(true);
	let pollTimer: ReturnType<typeof setInterval> | null = null;

	const services = ['google_oauth', 'kakao_oauth', 'youtube', 'gemini', 'openai', 'reddit'];

	async function fetchAlerts(): Promise<void> {
		try {
			loading = true;
			const params = new URLSearchParams();
			if (filterService) params.set('service_name', filterService);
			if (filterDismissed !== '') params.set('is_dismissed', filterDismissed);
			params.set('page', String(page));
			params.set('page_size', String(pageSize));

			const res = await adminRequest<AlertListResponse>(`/quota-alerts?${params}`);
			alerts = res.alerts;
			total = res.total;
		} catch {
			alerts = [];
			total = 0;
		} finally {
			loading = false;
		}
	}

	async function dismiss(alertId: string): Promise<void> {
		try {
			await adminRequest(`/quota-alerts/${alertId}/dismiss`, { method: 'POST' });
			await fetchAlerts();
		} catch {
			// ignore
		}
	}

	function startPolling(): void {
		pollTimer = setInterval(() => {
			if (document.visibilityState === 'visible') {
				fetchAlerts();
			}
		}, 10_000);
	}

	onMount(() => {
		fetchAlerts();
		startPolling();
	});

	onDestroy(() => {
		if (pollTimer) clearInterval(pollTimer);
	});

	function formatDate(iso: string | null): string {
		if (!iso) return '-';
		return new Date(iso).toLocaleString();
	}

	function truncate(text: string | null, max: number = 80): string {
		if (!text) return '-';
		return text.length > max ? text.slice(0, max) + '...' : text;
	}

	let totalPages = $derived(Math.max(1, Math.ceil(total / pageSize)));
</script>

<div>
	<h2 class="text-2xl font-bold text-gray-900 mb-6">{$t('admin.quota_alerts.title')}</h2>

	<!-- Filters -->
	<div class="flex gap-4 mb-4">
		<select
			bind:value={filterService}
			onchange={() => { page = 1; fetchAlerts(); }}
			class="border border-gray-300 rounded px-3 py-2 text-sm"
		>
			<option value="">{$t('admin.quota_alerts.filter_all')}</option>
			{#each services as svc}
				<option value={svc}>{svc}</option>
			{/each}
		</select>

		<select
			bind:value={filterDismissed}
			onchange={() => { page = 1; fetchAlerts(); }}
			class="border border-gray-300 rounded px-3 py-2 text-sm"
		>
			<option value="false">{$t('admin.quota_alerts.active')}</option>
			<option value="true">{$t('admin.quota_alerts.dismissed')}</option>
			<option value="">{$t('admin.quota_alerts.filter_all')}</option>
		</select>
	</div>

	<!-- Table -->
	{#if loading}
		<p class="text-gray-500">{$t('status.loading')}</p>
	{:else if alerts.length === 0}
		<p class="text-gray-500">{$t('admin.quota_alerts.no_alerts')}</p>
	{:else}
		<div class="overflow-x-auto">
			<table class="min-w-full bg-white border border-gray-200 rounded-lg">
				<thead class="bg-gray-50">
					<tr>
						<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.quota_alerts.col_service')}</th>
						<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.quota_alerts.col_error_type')}</th>
						<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.quota_alerts.col_detail')}</th>
						<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.quota_alerts.col_email_sent')}</th>
						<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.quota_alerts.col_created_at')}</th>
						<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.quota_alerts.col_status')}</th>
						<th class="px-4 py-3"></th>
					</tr>
				</thead>
				<tbody class="divide-y divide-gray-200">
					{#each alerts as alert}
						<tr class={alert.is_dismissed ? 'bg-gray-50' : 'bg-white'}>
							<td class="px-4 py-3 text-sm font-medium text-gray-900">{alert.service_name}</td>
							<td class="px-4 py-3 text-sm text-gray-600">{alert.error_type}</td>
							<td class="px-4 py-3 text-sm text-gray-600" title={alert.detail ?? ''}>{truncate(alert.detail)}</td>
							<td class="px-4 py-3 text-sm text-gray-600">{alert.email_sent ? $t('admin.quota_alerts.yes') : $t('admin.quota_alerts.no')}</td>
							<td class="px-4 py-3 text-sm text-gray-600">{formatDate(alert.created_at)}</td>
							<td class="px-4 py-3 text-sm">
								{#if alert.is_dismissed}
									<span class="inline-flex items-center rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600">{$t('admin.quota_alerts.dismissed')}</span>
								{:else}
									<span class="inline-flex items-center rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-700">{$t('admin.quota_alerts.active')}</span>
								{/if}
							</td>
							<td class="px-4 py-3 text-sm">
								{#if !alert.is_dismissed}
									<button
										onclick={() => dismiss(alert.id)}
										class="text-sm text-blue-600 hover:text-blue-800 font-medium"
									>
										{$t('admin.quota_alerts.dismiss')}
									</button>
								{/if}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>

		<!-- Pagination -->
		{#if totalPages > 1}
			<div class="flex justify-center gap-2 mt-4">
				<button
					onclick={() => { page = Math.max(1, page - 1); fetchAlerts(); }}
					disabled={page <= 1}
					class="px-3 py-1 text-sm border rounded disabled:opacity-50"
				>
					&laquo;
				</button>
				<span class="px-3 py-1 text-sm text-gray-600">{page} / {totalPages}</span>
				<button
					onclick={() => { page = Math.min(totalPages, page + 1); fetchAlerts(); }}
					disabled={page >= totalPages}
					class="px-3 py-1 text-sm border rounded disabled:opacity-50"
				>
					&raquo;
				</button>
			</div>
		{/if}
	{/if}
</div>
