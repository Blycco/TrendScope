<script lang="ts">
	import { t } from 'svelte-i18n';
	import { TrendingUp, Search, Tag, Lightbulb } from 'lucide-svelte';

	type Variant = 'no_trends' | 'no_results' | 'no_tracker' | 'no_insights';

	interface Props {
		icon?: 'default' | 'search' | 'none';
		titleKey?: string;
		descriptionKey?: string;
		variant?: Variant;
		onResetFilters?: () => void;
	}

	let { icon = 'default', titleKey, descriptionKey, variant, onResetFilters }: Props = $props();

	const variantConfig = $derived.by(() => {
		if (!variant) return null;
		const map = {
			no_trends:  { icon: TrendingUp, title: 'empty.no_trends',      desc: null,                  action: null,                actionHref: null },
			no_results: { icon: Search,     title: 'empty.no_results',     desc: null,                  action: 'empty.reset_filters', actionHref: null },
			no_tracker: { icon: Tag,        title: 'tracker.empty.title',  desc: 'tracker.empty.desc',  action: 'empty.add_keyword', actionHref: '/tracker' },
			no_insights:{ icon: Lightbulb,  title: 'empty.no_insights',    desc: null,                  action: null,                actionHref: null },
		} as const;
		return map[variant];
	});

	function handleAction(): void {
		if (variant === 'no_results' && onResetFilters) onResetFilters();
	}
</script>

<div class="flex flex-col items-center justify-center py-16 text-center">
	{#if variantConfig}
		<div class="mb-4 text-gray-300 dark:text-gray-600">
			<variantConfig.icon size={48} />
		</div>
		<p class="text-sm font-medium text-gray-500 dark:text-gray-400">{$t(variantConfig.title)}</p>
		{#if variantConfig.desc}
			<p class="mt-1 text-xs text-gray-400 dark:text-gray-500">{$t(variantConfig.desc)}</p>
		{/if}
		{#if variantConfig.action}
			{#if variantConfig.actionHref}
				<a
					href={variantConfig.actionHref}
					class="mt-4 inline-flex items-center rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
				>
					{$t(variantConfig.action)}
				</a>
			{:else}
				<button
					type="button"
					onclick={handleAction}
					class="mt-4 inline-flex items-center rounded-md border border-gray-300 dark:border-gray-600 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
				>
					{$t(variantConfig.action)}
				</button>
			{/if}
		{/if}
	{:else}
		<!-- Legacy mode: titleKey / descriptionKey -->
		{#if icon !== 'none'}
			<div class="mb-4 text-gray-300 dark:text-gray-600">
				{#if icon === 'search'}
					<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
						<circle cx="11" cy="11" r="8" />
						<line x1="21" y1="21" x2="16.65" y2="16.65" />
					</svg>
				{:else}
					<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
						<rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
						<line x1="9" y1="9" x2="15" y2="9" />
						<line x1="9" y1="12" x2="12" y2="12" />
					</svg>
				{/if}
			</div>
		{/if}
		{#if titleKey}
			<p class="text-sm font-medium text-gray-500 dark:text-gray-400">{$t(titleKey)}</p>
		{/if}
		{#if descriptionKey}
			<p class="mt-1 text-xs text-gray-400">{$t(descriptionKey)}</p>
		{/if}
	{/if}
</div>
