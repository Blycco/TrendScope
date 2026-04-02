<script lang="ts">
	import type { NewsItem } from '$lib/api';
	import { ExternalLink } from 'lucide-svelte';

	interface Props {
		news: NewsItem;
	}

	let { news }: Props = $props();

	const formattedDate = $derived(
		new Date(news.publish_time).toLocaleDateString(undefined, {
			year: 'numeric',
			month: 'short',
			day: 'numeric',
			hour: '2-digit',
			minute: '2-digit'
		})
	);
</script>

<article class="rounded-lg border border-gray-200 bg-white p-4 hover:shadow-md transition-shadow">
	<div class="flex items-start justify-between">
		<div class="flex-1">
			<a
				href={news.url}
				target="_blank"
				rel="noopener noreferrer"
				class="text-base font-semibold text-gray-900 hover:text-blue-600 inline-flex items-center gap-1"
			>
				{news.title}
				<ExternalLink size={14} class="text-gray-400" />
			</a>

			{#if news.summary}
				<p class="mt-1 text-sm text-gray-600 line-clamp-2">{news.summary}</p>
			{/if}
		</div>
	</div>

	<div class="mt-3 flex items-center gap-4 text-xs text-gray-500">
		{#if news.source}
			<span>{news.source}</span>
		{/if}
		<span>{formattedDate}</span>
		{#if news.article_count > 1}
			<span class="rounded-full bg-blue-50 px-2 py-0.5 text-blue-600 font-medium">+{news.article_count - 1}</span>
		{/if}
	</div>
</article>
