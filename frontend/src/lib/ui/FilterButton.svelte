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
		: 'border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700'}"
>
	{label}
</button>
