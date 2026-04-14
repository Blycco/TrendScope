<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { apiRequest, ApiRequestError } from '$lib/api';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';
	import SuccessToast from '$lib/ui/SuccessToast.svelte';
	import PageStateWrapper from '$lib/ui/PageStateWrapper.svelte';
	import EmptyState from '$lib/ui/EmptyState.svelte';
	import { Trash2, Bookmark } from 'lucide-svelte';

	interface ScrapItem {
		id: string;
		user_id: string;
		item_type: string;
		item_id: string;
		user_tags: string[];
		memo: string | null;
		created_at: string;
	}

	interface ScrapListResponse {
		items: ScrapItem[];
		total: number;
	}

	const PAGE_SIZE = 20;
	let items = $state<ScrapItem[]>([]);
	let total = $state(0);
	let offset = $state(0);
	let isLoading = $state(true);
	let deletingId = $state<string | null>(null);

	let errorOpen = $state(false);
	let errorCode = $state('');
	let errorMessageKey = $state('');
	let successOpen = $state(false);
	let successMessageKey = $state('toast.success.default');

	function showError(code: string, key: string): void {
		errorCode = code;
		errorMessageKey = key;
		errorOpen = true;
	}

	async function loadScraps(): Promise<void> {
		isLoading = true;
		try {
			const data = await apiRequest<ScrapListResponse>(
				`/scraps?limit=${PAGE_SIZE}&offset=${offset}`
			);
			items = data.items ?? [];
			total = data.total ?? 0;
		} catch (error) {
			if (error instanceof ApiRequestError) {
				showError(error.errorCode, 'error.server');
			} else {
				showError('ERR_NETWORK', 'error.network');
			}
			items = [];
		} finally {
			isLoading = false;
		}
	}

	async function removeScrap(id: string): Promise<void> {
		deletingId = id;
		try {
			await apiRequest(`/scraps/${id}`, { method: 'DELETE' });
			items = items.filter((s) => s.id !== id);
			total = Math.max(0, total - 1);
			successMessageKey = 'toast.scrap.removed';
			successOpen = true;
		} catch (error) {
			if (error instanceof ApiRequestError) {
				showError(error.errorCode, 'error.server');
			} else {
				showError('ERR_NETWORK', 'error.network');
			}
		} finally {
			deletingId = null;
		}
	}

	function targetHref(item: ScrapItem): string {
		if (item.item_type === 'trend') return `/trends/${item.item_id}`;
		return '#';
	}

	function nextPage(): void {
		if (offset + PAGE_SIZE < total) {
			offset += PAGE_SIZE;
			loadScraps();
		}
	}

	function prevPage(): void {
		if (offset > 0) {
			offset = Math.max(0, offset - PAGE_SIZE);
			loadScraps();
		}
	}

	onMount(() => {
		loadScraps();
	});
</script>

<div class="space-y-6">
	<div>
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{$t('page.scraps.title')}</h1>
		<p class="mt-1 text-sm text-gray-500 dark:text-gray-400">{$t('page.scraps.desc')}</p>
	</div>

	<PageStateWrapper {isLoading} isEmpty={!isLoading && items.length === 0}>
		{#snippet empty()}
			<EmptyState titleKey="scraps.empty.title" descriptionKey="scraps.empty.desc" />
		{/snippet}
		{#snippet children()}
			<div class="space-y-3">
				{#each items as item (item.id)}
					<div class="flex items-start justify-between gap-3 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4">
						<div class="flex-1 min-w-0">
							<div class="flex items-center gap-2">
								<Bookmark size={14} class="text-blue-600 dark:text-blue-400" />
								<a
									href={targetHref(item)}
									class="text-sm font-medium text-gray-900 dark:text-gray-100 hover:underline truncate"
								>
									{item.item_type} · {item.item_id}
								</a>
							</div>
							{#if item.memo}
								<p class="mt-1 text-xs text-gray-500 dark:text-gray-400">{item.memo}</p>
							{/if}
							{#if item.user_tags.length > 0}
								<div class="mt-2 flex flex-wrap gap-1">
									{#each item.user_tags as tag}
										<span class="inline-flex items-center rounded-full bg-gray-100 dark:bg-gray-700 px-2 py-0.5 text-xs text-gray-600 dark:text-gray-300">
											#{tag}
										</span>
									{/each}
								</div>
							{/if}
							<p class="mt-2 text-xs text-gray-400 dark:text-gray-500">
								{new Date(item.created_at).toLocaleDateString()}
							</p>
						</div>
						<button
							type="button"
							onclick={() => removeScrap(item.id)}
							disabled={deletingId === item.id}
							aria-label={$t('scraps.action.remove')}
							class="flex-shrink-0 text-gray-400 hover:text-red-500 transition-colors disabled:opacity-50"
						>
							<Trash2 size={14} />
						</button>
					</div>
				{/each}
			</div>

			{#if total > PAGE_SIZE}
				<div class="mt-4 flex items-center justify-between text-sm">
					<button
						type="button"
						onclick={prevPage}
						disabled={offset === 0}
						class="rounded-md border border-gray-200 dark:border-gray-700 px-3 py-1 text-gray-600 dark:text-gray-400 disabled:opacity-50"
					>
						{$t('pagination.prev')}
					</button>
					<span class="text-gray-500 dark:text-gray-400">
						{offset + 1}–{Math.min(offset + PAGE_SIZE, total)} / {total}
					</span>
					<button
						type="button"
						onclick={nextPage}
						disabled={offset + PAGE_SIZE >= total}
						class="rounded-md border border-gray-200 dark:border-gray-700 px-3 py-1 text-gray-600 dark:text-gray-400 disabled:opacity-50"
					>
						{$t('pagination.next')}
					</button>
				</div>
			{/if}
		{/snippet}
	</PageStateWrapper>
</div>

<ErrorModal open={errorOpen} errorCode={errorCode} messageKey={errorMessageKey} onClose={() => (errorOpen = false)} />
<SuccessToast open={successOpen} messageKey={successMessageKey} onClose={() => (successOpen = false)} />
