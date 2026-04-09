<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { adminRequest } from '$lib/api/admin';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';
	import PageStateWrapper from '$lib/ui/PageStateWrapper.svelte';

	interface Stopword {
		id: string;
		word: string;
		locale: string;
		is_active: boolean;
		source: string;
		created_at: string;
	}

	interface ListResponse {
		items: Stopword[];
		total: number;
	}

	let activeLocale = $state<'ko' | 'en'>('ko');
	let items = $state<Stopword[]>([]);
	let loading = $state(true);
	let newWord = $state('');
	let errorOpen = $state(false);
	let errorCode = $state('');

	async function fetchItems(): Promise<void> {
		try {
			loading = true;
			const data = await adminRequest<ListResponse>(`/stopwords?locale=${activeLocale}`);
			items = data.items;
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		} finally {
			loading = false;
		}
	}

	async function addWord(): Promise<void> {
		if (!newWord.trim()) return;
		try {
			await adminRequest('/stopwords', {
				method: 'POST',
				body: { word: newWord.trim(), locale: activeLocale }
			});
			newWord = '';
			await fetchItems();
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		}
	}

	async function deleteWord(id: string): Promise<void> {
		try {
			await adminRequest(`/stopwords/${id}`, { method: 'DELETE' });
			await fetchItems();
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		}
	}

	async function reloadCache(): Promise<void> {
		try {
			await adminRequest('/stopwords/reload', { method: 'POST' });
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		}
	}

	$effect(() => {
		const _locale = activeLocale;
		fetchItems();
	});

	onMount(fetchItems);
</script>

<div>
	<div class="flex items-center justify-between mb-4">
		<h2 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{$t('admin.stopwords.title')}</h2>
		<button
			class="text-sm bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-200 px-3 py-1.5 rounded hover:bg-gray-300 dark:hover:bg-gray-600"
			onclick={reloadCache}
		>
			{$t('admin.stopwords.reload_cache')}
		</button>
	</div>

	<!-- Locale tabs -->
	<div class="flex border-b border-gray-200 dark:border-gray-700 mb-6">
		<button
			class="px-4 py-2 text-sm font-medium {activeLocale === 'ko' ? 'border-b-2 border-blue-600 text-blue-600' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'}"
			onclick={() => (activeLocale = 'ko')}
		>
			{$t('admin.stopwords.tab_ko')}
		</button>
		<button
			class="px-4 py-2 text-sm font-medium {activeLocale === 'en' ? 'border-b-2 border-blue-600 text-blue-600' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'}"
			onclick={() => (activeLocale = 'en')}
		>
			{$t('admin.stopwords.tab_en')}
		</button>
	</div>

	<!-- Add form -->
	<div class="flex items-center gap-2 mb-6">
		<input
			type="text"
			class="text-sm border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded px-3 py-1.5 w-48"
			placeholder={$t('admin.stopwords.word_placeholder')}
			bind:value={newWord}
			onkeydown={(e) => e.key === 'Enter' && addWord()}
		/>
		<button class="text-sm bg-blue-600 text-white px-4 py-1.5 rounded hover:bg-blue-700" onclick={addWord}>
			{$t('admin.stopwords.add_word')}
		</button>
	</div>

	<PageStateWrapper isLoading={loading} isEmpty={!loading && items.length === 0}>
		{#snippet empty()}
			<p class="text-gray-500">{$t('admin.stopwords.no_words')}</p>
		{/snippet}
		{#snippet children()}
			<div class="flex flex-wrap gap-2">
				{#each items as item}
					<span class="inline-flex items-center gap-1 bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200 text-sm px-3 py-1 rounded-full">
						{item.word}
						<button
							class="ml-1 text-gray-400 hover:text-red-500 transition-colors"
							onclick={() => deleteWord(item.id)}
							aria-label={$t('admin.stopwords.delete')}
						>
							×
						</button>
					</span>
				{/each}
			</div>
		{/snippet}
	</PageStateWrapper>
</div>

<ErrorModal open={errorOpen} errorCode={errorCode} messageKey="error.server" onClose={() => (errorOpen = false)} onRetry={fetchItems} />
