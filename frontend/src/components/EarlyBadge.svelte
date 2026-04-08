<script lang="ts">
	import { t } from 'svelte-i18n';

	interface Props {
		score: number;
	}

	let { score }: Props = $props();

	const show = $derived(score >= 0.3);

	const label = $derived(
		score >= 0.8
			? 'status.hot'
			: score >= 0.5
				? 'status.emerging'
				: 'status.early'
	);

	const color = $derived(
		score >= 0.8
			? 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400'
			: score >= 0.5
				? 'bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-400'
				: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400'
	);
</script>

{#if show}
<span class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium {color}">
	{$t(label)}
</span>
{/if}
