<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { apiRequest, PlanGateRequestError } from '$lib/api';
	import type {
		TrendListResponse,
		CompareTimelineResponse,
		CompareTimelineItem
	} from '$lib/api';
	import { compareStore } from '$lib/stores/compare.svelte';
	import ComparisonChart from '$lib/components/ComparisonChart.svelte';
	import PlanGate from '$lib/ui/PlanGate.svelte';
	import { X, Search } from 'lucide-svelte';

	const intervals = ['15m', '30m', '1h', '6h', '24h', '7d'] as const;
	type Interval = (typeof intervals)[number];

	const intervalLabelKey: Record<Interval, string> = {
		'15m': 'chart.timeline.interval.15m',
		'30m': 'chart.timeline.interval.30m',
		'1h': 'filter.time.1h',
		'6h': 'filter.time.6h',
		'24h': 'filter.time.24h',
		'7d': 'filter.time.7d'
	};

	let selectedInterval = $state<Interval>('1h');
	let searchQuery = $state('');
	let searchResults = $state<{ id: string; title: string }[]>([]);
	let isSearching = $state(false);
	let showDropdown = $state(false);

	let compareData = $state<CompareTimelineItem[]>([]);
	let isLoading = $state(false);
	let errorMessage = $state('');
	let showPlanGate = $state(false);

	// Titles for selected trends (fetched when loading from URL)
	let trendTitles = $state<Record<string, string>>({});

	let searchTimeout: ReturnType<typeof setTimeout> | undefined;

	function updateUrl(): void {
		const ids = compareStore.toUrlParam();
		const url = ids
			? `/compare?ids=${ids}&interval=${selectedInterval}`
			: `/compare?interval=${selectedInterval}`;
		goto(url, { replaceState: true, keepFocus: true });
	}

	async function searchTrends(query: string): Promise<void> {
		if (query.length < 1) {
			searchResults = [];
			showDropdown = false;
			return;
		}
		isSearching = true;
		try {
			const resp = await apiRequest<TrendListResponse>(`/trends?limit=10`, { auth: false });
			searchResults = resp.items
				.filter(
					(item) =>
						item.title.toLowerCase().includes(query.toLowerCase()) ||
						item.keywords.some((k) => k.toLowerCase().includes(query.toLowerCase()))
				)
				.filter((item) => !compareStore.selectedIds.includes(item.id))
				.map((item) => ({ id: item.id, title: item.title }));
			showDropdown = searchResults.length > 0;
		} catch {
			searchResults = [];
		} finally {
			isSearching = false;
		}
	}

	function handleSearchInput(): void {
		clearTimeout(searchTimeout);
		searchTimeout = setTimeout(() => searchTrends(searchQuery), 300);
	}

	function selectTrend(id: string, title: string): void {
		if (compareStore.selectedIds.length >= 5) return;
		compareStore.addTrend(id);
		trendTitles = { ...trendTitles, [id]: title };
		searchQuery = '';
		searchResults = [];
		showDropdown = false;
		updateUrl();
		if (compareStore.selectedIds.length >= 2) {
			loadComparison();
		}
	}

	function removeTrend(id: string): void {
		compareStore.removeTrend(id);
		updateUrl();
		if (compareStore.selectedIds.length >= 2) {
			loadComparison();
		} else {
			compareData = [];
		}
	}

	function selectInterval(iv: Interval): void {
		selectedInterval = iv;
		updateUrl();
		if (compareStore.selectedIds.length >= 2) {
			loadComparison();
		}
	}

	async function loadComparison(): Promise<void> {
		const ids = compareStore.toUrlParam();
		if (!ids) return;
		isLoading = true;
		errorMessage = '';
		try {
			const resp = await apiRequest<CompareTimelineResponse>(
				`/trends/compare?ids=${ids}&interval=${selectedInterval}`
			);
			compareData = resp.trends;
			// Update titles from response
			for (const trend of resp.trends) {
				trendTitles = { ...trendTitles, [trend.group_id]: trend.title };
			}
		} catch (err) {
			if (err instanceof PlanGateRequestError) {
				showPlanGate = true;
				compareData = [];
			} else {
				errorMessage = 'Failed to load comparison data';
				compareData = [];
			}
		} finally {
			isLoading = false;
		}
	}

	onMount(() => {
		const urlIds = $page.url.searchParams.get('ids');
		const urlInterval = $page.url.searchParams.get('interval');
		if (urlInterval && intervals.includes(urlInterval as Interval)) {
			selectedInterval = urlInterval as Interval;
		}
		if (urlIds) {
			compareStore.setFromUrl(urlIds);
			if (compareStore.selectedIds.length >= 2) {
				loadComparison();
			}
		}
	});
