<script lang="ts">
	import type { Component } from 'svelte';

	interface Props {
		icon: Component;
		iconColor?: string;
		label: string;
		value: string | number;
		subtext?: string;
	}

	let { icon: Icon, iconColor = 'text-gray-500', label, value, subtext }: Props = $props();
</script>

<div class="rounded-lg border border-gray-200 bg-white p-4">
	<div class="flex items-center gap-3">
		<div class="flex-shrink-0 rounded-lg bg-gray-50 p-2">
			<Icon size={20} class={iconColor} />
		</div>
		<div class="min-w-0">
			<p class="text-xs text-gray-500 truncate">{label}</p>
			<p class="text-lg font-bold text-gray-900">{value}</p>
			{#if subtext}
				<p class="text-xs text-gray-400">{subtext}</p>
			{/if}
		</div>
	</div>
</div>
