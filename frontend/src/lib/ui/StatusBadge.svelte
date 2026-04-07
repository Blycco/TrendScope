<script lang="ts">
	import { t } from 'svelte-i18n';

	interface Props {
		status: string;
	}

	let { status }: Props = $props();

	const colorMap: Record<string, string> = {
		exploding: 'bg-red-100 text-red-700',
		rising: 'bg-green-100 text-green-700',
		stable: 'bg-blue-100 text-blue-700',
		declining: 'bg-orange-100 text-orange-700',
		peaked: 'bg-purple-100 text-purple-700',
	};

	const colorClass = $derived(colorMap[status] ?? 'bg-gray-100 text-gray-600');
</script>

<span class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium {colorClass}">
	{$t(`status.trend.${status}`)}
</span>
