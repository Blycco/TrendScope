<script lang="ts">
	import { t } from 'svelte-i18n';

	interface Props {
		score: number;
	}

	let { score }: Props = $props();

	const label = $derived(
		score >= 0.8
			? 'status.hot'
			: score >= 0.5
				? 'status.emerging'
				: score >= 0.3
					? 'status.early'
					: 'status.declining'
	);

	const color = $derived(
		score >= 0.8
			? 'bg-red-100 text-red-700'
			: score >= 0.5
				? 'bg-orange-100 text-orange-700'
				: score >= 0.3
					? 'bg-blue-100 text-blue-700'
					: 'bg-gray-100 text-gray-600'
	);
</script>

<span class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium {color}">
	{$t(label)}
</span>
