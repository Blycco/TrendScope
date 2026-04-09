<script lang="ts">
	import { t } from 'svelte-i18n';
	import { Hash } from 'lucide-svelte';

	interface Props {
		keywords: [string, number][];
		hotKeywords?: Set<string>;
		newKeywords?: Set<string>;
	}

	let { keywords, hotKeywords = new Set(), newKeywords = new Set() }: Props = $props();

	let maxCount = $derived(keywords.length > 0 ? keywords[0][1] : 1);
</script>

{#if keywords.length > 0}
	<div data-tour="top-keywords" class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 sm:p-5">
		<div class="flex items-center gap-2 mb-4">
			<Hash size={18} class="text-violet-500" />
			<h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100">
				{$t('dashboard.top_keywords')}
			</h3>
		</div>
		<div class="flex flex-wrap gap-2">
			{#each keywords as [kw, count]}
				{@const scale = 0.75 + (count / maxCount) * 0.5}
				{@const isHot = hotKeywords.has(kw)}
				{@const isNew = newKeywords.has(kw)}
				<a
					href="/trends?keyword={encodeURIComponent(kw)}"
					class="relative inline-flex items-center gap-1 rounded-full border px-3 py-1 hover:bg-violet-50 dark:hover:bg-violet-900/30 hover:border-violet-300 dark:hover:border-violet-600 transition-colors
						{isHot ? 'border-red-200 dark:border-red-700 bg-red-50 dark:bg-red-900/20' : 'border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700'}"
					style="font-size: {scale}rem"
				>
					{#if isHot}
						<span class="text-red-500" aria-label="급상승">🔥</span>
					{/if}
					<span class="text-gray-700 dark:text-gray-300">{kw}</span>
					<span class="text-gray-400 ml-0.5 text-xs">{count}</span>
					{#if isNew}
						<span class="absolute -top-1.5 -right-1 rounded-full bg-blue-500 px-1 py-0 text-white leading-tight" style="font-size: 0.55rem">NEW</span>
					{/if}
				</a>
			{/each}
		</div>
	</div>
{/if}
