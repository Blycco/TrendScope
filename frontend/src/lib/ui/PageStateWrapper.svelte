<script lang="ts">
	import EmptyState from './EmptyState.svelte';
	import type { Snippet } from 'svelte';

	interface Props {
		isLoading: boolean;
		isEmpty: boolean;
		error?: string;
		loading?: Snippet;
		empty?: Snippet;
		children?: Snippet;
	}

	let { isLoading, isEmpty, error, loading, empty, children }: Props = $props();
</script>

{#if isLoading}
	{#if loading}
		{@render loading()}
	{:else}
		<div class="space-y-3">
			{#each Array(5) as _}
				<div class="h-24 animate-pulse rounded-lg bg-gray-100"></div>
			{/each}
		</div>
	{/if}
{:else if error}
	<div class="rounded-md border border-red-200 bg-red-50 px-4 py-3">
		<p class="text-sm text-red-700">{error}</p>
	</div>
{:else if isEmpty}
	{#if empty}
		{@render empty()}
	{:else}
		<EmptyState titleKey="common.no_results" descriptionKey="common.no_results_desc" />
	{/if}
{:else if children}
	{@render children()}
{/if}
