<script lang="ts">
	interface Props {
		lines?: number;
	}

	let { lines = 3 }: Props = $props();
</script>

<div class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 animate-pulse">
	<div class="flex items-start justify-between">
		<div class="flex-1 space-y-2">
			<div class="h-4 w-3/4 rounded bg-gray-200 dark:bg-gray-700"></div>
			{#each Array(lines - 1) as _}
				<div class="h-3 w-1/2 rounded bg-gray-100 dark:bg-gray-600"></div>
			{/each}
		</div>
		<div class="ml-4 h-8 w-12 rounded bg-gray-200 dark:bg-gray-700"></div>
	</div>
	<div class="mt-3 flex gap-2">
		<div class="h-5 w-16 rounded-md bg-gray-100 dark:bg-gray-600"></div>
		<div class="h-5 w-16 rounded-md bg-gray-100 dark:bg-gray-600"></div>
		<div class="h-5 w-16 rounded-md bg-gray-100 dark:bg-gray-600"></div>
	</div>
</div>
