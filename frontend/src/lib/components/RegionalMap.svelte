<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { apiRequest } from '$lib/api';
	import type { RegionalTrendResponse } from '$lib/api';

	let data = $state<RegionalTrendResponse | null>(null);
	let hoveredLocale = $state<string | null>(null);
	let isLoading = $state(true);
	let loadError = $state(false);

	// Equirectangular projection onto a 800x400 viewBox:
	//   x = (lon + 180) * 800/360
	//   y = (85 - lat) * 400/140     (lat visible range ≈ 85..-55)
	function project(lat: number, lon: number): { x: number; y: number } {
		return { x: ((lon + 180) * 800) / 360, y: ((85 - lat) * 400) / 140 };
	}

	type LocaleMeta = { lat: number; lon: number; labelKey: string };

	const LOCALES: Record<string, LocaleMeta> = {
		ko: { lat: 37.5, lon: 127.0, labelKey: 'regional.locale.ko' },
		en: { lat: 39.0, lon: -98.0, labelKey: 'regional.locale.en' },
		ja: { lat: 36.0, lon: 139.7, labelKey: 'regional.locale.ja' },
		zh: { lat: 40.0, lon: 116.0, labelKey: 'regional.locale.zh' },
		fr: { lat: 48.8, lon: 2.3, labelKey: 'regional.locale.fr' },
		de: { lat: 52.5, lon: 13.4, labelKey: 'regional.locale.de' },
		es: { lat: 40.4, lon: -3.7, labelKey: 'regional.locale.es' },
		pt: { lat: 38.7, lon: -9.1, labelKey: 'regional.locale.pt' },
		ru: { lat: 55.8, lon: 37.6, labelKey: 'regional.locale.ru' },
		hi: { lat: 28.6, lon: 77.2, labelKey: 'regional.locale.hi' },
		ar: { lat: 24.7, lon: 46.7, labelKey: 'regional.locale.ar' },
		vi: { lat: 21.0, lon: 105.8, labelKey: 'regional.locale.vi' },
		id: { lat: -6.2, lon: 106.8, labelKey: 'regional.locale.id' },
		th: { lat: 13.8, lon: 100.5, labelKey: 'regional.locale.th' }
	};

	// Simplified continent polygons (lon,lat pairs → projected on render).
	// Outlines are approximate and optimized for legibility, not cartographic accuracy.
	const CONTINENTS: { name: string; points: [number, number][] }[] = [
		{
			name: 'north-america',
			points: [
				[-168, 66],
				[-140, 70],
				[-95, 72],
				[-65, 70],
				[-55, 52],
				[-60, 46],
				[-75, 35],
				[-82, 25],
				[-97, 25],
				[-108, 22],
				[-117, 32],
				[-125, 40],
				[-135, 55],
				[-165, 58]
			]
		},
		{
			name: 'south-america',
			points: [
				[-80, 10],
				[-60, 12],
				[-50, 0],
				[-35, -8],
				[-40, -25],
				[-58, -40],
				[-70, -52],
				[-75, -40],
				[-80, -20],
				[-78, -5]
			]
		},
		{
			name: 'europe',
			points: [
				[-10, 58],
				[5, 62],
				[25, 65],
				[40, 60],
				[40, 47],
				[30, 42],
				[15, 38],
				[-5, 38],
				[-10, 45]
			]
		},
		{
			name: 'africa',
			points: [
				[-15, 32],
				[10, 35],
				[30, 32],
				[42, 18],
				[48, 5],
				[40, -10],
				[35, -25],
				[20, -35],
				[12, -30],
				[10, -10],
				[0, 5],
				[-15, 15]
			]
		},
		{
			name: 'asia',
			points: [
				[30, 70],
				[60, 75],
				[110, 75],
				[145, 70],
				[150, 55],
				[140, 42],
				[130, 30],
				[110, 20],
				[100, 5],
				[90, 10],
				[78, 8],
				[70, 22],
				[55, 25],
				[45, 30],
				[40, 42],
				[30, 50]
			]
		},
		{
			name: 'oceania',
			points: [
				[115, -12],
				[135, -12],
				[150, -18],
				[152, -35],
				[140, -38],
				[118, -32]
			]
		}
	];

	function polygonToPath(points: [number, number][]): string {
		return (
			points
				.map(([lon, lat], i) => {
					const { x, y } = project(lat, lon);
					return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`;
				})
				.join(' ') + ' Z'
		);
	}

	const MIN_R = 8;
	const MAX_R = 32;

	function getRadius(count: number, maxCount: number): number {
		if (maxCount === 0) return MIN_R;
		return MIN_R + (count / maxCount) * (MAX_R - MIN_R);
	}

	onMount(async () => {
		try {
			data = await apiRequest<RegionalTrendResponse>('/trends/regional');
		} catch {
			loadError = true;
		} finally {
			isLoading = false;
		}
	});

	const maxCount = $derived(
		data && data.entries.length > 0 ? Math.max(...data.entries.map((e) => e.count), 1) : 1
	);

	const visibleEntries = $derived(
		data ? data.entries.filter((e) => LOCALES[e.locale] !== undefined) : []
	);

	function localeLabel(locale: string): string {
		const meta = LOCALES[locale];
		if (!meta) return locale;
		const translated = $t(meta.labelKey);
		return translated === meta.labelKey ? locale : translated;
	}

	function truncate(s: string, n: number): string {
		return s.length > n ? s.slice(0, n - 1) + '…' : s;
	}
</script>

{#if isLoading}
	<div class="flex h-48 items-center justify-center rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
		<p class="text-sm text-gray-500">{$t('status.loading')}</p>
	</div>
{:else if loadError}
	<div class="flex h-48 items-center justify-center rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
		<p class="text-sm text-gray-500">{$t('regional.load_error')}</p>
	</div>
{:else if data && visibleEntries.length > 0}
	<div class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4">
		<div class="flex items-center justify-between mb-3">
			<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300">
				{$t('regional.widget.title')}
			</h3>
			<span class="text-xs text-gray-500 dark:text-gray-400">
				{$t('regional.legend.range', { values: { min: 1, max: maxCount } })}
			</span>
		</div>
		<div class="overflow-x-auto">
			<svg
				viewBox="0 0 800 400"
				class="w-full h-auto"
				aria-label={$t('regional.map.aria')}
				role="img"
			>
				<rect x="0" y="0" width="800" height="400" fill="#f9fafb" class="dark:fill-gray-900" />

				{#each CONTINENTS as continent (continent.name)}
					<path
						d={polygonToPath(continent.points)}
						fill="#e5e7eb"
						stroke="#d1d5db"
						stroke-width="0.5"
						class="dark:fill-gray-700 dark:stroke-gray-600"
					/>
				{/each}

				{#each visibleEntries as entry (entry.locale)}
					{@const meta = LOCALES[entry.locale]}
					{@const pos = project(meta.lat, meta.lon)}
					{@const r = getRadius(entry.count, maxCount)}
					<circle
						cx={pos.x}
						cy={pos.y}
						r={r}
						fill="#3b82f6"
						fill-opacity="0.65"
						stroke="#1d4ed8"
						stroke-width="1"
						class="cursor-pointer transition-all hover:fill-opacity-90"
						onmouseenter={() => (hoveredLocale = entry.locale)}
						onmouseleave={() => (hoveredLocale = null)}
						onfocus={() => (hoveredLocale = entry.locale)}
						onblur={() => (hoveredLocale = null)}
						tabindex="0"
						role="img"
						aria-label="{localeLabel(entry.locale)}: {$t('regional.tooltip.trends', { values: { count: entry.count } })}"
					></circle>
					<text
						x={pos.x}
						y={pos.y + r + 12}
						text-anchor="middle"
						font-size="10"
						fill="#4b5563"
						class="dark:fill-gray-400 pointer-events-none select-none"
					>
						{localeLabel(entry.locale)}
					</text>
				{/each}

				{#if hoveredLocale}
					{@const entry = visibleEntries.find((e) => e.locale === hoveredLocale)}
					{#if entry}
						{@const meta = LOCALES[entry.locale]}
						{@const pos = project(meta.lat, meta.lon)}
						{@const r = getRadius(entry.count, maxCount)}
						{@const topCount = entry.top_trends.slice(0, 3).length}
						{@const boxW = 170}
						{@const boxH = 22 + topCount * 14 + 8}
						{@const tx = Math.min(pos.x + r + 8, 800 - boxW - 4)}
						{@const ty = Math.max(pos.y - 20, 4)}
						<rect
							x={tx}
							y={ty}
							width={boxW}
							height={boxH}
							rx="4"
							fill="white"
							stroke="#e5e7eb"
							class="dark:fill-gray-800 dark:stroke-gray-600"
						/>
						<text
							x={tx + 8}
							y={ty + 16}
							font-size="11"
							font-weight="600"
							fill="#111827"
							class="dark:fill-gray-100 pointer-events-none select-none"
						>
							{localeLabel(entry.locale)} · {$t('regional.tooltip.trends', { values: { count: entry.count } })}
						</text>
						{#each entry.top_trends.slice(0, 3) as trend, i}
							<text
								x={tx + 8}
								y={ty + 32 + i * 14}
								font-size="10"
								fill="#6b7280"
								class="dark:fill-gray-400 pointer-events-none select-none"
							>
								· {truncate(trend.title, 22)}
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