</script>

<svelte:head>
	<title>{$t('page.compare.title')} - TrendScope</title>
</svelte:head>

<div class="space-y-6">
	<h1 class="text-2xl font-bold text-gray-900">{$t('page.compare.title')}</h1>
	<p class="text-sm text-gray-500">{$t('compare.select_trends')}</p>

	<!-- Search -->
	<div class="relative max-w-md">
		<div class="relative">
			<Search size={16} class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
			<input
				type="text"
				bind:value={searchQuery}
				oninput={handleSearchInput}
				onfocus={() => {
					if (searchResults.length > 0) showDropdown = true;
				}}
				placeholder={$t('compare.search_placeholder')}
				class="w-full rounded-md border border-gray-300 py-2 pl-9 pr-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
				disabled={compareStore.selectedIds.length >= 5}
			/>
		</div>

		{#if showDropdown}
			<div
				class="absolute z-10 mt-1 w-full rounded-md border border-gray-200 bg-white shadow-lg"
			>
				{#each searchResults as result}
					<button
						type="button"
						class="block w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100"
						onclick={() => selectTrend(result.id, result.title)}
					>
						{result.title}
					</button>
				{/each}
			</div>
		{/if}

		{#if compareStore.selectedIds.length >= 5}
			<p class="mt-1 text-xs text-amber-600">{$t('compare.max_reached')}</p>
		{/if}
	</div>

	<!-- Selected chips -->
	{#if compareStore.selectedIds.length > 0}
		<div class="flex flex-wrap gap-2">
			{#each compareStore.selectedIds as id}
				<span
					class="inline-flex items-center gap-1 rounded-full bg-blue-50 px-3 py-1 text-sm text-blue-700"
				>
					{trendTitles[id] || id}
					<button
						type="button"
						class="ml-1 text-blue-500 hover:text-blue-700"
						onclick={() => removeTrend(id)}
						aria-label={$t('compare.remove')}
					>
						<X size={14} />
					</button>
				</span>
			{/each}
		</div>
	{/if}

	<!-- Interval toggle -->
	<div class="flex gap-1">
		{#each intervals as iv}
			<button
				type="button"
				class="rounded-md px-2 py-0.5 text-xs transition-colors {selectedInterval === iv
					? 'bg-blue-600 text-white'
					: 'bg-gray-100 text-gray-600 hover:bg-gray-200'}"
				onclick={() => selectInterval(iv)}
			>
				{$t(intervalLabelKey[iv])}
			</button>
		{/each}
	</div>

	<!-- Chart area -->
	{#if isLoading}
		<div class="flex h-60 items-center justify-center">
			<p class="text-sm text-gray-400">{$t('status.loading')}</p>
		</div>
	{:else if errorMessage}
		<div class="flex h-60 items-center justify-center">
			<p class="text-sm text-red-500">{errorMessage}</p>
		</div>
	{:else if compareStore.selectedIds.length < 2}
		<div class="flex h-60 items-center justify-center rounded-lg border border-dashed border-gray-300 bg-gray-50">
			<p class="text-sm text-gray-400">{$t('compare.empty')}</p>
		</div>
	{:else if compareData.length > 0}
		<ComparisonChart trends={compareData} interval={selectedInterval} />
	{/if}
</div>

<PlanGate open={showPlanGate} requiredPlan="pro" onClose={() => (showPlanGate = false)} />
