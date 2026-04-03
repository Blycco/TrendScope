<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { adminRequest } from '$lib/api/admin';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';

	interface Subscription {
		id: string;
		user_id: string;
		plan: string;
		status: string;
		provider: string | null;
		provider_sub_id: string | null;
		started_at: string | null;
		expires_at: string | null;
		created_at: string | null;
	}

	interface SubscriptionListResponse {
		subscriptions: Subscription[];
		total: number;
		page: number;
		page_size: number;
	}

	let subscriptions = $state<Subscription[]>([]);
	let total = $state(0);
	let page = $state(1);
	let loading = $state(true);
	let errorOpen = $state(false);
	let errorCode = $state('');
	let refundConfirmId = $state<string | null>(null);
	let refundReason = $state('');

	async function fetchSubscriptions(): Promise<void> {
		try {
			loading = true;
			const params = new URLSearchParams({ page: String(page), page_size: '20' });
			const data = await adminRequest<SubscriptionListResponse>(`/subscriptions?${params}`);
			subscriptions = data.subscriptions;
			total = data.total;
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		} finally {
			loading = false;
		}
	}

	async function refundSubscription(): Promise<void> {
		if (!refundConfirmId || !refundReason) return;
		try {
			await adminRequest(`/subscriptions/${refundConfirmId}/refund`, {
				method: 'POST',
				body: { reason: refundReason }
			});
			refundConfirmId = null;
			refundReason = '';
			await fetchSubscriptions();
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		}
	}

	onMount(() => {
		fetchSubscriptions();
	});
</script>

<div>
	<h2 class="text-2xl font-bold text-gray-900 mb-6">{$t('admin.subscriptions.title')}</h2>

	{#if loading}
		<p class="text-gray-500">{$t('status.loading')}</p>
	{:else}
		<div class="bg-white rounded-lg shadow overflow-x-auto">
			<table class="min-w-[640px] w-full divide-y divide-gray-200">
				<thead class="bg-gray-50">
					<tr>
						<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.subscriptions.col_user')}</th>
						<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.subscriptions.col_plan')}</th>
						<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.subscriptions.col_status')}</th>
						<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.subscriptions.col_provider')}</th>
						<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.subscriptions.col_expires')}</th>
						<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.subscriptions.col_actions')}</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-gray-200">
					{#each subscriptions as sub}
						<tr>
							<td class="px-4 py-3 text-sm text-gray-900">{sub.user_id}</td>
							<td class="px-4 py-3 text-sm text-gray-600">{sub.plan}</td>
							<td class="px-4 py-3">
								<span class="text-xs px-2 py-1 rounded {sub.status === 'active' ? 'bg-green-100 text-green-800' : sub.status === 'refunded' ? 'bg-yellow-100 text-yellow-800' : 'bg-gray-100 text-gray-800'}">
									{sub.status}
								</span>
							</td>
							<td class="px-4 py-3 text-sm text-gray-600">{sub.provider ?? '-'}</td>
							<td class="px-4 py-3 text-sm text-gray-600">{sub.expires_at ?? '-'}</td>
							<td class="px-4 py-3">
								{#if sub.status === 'active' || sub.status === 'cancelled'}
									<button
										class="text-xs text-orange-600 hover:text-orange-800"
										onclick={() => (refundConfirmId = sub.id)}
									>
										{$t('admin.subscriptions.refund')}
									</button>
								{/if}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>

		<div class="mt-4 flex items-center justify-between">
			<p class="text-sm text-gray-600">{$t('admin.users.total')}: {total}</p>
			<div class="flex gap-2">
				<button disabled={page <= 1} onclick={() => { page--; fetchSubscriptions(); }}
					class="rounded border px-3 py-1 text-sm disabled:opacity-50">{$t('admin.users.prev')}</button>
				<button disabled={page * 20 >= total} onclick={() => { page++; fetchSubscriptions(); }}
					class="rounded border px-3 py-1 text-sm disabled:opacity-50">{$t('admin.users.next')}</button>
			</div>
		</div>
	{/if}
</div>

{#if refundConfirmId}
	<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50" role="dialog" aria-modal="true">
		<div class="bg-white rounded-lg p-6 max-w-sm mx-4 shadow-xl">
			<h3 class="text-lg font-semibold">{$t('admin.subscriptions.refund_confirm_title')}</h3>
			<textarea
				bind:value={refundReason}
				placeholder={$t('admin.subscriptions.refund_reason')}
				class="mt-3 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
				rows="3"
			></textarea>
			<div class="mt-4 flex gap-3 justify-end">
				<button onclick={() => { refundConfirmId = null; refundReason = ''; }}
					class="rounded-md border px-4 py-2 text-sm">{$t('button.cancel')}</button>
				<button onclick={refundSubscription} disabled={!refundReason}
					class="rounded-md bg-orange-600 px-4 py-2 text-sm text-white hover:bg-orange-700 disabled:opacity-50">{$t('admin.subscriptions.refund')}</button>
			</div>
		</div>
	</div>
{/if}

<ErrorModal open={errorOpen} {errorCode} onClose={() => (errorOpen = false)} onRetry={fetchSubscriptions} />
