<script lang="ts">
	interface Props {
		label: string;
		active: boolean;
		activeClass?: string;
		onclick: () => void;
	}

	let { label, active, activeClass = 'bg-indigo-600 text-white', onclick }: Props = $props();
</script>

<button
	{onclick}
	class="rounded-full px-2.5 py-1 sm:px-3 text-xs font-medium transition-colors {active
		? activeClass
		: 'border border-gray-200 bg-white text-gray-600 hover:bg-gray-50'}"
>
	{label}
</button>
