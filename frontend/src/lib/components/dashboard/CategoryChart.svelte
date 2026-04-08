<script lang="ts">
	import { t } from 'svelte-i18n';
	import { BarChart3 } from 'lucide-svelte';

	interface Props {
		categoryCounts: Record<string, number>;
	}

	const CATEGORY_COLORS: Record<string, string> = {
		tech: '#3b82f6',
		economy: '#22c55e',
		entertainment: '#a855f7',
		lifestyle: '#ec4899',
		politics: '#ef4444',
		sports: '#f97316',
		society: '#14b8a6',
	};

	let { categoryCounts }: Props = $props();

	let entries = $derived(
		Object.entries(categoryCounts).sort((a, b) => b[1] - a[1])
	);
	let total = $derived(entries.reduce((s, [, c]) => s + c, 0));
</script>

{#if entries.length > 0}
	<div data-tour="category-chart" class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 sm:p-5">
		<div class="flex items-center gap-2 mb-4">
			<BarChart3 size={18} class="text-indigo-500" />
			<h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100">
				{$t('dashboard.category_distribution')}
			</h3>
		</div>
		<div class="flex items-center gap-6">
			<svg viewBox="0 0 120 120" class="w-28 h-28 flex-shrink-0">
				{#each entries as [cat, cnt], i}
					{@const pct = cnt / total}
					{@const offset = entries.slice(0, i).reduce((s, [, c]) => s + c / total, 0)}
					<circle
						cx="60" cy="60" r="45"
						fill="none"
						stroke={CATEGORY_COLORS[cat] ?? '#9ca3af'}
						stroke-width="16"
						stroke-dasharray="{pct * 283} {283 - pct * 283}"
						stroke-dashoffset="{-offset * 283}"
						transform="rotate(-90 60 60)"
					/>
				{/each}
				<text x="60" y="56" text-anchor="middle" class="text-lg font-bold fill-gray-900 dark:fill-gray-100" font-size="20">
					{total}
				</text>
				<text x="60" y="72" text-anchor="middle" class="fill-gray-400" font-size="10">
					{$t('dashboard.chart_total_label')}
				</text>
			</svg>
			<div class="flex-1 space-y-1.5">
				{#each entries as [cat, cnt]}
					{@const pct = Math.round((cnt / total) * 100)}
					<div class="flex items-center gap-2">
						<span
							class="w-2.5 h-2.5 rounded-full flex-shrink-0"
							style="background-color: {CATEGORY_COLORS[cat] ?? '#9ca3af'}"
						></span>
						<span class="text-xs text-gray-600 dark:text-gray-400 flex-1 truncate">
							{$t(`filter.category.${cat}`)}
						</span>
						<span class="text-xs font-medium text-gray-700 dark:text-gray-300">{pct}%</span>
					</div>
				{/each}
			</div>
		</div>
	</div>
{/if}
