<script lang="ts">
	let { title, hook, platform, difficulty } = $props<{
		title: string;
		hook: string;
		platform: string;
		difficulty: string;
	}>();

	const platformColors: Record<string, string> = {
		youtube: 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-400',
		instagram: 'bg-pink-100 dark:bg-pink-900/30 text-pink-800 dark:text-pink-400',
		blog: 'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-400',
		newsletter: 'bg-purple-100 dark:bg-purple-900/30 text-purple-800 dark:text-purple-400',
	};

	const difficultyColors: Record<string, string> = {
		easy: 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-400',
		medium: 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-400',
		hard: 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-400',
	};
</script>

<div class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 space-y-2">
	<div class="flex items-center gap-2">
		<span class="rounded-full px-2 py-0.5 text-xs font-medium {platformColors[platform] ?? 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-400'}">{platform}</span>
		<span class="rounded-full px-2 py-0.5 text-xs font-medium {difficultyColors[difficulty] ?? 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-400'}">{difficulty}</span>
	</div>
	<h3 class="font-semibold text-gray-900 dark:text-gray-100">{title}</h3>
	<p class="text-sm text-gray-600 dark:text-gray-400">{hook}</p>
</div>
