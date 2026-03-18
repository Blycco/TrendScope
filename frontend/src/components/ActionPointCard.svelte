<script lang="ts">
	import { t } from 'svelte-i18n';
	import type { InsightResponse } from '$lib/api';
	import { ExternalLink } from 'lucide-svelte';

	interface Props {
		insight: InsightResponse;
	}

	let { insight }: Props = $props();

	const roleLabel = $derived(
		insight.role === 'marketer'
			? 'role.marketer'
			: insight.role === 'creator'
				? 'role.creator'
				: insight.role === 'owner'
					? 'role.business_owner'
					: 'role.general'
	);

	const actionItems = $derived(getActionItems());

	function getActionItems(): { label: string; items: string[] }[] {
		const content = insight.content;
		if ('ad_opportunities' in content) {
			return [{ label: 'Ad Opportunities', items: content.ad_opportunities }];
		}
		if ('title_drafts' in content) {
			return [
				{ label: 'Title Drafts', items: content.title_drafts },
				{ label: 'SEO Keywords', items: content.seo_keywords }
			];
		}
		if ('consumer_reactions' in content) {
			return [
				{ label: 'Consumer Reactions', items: content.consumer_reactions },
				{ label: 'Product Hints', items: content.product_hints },
				{ label: 'Market Opportunities', items: content.market_ops }
			];
		}
		if ('sns_drafts' in content) {
			return [
				{ label: 'SNS Drafts', items: content.sns_drafts },
				{ label: 'Engagement Methods', items: content.engagement_methods }
			];
		}
		return [];
	}

	const sourceUrls = $derived(
		'source_urls' in insight.content ? (insight.content as { source_urls: string[] }).source_urls : []
	);
</script>

<div class="rounded-lg border border-gray-200 bg-white p-5">
	<div class="flex items-center justify-between mb-4">
		<h3 class="text-lg font-semibold text-gray-900">
			{$t('insight.for_role', { values: { role: $t(roleLabel) } })}
		</h3>
		{#if insight.degraded}
			<span class="text-xs text-amber-600 bg-amber-50 px-2 py-1 rounded">Fallback</span>
		{/if}
	</div>

	<div class="space-y-4">
		{#each actionItems as section}
			<div>
				<h4 class="text-sm font-medium text-gray-700 mb-2">{section.label}</h4>
				<ul class="space-y-1.5">
					{#each section.items as item}
						<li class="text-sm text-gray-600 pl-4 relative before:content-[''] before:absolute before:left-0 before:top-2 before:w-1.5 before:h-1.5 before:rounded-full before:bg-blue-400">
							{item}
						</li>
					{/each}
				</ul>
			</div>
		{/each}
	</div>

	{#if sourceUrls.length > 0}
		<div class="mt-4 pt-3 border-t border-gray-100">
			<h4 class="text-xs font-medium text-gray-500 mb-1.5">Sources</h4>
			<div class="flex flex-wrap gap-2">
				{#each sourceUrls as url, i}
					<a
						href={url}
						target="_blank"
						rel="noopener noreferrer"
						class="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline"
					>
						[{i + 1}] <ExternalLink size={10} />
					</a>
				{/each}
			</div>
		</div>
	{/if}
</div>
