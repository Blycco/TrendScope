<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { adminRequest } from '$lib/api/admin';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';

	interface User {
		id: string;
		email: string;
		display_name: string | null;
		role: string;
		plan: string;
		locale: string;
		is_active: boolean;
		created_at: string | null;
	}

	interface UserListResponse {
		users: User[];
		total: number;
		page: number;
		page_size: number;
	}

	let users = $state<User[]>([]);
	let total = $state(0);
	let page = $state(1);
	let search = $state('');
	let loading = $state(true);
	let errorOpen = $state(false);
	let errorCode = $state('');
	let deleteConfirmId = $state<string | null>(null);

	async function fetchUsers(): Promise<void> {
		try {
			loading = true;
			const params = new URLSearchParams({ page: String(page), page_size: '20' });
			if (search) params.set('search', search);
			const data = await adminRequest<UserListResponse>(`/users?${params}`);
			users = data.users;
			total = data.total;
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		} finally {
			loading = false;
		}
	}

	async function updateUser(userId: string, field: string, value: string | boolean): Promise<void> {
		try {
			await adminRequest(`/users/${userId}`, {
				method: 'PATCH',
				body: { [field]: value }
			});
			await fetchUsers();
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		}
	}

	async function deleteUser(userId: string): Promise<void> {
		try {
			await adminRequest(`/users/${userId}`, { method: 'DELETE' });
			deleteConfirmId = null;
			await fetchUsers();
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		}
	}

	function handleSearch(): void {
		page = 1;
		fetchUsers();
	}

	onMount(() => {
		fetchUsers();
	});
</script>

<div>
	<h2 class="text-2xl font-bold text-gray-900 mb-6">{$t('admin.users.title')}</h2>

	<div class="mb-4 flex gap-2">
		<input
			type="text"
			bind:value={search}
			placeholder={$t('admin.users.search')}
			class="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm"
			onkeydown={(e) => { if (e.key === 'Enter') handleSearch(); }}
		/>
		<button
			onclick={handleSearch}
			class="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
		>
			{$t('admin.users.search')}
		</button>
	</div>

	{#if loading}
		<p class="text-gray-500">{$t('status.loading')}</p>
	{:else}
		<div class="bg-white rounded-lg shadow overflow-x-auto">
			<table class="min-w-full divide-y divide-gray-200">
				<thead class="bg-gray-50">
					<tr>
						<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.users.col_email')}</th>
						<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.users.col_name')}</th>
						<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.users.col_role')}</th>
						<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.users.col_plan')}</th>
						<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.users.col_status')}</th>
						<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.users.col_actions')}</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-gray-200">
					{#each users as user}
						<tr>
							<td class="px-4 py-3 text-sm text-gray-900">{user.email}</td>
							<td class="px-4 py-3 text-sm text-gray-600">{user.display_name ?? '-'}</td>
							<td class="px-4 py-3 text-sm text-gray-600">{user.role}</td>
							<td class="px-4 py-3">
								<select
									class="text-sm border border-gray-300 rounded px-2 py-1"
									value={user.plan}
									onchange={(e) => updateUser(user.id, 'plan', e.currentTarget.value)}
								>
									<option value="free">Free</option>
									<option value="pro">Pro</option>
									<option value="business">Business</option>
									<option value="enterprise">Enterprise</option>
								</select>
							</td>
							<td class="px-4 py-3">
								<button
									class="text-xs px-2 py-1 rounded {user.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}"
									onclick={() => updateUser(user.id, 'is_active', !user.is_active)}
								>
									{user.is_active ? $t('admin.users.active') : $t('admin.users.suspended')}
								</button>
							</td>
							<td class="px-4 py-3">
								<button
									class="text-xs text-red-600 hover:text-red-800"
									onclick={() => (deleteConfirmId = user.id)}
								>
									{$t('button.delete')}
								</button>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>

		<div class="mt-4 flex items-center justify-between">
			<p class="text-sm text-gray-600">
				{$t('admin.users.total')}: {total}
			</p>
			<div class="flex gap-2">
				<button
					disabled={page <= 1}
					onclick={() => { page--; fetchUsers(); }}
					class="rounded border px-3 py-1 text-sm disabled:opacity-50"
				>
					{$t('admin.users.prev')}
				</button>
				<button
					disabled={page * 20 >= total}
					onclick={() => { page++; fetchUsers(); }}
					class="rounded border px-3 py-1 text-sm disabled:opacity-50"
				>
					{$t('admin.users.next')}
				</button>
			</div>
		</div>
	{/if}
</div>

{#if deleteConfirmId}
	<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50" role="dialog" aria-modal="true">
		<div class="bg-white rounded-lg p-6 max-w-sm mx-4 shadow-xl">
			<h3 class="text-lg font-semibold">{$t('admin.users.delete_confirm_title')}</h3>
			<p class="mt-2 text-sm text-gray-600">{$t('admin.users.delete_confirm_message')}</p>
			<div class="mt-4 flex gap-3 justify-end">
				<button
					onclick={() => (deleteConfirmId = null)}
					class="rounded-md border px-4 py-2 text-sm"
				>
					{$t('button.cancel')}
				</button>
				<button
					onclick={() => { if (deleteConfirmId) deleteUser(deleteConfirmId); }}
					class="rounded-md bg-red-600 px-4 py-2 text-sm text-white hover:bg-red-700"
				>
					{$t('button.delete')}
				</button>
			</div>
		</div>
	</div>
{/if}

<ErrorModal
	open={errorOpen}
	{errorCode}
	onClose={() => (errorOpen = false)}
	onRetry={fetchUsers}
/>
