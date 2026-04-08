<script lang="ts">
	import { t } from 'svelte-i18n';

	interface Props {
		status: string;
	}

	let { status }: Props = $props();

	const colorMap: Record<string, string> = {
		exploding: 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400',
		rising: 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400',
		stable: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400',
		declining: 'bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-400',
		peaked: 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400',
	};

	const colorClass = $derived(colorMap[status] ?? 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400');
</script>

<span class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium {colorClass}">
	{$t(`status.trend.${status}`)}
</span>
