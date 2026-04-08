<script lang="ts">
	import { t } from 'svelte-i18n';

	interface Props {
		icon?: 'default' | 'search' | 'none';
		titleKey: string;
		descriptionKey?: string;
	}

	let { icon = 'default', titleKey, descriptionKey }: Props = $props();
</script>

<div class="flex flex-col items-center justify-center py-16 text-center">
	{#if icon !== 'none'}
		<div class="mb-4 text-gray-300 dark:text-gray-600">
			{#if icon === 'search'}
				<svg
					xmlns="http://www.w3.org/2000/svg"
					width="48"
					height="48"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="1.5"
					stroke-linecap="round"
					stroke-linejoin="round"
					aria-hidden="true"
				>
					<circle cx="11" cy="11" r="8" />
					<line x1="21" y1="21" x2="16.65" y2="16.65" />
				</svg>
			{:else}
				<svg
					xmlns="http://www.w3.org/2000/svg"
					width="48"
					height="48"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="1.5"
					stroke-linecap="round"
					stroke-linejoin="round"
					aria-hidden="true"
				>
					<rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
					<line x1="9" y1="9" x2="15" y2="9" />
					<line x1="9" y1="12" x2="12" y2="12" />
				</svg>
			{/if}
		</div>
	{/if}

	<p class="text-sm font-medium text-gray-500 dark:text-gray-400">{$t(titleKey)}</p>

	{#if descriptionKey}
		<p class="mt-1 text-xs text-gray-400">{$t(descriptionKey)}</p>
	{/if}
</div>
