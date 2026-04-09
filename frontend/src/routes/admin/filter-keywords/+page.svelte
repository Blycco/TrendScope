<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { adminRequest } from '$lib/api/admin';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';
	import PageStateWrapper from '$lib/ui/PageStateWrapper.svelte';

	interface FilterKeyword {
		id: string;
		keyword: string;
		category: string;
		source: string;
		is_active: boolean;
		confidence: number;
		created_at: string;
		updated_at: string;
	}

	interface ListResponse {
		items: FilterKeyword[];
		total: number;
	}

	type TabType = 'pending' | 'active' | 'all';

	const CATEGORIES = ['ad', 'gambling', 'adult', 'obituary', 'irrelevant', 'custom'];

	let activeTab = $state<TabType>('pending');
	let items = $state<FilterKeyword[]>([]);
	let loading = $state(true);
	let selectedIds = $state<Set<string>>(new Set());
	let newKeyword = $state('');
	let newCategory = $state('ad');
	let errorOpen = $state(false);
	let errorCode = $state('');

	function sourceLabel(source: string): string {
		if (source === 'ai_suggested') return $t('admin.filter_keywords.source_ai');
		if (source === 'system') return $t('admin.filter_keywords.source_system');
		return $t('admin.filter_keywords.source_manual');
	}

	function sourceBadgeClass(source: string): string {
		if (source === 'ai_suggested') return 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400';
		if (source === 'system') return 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300';
		return 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400';
	}

	async function fetchItems(): Promise<void> {
		try {
			loading = true;
			const params = new URLSearchParams();
			if (activeTab === 'pending') {
				params.set('source', 'ai_suggested');
				params.set('is_active', 'false');
			} else if (activeTab === 'active') {
				params.set('is_active', 'true');
			}
			params.set('limit', '200');
			const data = await adminRequest<ListResponse>(`/filter-keywords?${params}`);
			items = data.items;
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		} finally {
			loading = false;
		}
	}

	async function approve(id: string): Promise<void> {
		try {
			await adminRequest(`/filter-keywords/${id}/approve`, { method: 'POST' });
			await fetchItems();
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		}
	}

	async function toggleActive(id: string, current: boolean): Promise<void> {
		try {
			await adminRequest(`/filter-keywords/${id}`, {
				method: 'PATCH',
				body: { is_active: !current }
			});
			await fetchItems();
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		}
	}

	async function deleteKeyword(id: string): Promise<void> {
		try {
			await adminRequest(`/filter-keywords/${id}`, { method: 'DELETE' });
			selectedIds.delete(id);
			selectedIds = new Set(selectedIds);
			await fetchItems();
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		}
	}

	async function bulkApprove(): Promise<void> {
		for (const id of selectedIds) {
			try {
				await adminRequest(`/filter-keywords/${id}/approve`, { method: 'POST' });
			} catch {
				// continue others
			}
		}
		selectedIds = new Set();
		await fetchItems();
	}

	async function bulkDelete(): Promise<void> {
		for (const id of selectedIds) {
			try {
				await adminRequest(`/filter-keywords/${id}`, { method: 'DELETE' });
			} catch {
				// continue others
			}
		}
		selectedIds = new Set();
		await fetchItems();
	}

	async function addKeyword(): Promise<void> {
		if (!newKeyword.trim()) return;
		try {
			await adminRequest('/filter-keywords', {
				method: 'POST',
				body: { keyword: newKeyword.trim(), category: newCategory }
			});
			newKeyword = '';
			await fetchItems();
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		}
	}

	async function reloadCache(): Promise<void> {
		try {
			await adminRequest('/filter-keywords/reload', { method: 'POST' });
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		}
	}

	function toggleSelect(id: string): void {
		const next = new Set(selectedIds);
		if (next.has(id)) next.delete(id);
		else next.add(id);
		selectedIds = next;
	}

	$effect(() => {
		const _tab = activeTab;
		fetchItems();
	});

	onMount(fetchItems);
</script>

