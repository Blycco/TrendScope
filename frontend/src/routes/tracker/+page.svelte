<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount, onDestroy } from 'svelte';
	import { trackEvent, startAutoFlush, stopAutoFlush } from '$lib/tracker';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';

	let keywords = $state<string[]>([]);
	let newKeyword = $state('');
	let errorOpen = $state(false);
	let errorMessageKey = $state('');

	function addKeyword(): void {
		const trimmed = newKeyword.trim();
		if (!trimmed) return;
		if (keywords.includes(trimmed)) return;

		keywords = [...keywords, trimmed];
		newKeyword = '';
		trackEvent('keyword_add', { keyword: trimmed });
	}

	function removeKeyword(keyword: string): void {
		keywords = keywords.filter((k) => k !== keyword);
		trackEvent('keyword_remove', { keyword });
	}

	function handleSubmit(e: Event): void {
		e.preventDefault();
		addKeyword();
	}

	onMount(() => {
		startAutoFlush();
		trackEvent('page_view', { page: 'tracker' });
	});

	onDestroy(() => {
		stopAutoFlush();
	});
</script>

<div class="space-y-6">
	<h1 class="text-2xl font-bold text-gray-900">{$t('page.tracker.title')}</h1>

	<form onsubmit={handleSubmit} class="flex gap-3">
		<input
			type="text"
			bind:value={newKeyword}
			placeholder={$t('label.keyword')}
			class="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
		/>
		<button
			type="submit"
			class="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
		>
			{$t('tracker.add_keyword')}
		</button>
	</form>

	<div>
		<h2 class="text-lg font-semibold text-gray-900 mb-3">{$t('tracker.my_keywords')}</h2>
		{#if keywords.length === 0}
			<p class="text-gray-500">{$t('status.no_results')}</p>
		{:else}
			<div class="flex flex-wrap gap-2">
				{#each keywords as keyword}
					<span class="inline-flex items-center gap-1 rounded-full bg-blue-50 px-3 py-1.5 text-sm text-blue-700">
						{keyword}
						<button
							onclick={() => removeKeyword(keyword)}
							class="ml-1 text-blue-400 hover:text-blue-600"
							aria-label="remove"
						>
							x
						</button>
					</span>
				{/each}
			</div>
		{/if}
	</div>
</div>

<ErrorModal open={errorOpen} messageKey={errorMessageKey} onClose={() => (errorOpen = false)} />
