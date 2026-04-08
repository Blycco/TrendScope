<script lang="ts">
	import { t } from 'svelte-i18n';
	import { Hash } from 'lucide-svelte';

	interface Props {
		keywords: [string, number][];
	}

	let { keywords }: Props = $props();

	let maxCount = $derived(keywords.length > 0 ? keywords[0][1] : 1);
</script>

{#if keywords.length > 0}
	<div data-tour="top-keywords" class="rounded-lg border border-gray-200 bg-white p-4 sm:p-5">
		<div class="flex items-center gap-2 mb-4">
			<Hash size={18} class="text-violet-500" />
			<h3 class="text-sm font-semibold text-gray-900">
				{$t('dashboard.top_keywords')}
			</h3>
		</div>
		<div class="flex flex-wrap gap-2">
			{#each keywords as [kw, count]}
				{@const scale = 0.75 + (count / maxCount) * 0.5}
				<a
					href="/trends?keyword={encodeURIComponent(kw)}"
					class="inline-block rounded-full border border-gray-200 bg-gray-50 px-3 py-1 hover:bg-violet-50 hover:border-violet-300 transition-colors"
					style="font-size: {scale}rem"
				>
					<span class="text-gray-700">{kw}</span>
					<span class="text-gray-400 ml-1 text-xs">{count}</span>
				</a>
			{/each}
		</div>
	</div>
{/if}
