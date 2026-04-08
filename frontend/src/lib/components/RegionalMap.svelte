<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { apiRequest } from '$lib/api';
	import type { RegionalTrendResponse, RegionalTrendEntry } from '$lib/api';

	let data = $state<RegionalTrendResponse | null>(null);
	let hoveredLocale = $state<string | null>(null);
	let tooltipX = $state(0);
	let tooltipY = $state(0);
	let isLoading = $state(true);

	// SVG coordinate map (800x400 viewBox)
	const LOCALE_POS: Record<string, { x: number; y: number; label: string }> = {
		ko: { x: 660, y: 175, label: '한국' },
		en: { x: 180, y: 165, label: '영미권' },
		ja: { x: 700, y: 180, label: '일본' },
		zh: { x: 610, y: 185, label: '중국' },
		fr: { x: 395, y: 155, label: '프랑스' },
		de: { x: 415, y: 148, label: '독일' },
	};

	const MIN_R = 8;
	const MAX_R = 36;

	function getRadius(count: number, maxCount: number): number {
		if (maxCount === 0) return MIN_R;
		return MIN_R + (count / maxCount) * (MAX_R - MIN_R);
	}

	onMount(async () => {
		try {
			data = await apiRequest<RegionalTrendResponse>('/trends/regional');
		} catch {
			// silent fail
		} finally {
			isLoading = false;
		}
	});

	const maxCount = $derived(
		data ? Math.max(...data.entries.map((e) => e.count), 1) : 1
	);
</script>

{#if isLoading}
	<div class="flex h-48 items-center justify-center rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
		<p class="text-sm text-gray-500">{$t('status.loading')}</p>
	</div>
{:else if data && data.entries.length > 0}
	<div class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4">
		<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
			{$t('regional.widget.title')}
		</h3>
		<div class="overflow-x-auto">
			<svg
				viewBox="0 0 800 400"
				class="w-full"
				aria-label={$t('regional.map.aria')}
				role="img"
			>
				<!-- Continent placeholders -->
				<!-- Americas -->
				<rect x="80" y="110" width="140" height="160" rx="8" fill="#e5e7eb" class="dark:fill-gray-700" />
				<!-- Europe -->
				<rect x="370" y="120" width="70" height="70" rx="6" fill="#e5e7eb" class="dark:fill-gray-700" />
				<!-- Africa -->
				<rect x="380" y="200" width="80" height="100" rx="8" fill="#e5e7eb" class="dark:fill-gray-700" />
				<!-- Asia -->
				<rect x="560" y="110" width="160" height="120" rx="8" fill="#e5e7eb" class="dark:fill-gray-700" />
				<!-- Oceania -->
				<rect x="660" y="290" width="80" height="50" rx="6" fill="#e5e7eb" class="dark:fill-gray-700" />

				{#each data.entries as entry}
					{@const pos = LOCALE_POS[entry.locale]}
					{#if pos}
						{@const r = getRadius(entry.count, maxCount)}
						<circle
							cx={pos.x}
							cy={pos.y}
							r={r}
							fill="#3b82f6"
							fill-opacity="0.7"
							class="cursor-pointer transition-opacity hover:fill-opacity-90"
							onmouseenter={() => {
								hoveredLocale = entry.locale;
								tooltipX = pos.x + r + 4;
								tooltipY = pos.y;
							}}
							onmouseleave={() => (hoveredLocale = null)}
							role="img"
							aria-label="{pos.label}: {$t('regional.tooltip.trends', { values: { count: entry.count } })}"
						/>
						<text
							x={pos.x}
							y={pos.y + r + 14}
							text-anchor="middle"
							font-size="11"
							fill="#4b5563"
							class="dark:fill-gray-400 pointer-events-none select-none"
						>
							{pos.label}
						</text>
					{/if}
				{/each}

				<!-- Tooltip -->
				{#if hoveredLocale}
					{@const entry = data.entries.find((e) => e.locale === hoveredLocale)}
					{#if entry && LOCALE_POS[entry.locale]}
						{@const pos = LOCALE_POS[entry.locale]}
						{@const r = getRadius(entry.count, maxCount)}
						{@const tx = pos.x + r + 8}
						{@const ty = pos.y - 20}
						<rect
							x={tx}
							y={ty}
							width="148"
							height={16 + entry.top_trends.slice(0, 2).length * 14 + 8}
							rx="4"
							fill="white"
							stroke="#e5e7eb"
							class="dark:fill-gray-800 dark:stroke-gray-600"
						/>
						<text
							x={tx + 8}
							y={ty + 14}
							font-size="11"
							fill="#374151"
							class="dark:fill-gray-300 pointer-events-none select-none"
						>
							{pos.label}: {entry.count}{$t('regional.tooltip.trends', { values: { count: entry.count } }).replace(String(entry.count), '').trim() ? '' : '개'}
						</text>
						{#each entry.top_trends.slice(0, 2) as trend, i}
							<text
								x={tx + 8}
								y={ty + 28 + i * 14}
								font-size="10"
								fill="#6b7280"
								class="dark:fill-gray-400 pointer-events-none select-none"
							>
								· {trend.title.length > 18 ? trend.title.slice(0, 17) + '…' : trend.title}
							</text>
						{/each}
					{/if}
				{/if}
			</svg>
		</div>
	</div>
{:else}
	<div class="flex h-48 items-center justify-center rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
		<p class="text-sm text-gray-500">{$t('regional.no_data')}</p>
	</div>
{/if}
