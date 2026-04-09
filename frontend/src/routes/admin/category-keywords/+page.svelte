<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { adminRequest } from '$lib/api/admin';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';
	import PageStateWrapper from '$lib/ui/PageStateWrapper.svelte';

	interface CategoryKeyword {
		id: string;
		keyword: string;
		category: string;
		weight: number;
		locale: string;
		is_active: boolean;
		created_at: string;
	}

	interface ListResponse {
		items: CategoryKeyword[];
		total: number;
	}

	const CATEGORIES = ['sports', 'tech', 'economy', 'entertainment', 'science', 'politics', 'society'];

	let activeCategory = $state(CATEGORIES[0]);
	let items = $state<CategoryKeyword[]>([]);
	let loading = $state(true);
	let newKeyword = $state('');
	let newWeight = $state(1.0);
	let errorOpen = $state(false);
	let errorCode = $state('');

	async function fetchItems(): Promise<void> {
		try {
			loading = true;
			const data = await adminRequest<ListResponse>(`/category-keywords?category=${activeCategory}`);
			items = data.items;
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		} finally {
			loading = false;
		}
	}

	async function addKeyword(): Promise<void> {
		if (!newKeyword.trim()) return;
		try {
			await adminRequest('/category-keywords', {
				method: 'POST',
				body: { keyword: newKeyword.trim(), category: activeCategory, weight: newWeight }
			});
			newKeyword = '';
			newWeight = 1.0;
			await fetchItems();
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		}
	}

	async function updateWeight(id: string, weight: number): Promise<void> {
		try {
			await adminRequest(`/category-keywords/${id}`, {
				method: 'PATCH',
				body: { weight }
			});
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		}
	}

	async function deleteKeyword(id: string): Promise<void> {
		try {
			await adminRequest(`/category-keywords/${id}`, { method: 'DELETE' });
			await fetchItems();
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		}
	}

	async function reloadCache(): Promise<void> {
		try {
			await adminRequest('/category-keywords/reload', { method: 'POST' });
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		}
	}

	$effect(() => {
		const _cat = activeCategory;
		fetchItems();
	});

	onMount(fetchItems);
</script>

<div>
	<div class="flex items-center justify-between mb-4">
		<h2 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{$t('admin.category_keywords.title')}</h2>
		<button
			class="text-sm bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-200 px-3 py-1.5 rounded hover:bg-gray-300 dark:hover:bg-gray-600"
			onclick={reloadCache}
		>
			{$t('admin.category_keywords.reload_cache')}
		</button>
	</div>

	<!-- Category tabs -->
	<div class="flex flex-wrap border-b border-gray-200 dark:border-gray-700 mb-6">
		{#each CATEGORIES as cat}
			<button
				class="px-3 py-2 text-sm font-medium {activeCategory === cat ? 'border-b-2 border-blue-600 text-blue-600' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'}"
				onclick={() => (activeCategory = cat)}
			>
				{cat}
			</button>
		{/each}
	</div>

	<!-- Add form -->
	<div class="flex items-center gap-2 mb-6">
		<input
			type="text"
			class="text-sm border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded px-3 py-1.5 w-40"
			placeholder={$t('admin.category_keywords.keyword_placeholder')}
			bind:value={newKeyword}
			onkeydown={(e) => e.key === 'Enter' && addKeyword()}
		/>
		<input
			type="range"
			min="0.5"
			max="2.0"
			step="0.1"
			class="w-24"
			bind:value={newWeight}
		/>
		<span class="text-sm text-gray-600 dark:text-gray-400 w-8">{newWeight.toFixed(1)}</span>
		<button class="text-sm bg-blue-600 text-white px-4 py-1.5 rounded hover:bg-blue-700" onclick={addKeyword}>
			{$t('admin.category_keywords.add_keyword')}
		</button>
	</div>

	<PageStateWrapper isLoading={loading} isEmpty={!loading && items.length === 0}>
		{#snippet empty()}
			<p class="text-gray-500">{$t('admin.category_keywords.no_keywords')}</p>
		{/snippet}
		{#snippet children()}
			<div class="bg-white dark:bg-gray-800 rounded-lg shadow overflow-x-auto">
				<table class="min-w-[480px] w-full divide-y divide-gray-200 dark:divide-gray-700">
					<thead class="bg-gray-50 dark:bg-gray-700">
						<tr>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{$t('admin.category_keywords.col_keyword')}</th>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{$t('admin.category_keywords.col_weight')}</th>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{$t('admin.category_keywords.col_actions')}</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-200 dark:divide-gray-700">
						{#each items as item}
							<tr>
								<td class="px-4 py-3 text-sm font-medium text-gray-900 dark:text-gray-100">{item.keyword}</td>
								<td class="px-4 py-3">
									<div class="flex items-center gap-2">
										<input
											type="range"
											min="0.5"
											max="2.0"
											step="0.1"
											value={item.weight}
											class="w-20"
											onchange={(e) => updateWeight(item.id, parseFloat(e.currentTarget.value))}
										/>
										<span class="text-xs text-gray-600 dark:text-gray-400 w-8">{item.weight.toFixed(1)}</span>
									</div>
								</td>
								<td class="px-4 py-3">
									<button class="text-xs text-red-600 hover:text-red-800" onclick={() => deleteKeyword(item.id)}>
										{$t('admin.category_keywords.delete')}
									</button>
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
