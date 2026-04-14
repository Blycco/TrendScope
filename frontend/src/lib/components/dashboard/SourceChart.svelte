<script lang="ts">
	import { t } from 'svelte-i18n';
	import { Globe } from 'lucide-svelte';

	interface Props {
		sourceCounts: Record<string, number>;
	}

	const SOURCE_COLORS: Record<string, string> = {
		rss: '#3b82f6',
		reddit: '#f97316',
		community: '#22c55e',
		twitter: '#06b6d4',
		google_trends: '#a855f7',
		burst_gnews: '#ef4444',
		burst_reddit: '#f59e0b',
	};

	let { sourceCounts }: Props = $props();

	let entries = $derived(
		Object.entries(sourceCounts).sort((a, b) => b[1] - a[1])
	);
	let total = $derived(entries.reduce((s, [, c]) => s + c, 0));
</script>

{#if entries.length > 0}
	<div class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 sm:p-5">
		<div class="flex items-center gap-2 mb-4">
			<Globe size={18} class="text-cyan-500" />
			<h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100">
				{$t('dashboard.source_distribution')}
			</h3>
		</div>
		<div class="space-y-3">
			<svg viewBox="0 0 300 24" class="w-full" aria-label={$t('dashboard.source_distribution')}>
				{#each entries as [src, cnt], i}
					{@const pct = cnt / total}
					{@const xOffset = entries.slice(0, i).reduce((s, [, c]) => s + (c / total) * 300, 0)}
					<rect
						x={xOffset}
						y="0"
						width={pct * 300}
						height="24"
						rx={i === 0 ? 4 : 0}
						fill={SOURCE_COLORS[src] ?? '#9ca3af'}
					/>
				{/each}
			</svg>
			<div class="flex flex-wrap gap-x-4 gap-y-1.5">
				{#each entries as [src, cnt]}
					{@const pct = Math.round((cnt / total) * 100)}
					<div class="flex items-center gap-1.5">
						<span
							class="w-2.5 h-2.5 rounded-full flex-shrink-0"
							style="background-color: {SOURCE_COLORS[src] ?? '#9ca3af'}"
						></span>
						<span class="text-xs text-gray-600 dark:text-gray-400">
							{src}
						</span>
						<span class="text-xs font-medium text-gray-700 dark:text-gray-300">{pct}%</span>
					</div>
				{/each}
			</div>
		</div>
	</div>
{/if}
