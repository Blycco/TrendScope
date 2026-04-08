<script lang="ts">
	import { t } from 'svelte-i18n';

	interface Props {
		hasMore: boolean;
		isLoading: boolean;
		onclick: () => void;
	}

	let { hasMore, isLoading, onclick }: Props = $props();
</script>

{#if hasMore}
	<div class="flex justify-center pt-4">
		<button
			{onclick}
			disabled={isLoading}
			class="flex items-center gap-2 rounded-md border border-gray-300 dark:border-gray-600 px-6 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50"
		>
			{#if isLoading}
				<svg
					class="h-4 w-4 animate-spin text-gray-500"
					xmlns="http://www.w3.org/2000/svg"
					fill="none"
					viewBox="0 0 24 24"
					aria-hidden="true"
				>
					<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
					<path
						class="opacity-75"
						fill="currentColor"
						d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
					></path>
				</svg>
			{/if}
			{$t('common.load_more')}
		</button>
	</div>
{/if}
