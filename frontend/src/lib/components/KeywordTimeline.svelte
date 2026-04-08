<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { apiRequest } from '$lib/api';
	import type { KeywordHistoryResponse } from '$lib/api';

	let { groupId }: { groupId: string } = $props();

	let data = $state<KeywordHistoryResponse | null>(null);
	let isLoading = $state(true);

	const SVG_WIDTH = 600;
	const SVG_HEIGHT = 200;
	const PAD_LEFT = 40;
	const PAD_RIGHT = 16;
	const PAD_TOP = 16;
	const PAD_BOTTOM = 32;
	const COLORS = ['#3b82f6', '#22c55e', '#a855f7', '#f97316', '#ef4444'];
	const MAX_KEYWORDS = 5;

	onMount(async () => {
		try {
			data = await apiRequest<KeywordHistoryResponse>(
				`/trends/${groupId}/keywords/history`
			);
		} catch {
			// silent fail
		} finally {
			isLoading = false;
		}
	});

	/**
	 * Pick the top MAX_KEYWORDS terms from the first snapshot by frequency.
	 */
	function getTopTerms(snapshots: KeywordHistoryResponse['snapshots']): string[] {
		if (snapshots.length === 0) return [];
		return [...snapshots[0].top_keywords]
			.sort((a, b) => b.frequency - a.frequency)
			.slice(0, MAX_KEYWORDS)
			.map((k) => k.term);
	}

	/**
	 * Build polyline points string for a single term across all snapshots.
	 */
	function buildPoints(
		snapshots: KeywordHistoryResponse['snapshots'],
		term: string,
		maxFreq: number
	): string {
		const chartW = SVG_WIDTH - PAD_LEFT - PAD_RIGHT;
		const chartH = SVG_HEIGHT - PAD_TOP - PAD_BOTTOM;
		const n = snapshots.length;

		return snapshots
			.map((snap, i) => {
				const freq = snap.top_keywords.find((k) => k.term === term)?.frequency ?? 0;
				const x = PAD_LEFT + (n === 1 ? chartW / 2 : (i / (n - 1)) * chartW);
				const y = PAD_TOP + chartH - (maxFreq > 0 ? (freq / maxFreq) * chartH : 0);
				return `${x.toFixed(1)},${y.toFixed(1)}`;
			})
			.join(' ');
	}

	function formatLabel(isoDate: string): string {
		try {
			const d = new Date(isoDate);
			return `${d.getMonth() + 1}/${d.getDate()}`;
		} catch {
			return isoDate.slice(5, 10);
		}
	}

	const derived = $derived(() => {
		if (!data || data.snapshots.length < 2) return null;
		const terms = getTopTerms(data.snapshots);
		const allFreqs = data.snapshots.flatMap((s) =>
			s.top_keywords.map((k) => k.frequency)
		);
		const maxFreq = Math.max(...allFreqs, 1);
		return { terms, maxFreq };
	});
</script>

{#if !isLoading && data && data.snapshots.length >= 2}
	{@const info = derived()}
	{#if info}
		<div class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4">
			<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
				{$t('keyword.history.title')}
			</h3>
			<div class="overflow-x-auto">
				<svg
					viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}"
					width="100%"
					aria-label={$t('keyword.history.title')}
				>
					<!-- Y-axis -->
					<line
						x1={PAD_LEFT}
						y1={PAD_TOP}
						x2={PAD_LEFT}
						y2={SVG_HEIGHT - PAD_BOTTOM}
						stroke="#e5e7eb"
						stroke-width="1"
					/>
					<!-- X-axis -->
					<line
						x1={PAD_LEFT}
						y1={SVG_HEIGHT - PAD_BOTTOM}
						x2={SVG_WIDTH - PAD_RIGHT}
						y2={SVG_HEIGHT - PAD_BOTTOM}
						stroke="#e5e7eb"
						stroke-width="1"
					/>

					<!-- X-axis labels -->
					{#each data.snapshots as snap, i}
						{@const n = data.snapshots.length}
						{@const chartW = SVG_WIDTH - PAD_LEFT - PAD_RIGHT}
						{@const x = PAD_LEFT + (n === 1 ? chartW / 2 : (i / (n - 1)) * chartW)}
						<text
							x={x}
							y={SVG_HEIGHT - PAD_BOTTOM + 14}
							text-anchor="middle"
							font-size="10"
							fill="#9ca3af"
						>
							{formatLabel(snap.snapshot_at)}
						</text>
					{/each}

					<!-- Lines per term -->
					{#each info.terms as term, ti}
						{@const pts = buildPoints(data.snapshots, term, info.maxFreq)}
						{@const color = COLORS[ti % COLORS.length]}
						<polyline
							points={pts}
							fill="none"
							stroke={color}
							stroke-width="2"
							stroke-linejoin="round"
							stroke-linecap="round"
						/>
					{/each}
				</svg>
			</div>

			<!-- Legend -->
			<div class="mt-2 flex flex-wrap gap-x-4 gap-y-1">
				{#each info.terms as term, ti}
					{@const color = COLORS[ti % COLORS.length]}
					<div class="flex items-center gap-1">
						<span
							class="inline-block w-3 h-0.5 rounded"
							style="background-color:{color}"
						></span>
						<span class="text-xs text-gray-500 dark:text-gray-400">{term}</span>
					</div>
				{/each}
			</div>
		</div>
	{/if}
{/if}
