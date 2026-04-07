<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { adminRequest, adminDownload } from '$lib/api/admin';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';
	import PageStateWrapper from '$lib/ui/PageStateWrapper.svelte';

	interface AuditItem {
		id: string | null;
		user_id: string | null;
		action: string;
		target_type: string | null;
		target_id: string | null;
		ip_address: string | null;
		detail: Record<string, unknown> | null;
		created_at: string | null;
	}

	interface AuditListResponse {
		logs: AuditItem[];
		total: number;
		page: number;
		page_size: number;
	}

	let logs = $state<AuditItem[]>([]);
	let total = $state(0);
	let page = $state(1);
	let filterUserId = $state('');
	let filterAction = $state('');
	let filterDateFrom = $state('');
	let filterDateTo = $state('');
	let loading = $state(true);
	let errorOpen = $state(false);
	let errorCode = $state('');

	function buildParams(): URLSearchParams {
		const params = new URLSearchParams({ page: String(page), page_size: '50' });
		if (filterUserId) params.set('user_id', filterUserId);
		if (filterAction) params.set('action', filterAction);
		if (filterDateFrom) params.set('date_from', new Date(filterDateFrom).toISOString());
		if (filterDateTo) params.set('date_to', new Date(filterDateTo).toISOString());
		return params;
	}

	async function fetchLogs(): Promise<void> {
		try {
			loading = true;
			const data = await adminRequest<AuditListResponse>(`/audit?${buildParams()}`);
			logs = data.logs;
			total = data.total;
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		} finally {
			loading = false;
		}
	}

	async function exportLogs(format: string): Promise<void> {
		try {
			const params = buildParams();
			params.set('format', format);
			await adminDownload(`/audit/export?${params}`, `audit_log.${format}`);
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		}
	}

	function applyFilter(): void {
		page = 1;
		fetchLogs();
	}

	onMount(() => {
		fetchLogs();
	});
</script>

<div>
	<div class="flex items-center justify-between mb-6">
		<h2 class="text-2xl font-bold text-gray-900">{$t('admin.audit.title')}</h2>
		<div class="flex gap-2">
			<button onclick={() => exportLogs('json')}
				class="rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50">{$t('admin.audit.export_json')}</button>
			<button onclick={() => exportLogs('csv')}
				class="rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50">{$t('admin.audit.export_csv')}</button>
		</div>
	</div>

	<div class="bg-white rounded-lg shadow p-4 mb-4">
		<div class="grid grid-cols-1 sm:grid-cols-4 gap-3">
			<input type="text" bind:value={filterUserId} placeholder={$t('admin.audit.filter_user_id')}
				class="rounded-md border border-gray-300 px-3 py-2 text-sm" />
			<input type="text" bind:value={filterAction} placeholder={$t('admin.audit.filter_action')}
				class="rounded-md border border-gray-300 px-3 py-2 text-sm" />
			<input type="date" bind:value={filterDateFrom}
				class="rounded-md border border-gray-300 px-3 py-2 text-sm" />
			<div class="flex gap-2">
				<input type="date" bind:value={filterDateTo}
					class="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm" />
				<button onclick={applyFilter}
					class="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">{$t('admin.audit.apply_filter')}</button>
			</div>
		</div>
	</div>

	<PageStateWrapper isLoading={loading} isEmpty={!loading && logs.length === 0}>
		{#snippet children()}
			<div class="bg-white rounded-lg shadow overflow-x-auto">
				<table class="min-w-[640px] w-full divide-y divide-gray-200">
					<thead class="bg-gray-50">
						<tr>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.audit.col_time')}</th>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.audit.col_user')}</th>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.audit.col_action')}</th>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.audit.col_target')}</th>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.audit.col_ip')}</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-200">
						{#each logs as log}
							<tr>
								<td class="px-4 py-3 text-xs text-gray-600">{log.created_at ?? '-'}</td>
								<td class="px-4 py-3 text-xs text-gray-600">{log.user_id ?? '-'}</td>
								<td class="px-4 py-3 text-xs font-medium text-gray-900">{log.action}</td>
								<td class="px-4 py-3 text-xs text-gray-600">{log.target_type ?? ''} {log.target_id ?? ''}</td>
								<td class="px-4 py-3 text-xs text-gray-500">{log.ip_address ?? '-'}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>

			<div class="mt-4 flex items-center justify-between">
				<p class="text-sm text-gray-600">{$t('admin.users.total')}: {total}</p>
				<div class="flex gap-2">
					<button disabled={page <= 1} onclick={() => { page--; fetchLogs(); }}
						class="rounded border px-3 py-1 text-sm disabled:opacity-50">{$t('admin.users.prev')}</button>
					<button disabled={page * 50 >= total} onclick={() => { page++; fetchLogs(); }}
						class="rounded border px-3 py-1 text-sm disabled:opacity-50">{$t('admin.users.next')}</button>
				</div>
			</div>
		{/snippet}
	</PageStateWrapper>
</div>

<ErrorModal open={errorOpen} {errorCode} onClose={() => (errorOpen = false)} onRetry={fetchLogs} />
