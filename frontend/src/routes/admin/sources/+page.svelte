<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { adminRequest } from '$lib/api/admin';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';

	interface Source {
		id: string;
		source_name: string;
		quota_limit: number;
		quota_used: number;
		is_active: boolean | null;
		updated_at: string | null;
	}

	interface SourceListResponse {
		sources: Source[];
	}

	let sources = $state<Source[]>([]);
	let loading = $state(true);
	let errorOpen = $state(false);
	let errorCode = $state('');

	async function fetchSources(): Promise<void> {
		try {
			loading = true;
			const data = await adminRequest<SourceListResponse>('/sources');
			sources = data.sources;
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		} finally {
			loading = false;
		}
	}

	async function updateQuota(sourceId: string, quotaLimit: number): Promise<void> {
		try {
			await adminRequest(`/sources/${sourceId}`, {
				method: 'PATCH',
				body: { quota_limit: quotaLimit }
			});
			await fetchSources();
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		}
	}

	async function resetQuota(sourceId: string): Promise<void> {
		try {
			await adminRequest(`/sources/${sourceId}/reset`, { method: 'POST' });
			await fetchSources();
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		}
	}

	onMount(() => {
		fetchSources();
	});
</script>

<div>
	<h2 class="text-2xl font-bold text-gray-900 mb-6">{$t('admin.sources.title')}</h2>

	{#if loading}
		<p class="text-gray-500">{$t('status.loading')}</p>
	{:else}
		<div class="bg-white rounded-lg shadow overflow-x-auto">
			<table class="min-w-full divide-y divide-gray-200">
				<thead class="bg-gray-50">
					<tr>
						<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.sources.col_name')}</th>
						<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.sources.col_quota_limit')}</th>
						<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.sources.col_quota_used')}</th>
						<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.sources.col_status')}</th>
						<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.users.col_actions')}</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-gray-200">
					{#each sources as source}
						<tr>
							<td class="px-4 py-3 text-sm font-medium text-gray-900">{source.source_name}</td>
							<td class="px-4 py-3">
								<input
									type="number"
									value={source.quota_limit}
									class="w-24 text-sm border border-gray-300 rounded px-2 py-1"
									onchange={(e) => updateQuota(source.id, Number(e.currentTarget.value))}
								/>
							</td>
							<td class="px-4 py-3 text-sm text-gray-600">
								{source.quota_used}
								{#if source.quota_limit > 0}
									<span class="text-xs text-gray-400 ml-1">
										({Math.round((source.quota_used / source.quota_limit) * 100)}%)
									</span>
								{/if}
							</td>
							<td class="px-4 py-3">
								<span class="text-xs px-2 py-1 rounded {source.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">
									{source.is_active ? $t('admin.users.active') : $t('admin.users.suspended')}
								</span>
							</td>
							<td class="px-4 py-3">
								<button
									class="text-xs text-blue-600 hover:text-blue-800"
									onclick={() => resetQuota(source.id)}
								>
									{$t('admin.sources.reset_quota')}
								</button>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>

<ErrorModal open={errorOpen} {errorCode} onClose={() => (errorOpen = false)} onRetry={fetchSources} />
