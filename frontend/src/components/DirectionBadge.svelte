<script lang="ts">
	import { t } from 'svelte-i18n';

	interface Props {
		direction: 'rising' | 'steady' | 'declining';
	}

	let { direction }: Props = $props();
</script>

{#if direction === 'rising'}
<span class="inline-flex items-center rounded-full bg-green-100 dark:bg-green-900/30 px-2.5 py-0.5 text-xs font-medium text-green-700 dark:text-green-400">
	{$t('status.rising')}
</span>
{:else if direction === 'declining'}
<span class="inline-flex items-center rounded-full bg-red-100 dark:bg-red-900/30 px-2.5 py-0.5 text-xs font-medium text-red-700 dark:text-red-400">
	{$t('status.declining')}
</span>
{/if}
