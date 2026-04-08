<script lang="ts">
	import { t } from 'svelte-i18n';
	import { Sun, Moon, Monitor } from 'lucide-svelte';
	import { themeStore } from '$lib/stores/theme.svelte';
</script>

<button
	onclick={() => themeStore.toggleTheme()}
	class="p-1.5 text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100 transition-colors"
	aria-label={$t('theme.toggle')}
>
	{#if themeStore.theme === 'light'}
		<Sun size={18} />
	{:else if themeStore.theme === 'dark'}
		<Moon size={18} />
	{:else}
		<Monitor size={18} />
	{/if}
</button>