<div>
	<div class="flex items-center justify-between mb-4">
		<h2 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{$t('admin.filter_keywords.title')}</h2>
		<button
			class="text-sm bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-200 px-3 py-1.5 rounded hover:bg-gray-300 dark:hover:bg-gray-600"
			onclick={reloadCache}
		>
			{$t('admin.filter_keywords.reload_cache')}
		</button>
	</div>

	<!-- Tabs -->
	<div class="flex border-b border-gray-200 dark:border-gray-700 mb-6">
		{#each ([{ tab: 'pending' as TabType, key: 'admin.filter_keywords.tab_pending' }, { tab: 'active' as TabType, key: 'admin.filter_keywords.tab_active' }, { tab: 'all' as TabType, key: 'admin.filter_keywords.tab_all' }]) as item}
			<button
				class="px-4 py-2 text-sm font-medium {activeTab === item.tab ? 'border-b-2 border-blue-600 text-blue-600' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'}"
				onclick={() => { activeTab = item.tab; selectedIds = new Set(); }}
			>
				{$t(item.key)}
			</button>
		{/each}
	</div>

	<!-- Bulk actions (pending tab) -->
	{#if activeTab === 'pending' && selectedIds.size > 0}
		<div class="flex gap-2 mb-4">
			<button class="text-xs bg-green-600 text-white px-3 py-1 rounded hover:bg-green-700" onclick={bulkApprove}>
				{$t('admin.filter_keywords.bulk_approve')} ({selectedIds.size})
			</button>
			<button class="text-xs bg-red-600 text-white px-3 py-1 rounded hover:bg-red-700" onclick={bulkDelete}>
				{$t('admin.filter_keywords.bulk_delete')} ({selectedIds.size})
			</button>
		</div>
	{/if}

	<!-- Add form -->
	<div class="flex items-center gap-2 mb-4">
		<input
			type="text"
			class="text-sm border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded px-3 py-1.5 w-48"
			placeholder={$t('admin.filter_keywords.keyword_placeholder')}
			bind:value={newKeyword}
			onkeydown={(e) => e.key === 'Enter' && addKeyword()}
		/>
		<select class="text-sm border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded px-2 py-1.5" bind:value={newCategory}>
			{#each CATEGORIES as cat}
				<option value={cat}>{cat}</option>
			{/each}
		</select>
		<button class="text-sm bg-blue-600 text-white px-4 py-1.5 rounded hover:bg-blue-700" onclick={addKeyword}>
			{$t('admin.filter_keywords.add_keyword')}
		</button>
	</div>

	<PageStateWrapper isLoading={loading} isEmpty={!loading && items.length === 0}>
		{#snippet empty()}
			<p class="text-gray-500">{$t('admin.filter_keywords.no_keywords')}</p>
		{/snippet}
		{#snippet children()}
			<div class="bg-white dark:bg-gray-800 rounded-lg shadow overflow-x-auto">
				<table class="min-w-[640px] w-full divide-y divide-gray-200 dark:divide-gray-700">
					<thead class="bg-gray-50 dark:bg-gray-700">
						<tr>
							{#if activeTab === 'pending'}
								<th class="px-3 py-3 w-8"><input type="checkbox" onchange={(e) => { if (e.currentTarget.checked) selectedIds = new Set(items.map(i => i.id)); else selectedIds = new Set(); }} /></th>
							{/if}
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{$t('admin.filter_keywords.col_keyword')}</th>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{$t('admin.filter_keywords.col_category')}</th>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{$t('admin.filter_keywords.col_source')}</th>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{$t('admin.filter_keywords.col_confidence')}</th>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{$t('admin.filter_keywords.col_active')}</th>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{$t('admin.filter_keywords.col_actions')}</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-200 dark:divide-gray-700">
						{#each items as item}
							<tr>
								{#if activeTab === 'pending'}
									<td class="px-3 py-2"><input type="checkbox" checked={selectedIds.has(item.id)} onchange={() => toggleSelect(item.id)} /></td>
								{/if}
								<td class="px-4 py-3 text-sm font-medium text-gray-900 dark:text-gray-100">{item.keyword}</td>
								<td class="px-4 py-3 text-xs text-gray-600 dark:text-gray-400">{item.category}</td>
								<td class="px-4 py-3">
									<span class="text-xs px-2 py-0.5 rounded-full {sourceBadgeClass(item.source)}">{sourceLabel(item.source)}</span>
								</td>
								<td class="px-4 py-3 text-xs text-gray-600 dark:text-gray-400">{Math.round(item.confidence * 100)}%</td>
								<td class="px-4 py-3">
									<span class="text-xs px-2 py-1 rounded {item.is_active ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-400' : 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-400'}">
										{item.is_active ? $t('admin.users.active') : $t('admin.users.suspended')}
									</span>
								</td>
								<td class="px-4 py-3 text-xs space-x-2">
									{#if item.source === 'ai_suggested' && !item.is_active}
										<button class="text-green-600 hover:text-green-800" onclick={() => approve(item.id)}>{$t('admin.filter_keywords.approve')}</button>
									{/if}
									<button class="text-blue-600 hover:text-blue-800" onclick={() => toggleActive(item.id, item.is_active)}>
										{item.is_active ? $t('admin.filter_keywords.deactivate') : $t('admin.filter_keywords.activate')}
									</button>
									<button class="text-red-600 hover:text-red-800" onclick={() => deleteKeyword(item.id)}>{$t('admin.filter_keywords.delete')}</button>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/snippet}
	</PageStateWrapper>
</div>

<ErrorModal open={errorOpen} errorCode={errorCode} messageKey="error.server" onClose={() => (errorOpen = false)} onRetry={fetchItems} />
