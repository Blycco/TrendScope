<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount, onDestroy, untrack } from 'svelte';
	import { adminRequest } from '$lib/api/admin';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';

	// --- Types ---
	interface Source {
		id: string;
		source_name: string;
		quota_limit: number;
		quota_used: number;
		is_active: boolean | null;
		updated_at: string | null;
	}

	interface SourceListResponse {
		sources: Source[];
	}

	interface FeedSource {
		id: string;
		source_config_id: string | null;
		source_type: string;
		name: string;
		url: string;
		category: string;
		locale: string;
		is_active: boolean;
		priority: number;
		config: Record<string, unknown>;
		health_status: string;
		last_crawled_at: string | null;
		last_success_at: string | null;
		last_error: string | null;
		last_error_at: string | null;
		consecutive_failures: number;
		avg_latency_ms: number | null;
		total_crawl_count: number;
		total_error_count: number;
		created_at: string | null;
		updated_at: string | null;
	}

	interface FeedListResponse {
		feeds: FeedSource[];
		total: number;
		page: number;
		page_size: number;
	}

	interface HealthSummaryItem {
		source_type: string;
		total: number;
		healthy: number;
		degraded: number;
		error: number;
		unknown: number;
	}

	interface HealthDashboardResponse {
		summary: HealthSummaryItem[];
		last_updated: string;
	}

	// --- State ---
	let activeTab = $state<'groups' | 'feeds'>('feeds');

	// Source groups state
	let sources = $state<Source[]>([]);
	let sourcesLoading = $state(true);

	// Feed state
	let feeds = $state<FeedSource[]>([]);
	let feedsTotal = $state(0);
	let feedsLoading = $state(true);
	let feedsPage = $state(1);
	let feedsPageSize = $state(50);
	let healthSummary = $state<HealthSummaryItem[]>([]);

	// Filters
	let filterType = $state('');
	let filterHealth = $state('');
	let filterLocale = $state('');
	let filterSearch = $state('');

	// Selection
	let selectedIds = $state<Set<string>>(new Set());

	// Modal state
	let showModal = $state(false);
	let modalMode = $state<'create' | 'edit'>('create');
	let editFeed = $state<Partial<FeedSource>>({});
	let showDeleteConfirm = $state(false);
	let deleteFeedId = $state('');

	// Error
	let errorOpen = $state(false);
	let errorCode = $state('');
	let hasError = $state(false);

	// Polling
	let pollInterval: ReturnType<typeof setInterval> | null = null;

	const SOURCE_TYPES = ['rss', 'reddit', 'nitter', 'community', 'google_trends'];
	const CATEGORIES = ['general', 'politics', 'economy', 'it', 'entertainment', 'sports'];
	const LOCALES = ['ko', 'en', 'ja'];

	// --- Source Groups ---
	async function fetchSources(): Promise<void> {
		try {
			sourcesLoading = true;
			const data = await adminRequest<SourceListResponse>('/sources');
			sources = data.sources;
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		} finally {
			sourcesLoading = false;
		}
	}

	async function updateQuota(sourceId: string, quotaLimit: number): Promise<void> {
		try {
			await adminRequest(`/sources/${sourceId}`, {
				method: 'PATCH',
				body: { quota_limit: quotaLimit }
			});
			await fetchSources();
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		}
	}

	async function resetQuota(sourceId: string): Promise<void> {
		try {
			await adminRequest(`/sources/${sourceId}/reset`, { method: 'POST' });
			await fetchSources();
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		}
	}

	// --- Feed Sources ---
	async function fetchFeeds(): Promise<void> {
		try {
			feedsLoading = true;
			const params = new URLSearchParams();
			if (filterType) params.set('source_type', filterType);
			if (filterHealth) params.set('health_status', filterHealth);
			if (filterLocale) params.set('locale', filterLocale);
			if (filterSearch) params.set('search', filterSearch);
			params.set('page', String(feedsPage));
			params.set('page_size', String(feedsPageSize));

			const data = await adminRequest<FeedListResponse>(`/feed-sources?${params}`);
			feeds = data.feeds;
			feedsTotal = data.total;
			hasError = false;
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
			hasError = true;
		} finally {
			feedsLoading = false;
		}
	}

	async function fetchHealthSummary(): Promise<void> {
		try {
			const data = await adminRequest<HealthDashboardResponse>('/feed-sources/health/summary');
			healthSummary = data.summary;
		} catch {
			// silent
		}
	}

	async function refreshFeeds(): Promise<void> {
		await Promise.all([fetchFeeds(), fetchHealthSummary()]);
	}

	function openCreateModal(): void {
		modalMode = 'create';
		editFeed = { source_type: 'rss', category: 'general', locale: 'ko', is_active: true, priority: 0, config: {} };
		showModal = true;
	}

	function openEditModal(feed: FeedSource): void {
		modalMode = 'edit';
		editFeed = { ...feed };
		showModal = true;
	}

	async function saveFeed(): Promise<void> {
		try {
			if (modalMode === 'create') {
				await adminRequest('/feed-sources', {
					method: 'POST',
					body: {
						source_type: editFeed.source_type,
						name: editFeed.name,
						url: editFeed.url,
						category: editFeed.category,
						locale: editFeed.locale,
						is_active: editFeed.is_active,
						priority: editFeed.priority ?? 0,
						config: editFeed.config ?? {}
					}
				});
			} else {
				await adminRequest(`/feed-sources/${editFeed.id}`, {
					method: 'PATCH',
					body: {
						name: editFeed.name,
						url: editFeed.url,
						category: editFeed.category,
						locale: editFeed.locale,
						is_active: editFeed.is_active,
						priority: editFeed.priority
					}
				});
			}
			showModal = false;
			await refreshFeeds();
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		}
	}

	async function confirmDelete(): Promise<void> {
		try {
			await adminRequest(`/feed-sources/${deleteFeedId}`, { method: 'DELETE' });
			showDeleteConfirm = false;
			await refreshFeeds();
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		}
	}

	async function bulkToggle(isActive: boolean): Promise<void> {
		if (selectedIds.size === 0) return;
		try {
			await adminRequest('/feed-sources/bulk-toggle', {
				method: 'POST',
				body: { feed_ids: [...selectedIds], is_active: isActive }
			});
			selectedIds = new Set();
			await refreshFeeds();
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		}
	}

	function toggleSelect(id: string): void {
		const next = new Set(selectedIds);
		if (next.has(id)) next.delete(id);
		else next.add(id);
		selectedIds = next;
	}

	function toggleSelectAll(): void {
		if (selectedIds.size === feeds.length) {
			selectedIds = new Set();
		} else {
			selectedIds = new Set(feeds.map((f) => f.id));
		}
	}

	function healthDot(status: string): string {
		switch (status) {
			case 'healthy': return 'bg-green-500';
			case 'degraded': return 'bg-yellow-500';
			case 'error': return 'bg-red-500';
			default: return 'bg-gray-400';
		}
	}

	function healthBg(status: string): string {
		switch (status) {
			case 'healthy': return '';
			case 'degraded': return 'bg-yellow-50';
			case 'error': return 'bg-red-50';
			default: return '';
		}
	}

	function formatTime(iso: string | null): string {
		if (!iso) return '-';
		const d = new Date(iso);
		const diff = Date.now() - d.getTime();
		if (diff < 60000) return `${Math.floor(diff / 1000)}s ago`;
		if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
		if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
		return d.toLocaleDateString();
	}

	function typeLabel(t_fn: (key: string) => string, type: string): string {
		const map: Record<string, string> = {
			rss: t_fn('admin.feeds.type_rss'),
			reddit: t_fn('admin.feeds.type_reddit'),
			nitter: t_fn('admin.feeds.type_nitter'),
			community: t_fn('admin.feeds.type_community'),
			google_trends: t_fn('admin.feeds.type_google_trends')
		};
		return map[type] ?? type;
	}

	function startPolling(): void {
		pollInterval = setInterval(() => {
			if (document.visibilityState === 'visible' && activeTab === 'feeds' && !hasError) {
				refreshFeeds();
			}
		}, 10000);
	}

	onMount(() => {
		fetchSources();
		refreshFeeds();
		startPolling();
	});

	onDestroy(() => {
		if (pollInterval) clearInterval(pollInterval);
	});

	$effect(() => {
		// Track only filter/pagination dependencies — never loading state
		const _type = filterType;
		const _health = filterHealth;
		const _locale = filterLocale;
		const _search = filterSearch;
		const _page = feedsPage;
		// Use untrack so fetchFeeds() does not register reactive dependencies
		untrack(() => { fetchFeeds(); });
	});
</script>

<div>
	<h2 class="text-2xl font-bold text-gray-900 mb-4">{$t('admin.sources.title')}</h2>

	<!-- Tabs -->
	<div class="flex border-b border-gray-200 mb-6">
		<button
			class="px-4 py-2 text-sm font-medium {activeTab === 'groups' ? 'border-b-2 border-blue-600 text-blue-600' : 'text-gray-500 hover:text-gray-700'}"
			onclick={() => (activeTab = 'groups')}
		>
			{$t('admin.feeds.tab_groups')}
		</button>
		<button
			class="px-4 py-2 text-sm font-medium {activeTab === 'feeds' ? 'border-b-2 border-blue-600 text-blue-600' : 'text-gray-500 hover:text-gray-700'}"
			onclick={() => (activeTab = 'feeds')}
		>
			{$t('admin.feeds.tab_feeds')}
		</button>
	</div>

	{#if activeTab === 'groups'}
		<!-- Source Groups Tab (existing) -->
		{#if sourcesLoading}
			<p class="text-gray-500">{$t('status.loading')}</p>
		{:else}
			<div class="bg-white rounded-lg shadow overflow-x-auto">
				<table class="min-w-full divide-y divide-gray-200">
					<thead class="bg-gray-50">
						<tr>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.sources.col_name')}</th>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.sources.col_quota_limit')}</th>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.sources.col_quota_used')}</th>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.sources.col_status')}</th>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.users.col_actions')}</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-200">
						{#each sources as source}
							<tr>
								<td class="px-4 py-3 text-sm font-medium text-gray-900">{source.source_name}</td>
								<td class="px-4 py-3">
									<input
										type="number"
										value={source.quota_limit}
										class="w-24 text-sm border border-gray-300 rounded px-2 py-1"
										onchange={(e) => updateQuota(source.id, Number(e.currentTarget.value))}
									/>
								</td>
								<td class="px-4 py-3 text-sm text-gray-600">
									{source.quota_used}
									{#if source.quota_limit > 0}
										<span class="text-xs text-gray-400 ml-1">
											({Math.round((source.quota_used / source.quota_limit) * 100)}%)
										</span>
									{/if}
								</td>
								<td class="px-4 py-3">
									<span class="text-xs px-2 py-1 rounded {source.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">
										{source.is_active ? $t('admin.users.active') : $t('admin.users.suspended')}
									</span>
								</td>
								<td class="px-4 py-3">
									<button
										class="text-xs text-blue-600 hover:text-blue-800"
										onclick={() => resetQuota(source.id)}
									>
										{$t('admin.sources.reset_quota')}
									</button>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}

	{:else}
		<!-- Feed Management Tab -->

		<!-- Health Summary Cards -->
		{#if healthSummary.length > 0}
			<div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3 mb-6">
				{#each healthSummary as item}
					<div class="bg-white rounded-lg shadow p-4">
						<div class="text-sm font-medium text-gray-700 mb-2">{typeLabel($t, item.source_type)}</div>
						<div class="flex items-center gap-2 text-xs">
							<span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-green-500 inline-block"></span>{item.healthy}</span>
							<span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-yellow-500 inline-block"></span>{item.degraded}</span>
							<span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-red-500 inline-block"></span>{item.error}</span>
							<span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-gray-400 inline-block"></span>{item.unknown}</span>
						</div>
						<div class="text-xs text-gray-400 mt-1">{$t('admin.feeds.health_total', { values: { count: item.total } })}</div>
					</div>
				{/each}
			</div>
		{/if}

		<!-- Filters + Actions -->
		<div class="flex flex-wrap items-center gap-3 mb-4">
			<select class="text-sm border border-gray-300 rounded px-2 py-1" bind:value={filterType}>
				<option value="">{$t('admin.feeds.all_types')}</option>
				{#each SOURCE_TYPES as st}
					<option value={st}>{typeLabel($t, st)}</option>
				{/each}
			</select>
			<select class="text-sm border border-gray-300 rounded px-2 py-1" bind:value={filterHealth}>
				<option value="">{$t('admin.feeds.all_statuses')}</option>
				<option value="healthy">{$t('admin.feeds.health_healthy')}</option>
				<option value="degraded">{$t('admin.feeds.health_degraded')}</option>
				<option value="error">{$t('admin.feeds.health_error')}</option>
				<option value="unknown">{$t('admin.feeds.health_unknown')}</option>
			</select>
			<select class="text-sm border border-gray-300 rounded px-2 py-1" bind:value={filterLocale}>
				<option value="">{$t('admin.feeds.all_locales')}</option>
				{#each LOCALES as loc}
					<option value={loc}>{loc.toUpperCase()}</option>
				{/each}
			</select>
			<input
				type="text"
				class="text-sm border border-gray-300 rounded px-2 py-1 w-48"
				placeholder={$t('admin.feeds.filter_search')}
				bind:value={filterSearch}
			/>
			<div class="flex-1"></div>
			{#if selectedIds.size > 0}
				<button class="text-xs bg-green-600 text-white px-3 py-1 rounded hover:bg-green-700" onclick={() => bulkToggle(true)}>
					{$t('admin.feeds.bulk_enable')}
				</button>
				<button class="text-xs bg-red-600 text-white px-3 py-1 rounded hover:bg-red-700" onclick={() => bulkToggle(false)}>
					{$t('admin.feeds.bulk_disable')}
				</button>
			{/if}
			<button class="text-sm bg-blue-600 text-white px-4 py-1.5 rounded hover:bg-blue-700" onclick={openCreateModal}>
				{$t('admin.feeds.add_feed')}
			</button>
		</div>

		<!-- Feed Table -->
		{#if feedsLoading && feeds.length === 0}
			<p class="text-gray-500">{$t('status.loading')}</p>
		{:else if feeds.length === 0}
			<p class="text-gray-500">{$t('admin.feeds.no_feeds')}</p>
		{:else}
			<div class="bg-white rounded-lg shadow overflow-x-auto">
				<table class="min-w-full divide-y divide-gray-200">
					<thead class="bg-gray-50">
						<tr>
							<th class="px-3 py-3 w-8">
								<input type="checkbox" checked={selectedIds.size === feeds.length && feeds.length > 0} onchange={toggleSelectAll} />
							</th>
							<th class="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase w-8">{$t('admin.feeds.col_status')}</th>
							<th class="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.feeds.col_name')}</th>
							<th class="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.feeds.col_url')}</th>
							<th class="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.feeds.col_type')}</th>
							<th class="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.feeds.col_category')}</th>
							<th class="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.feeds.col_locale')}</th>
							<th class="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.feeds.col_last_crawled')}</th>
							<th class="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.feeds.col_latency')}</th>
							<th class="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$t('admin.feeds.col_actions')}</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-200">
						{#each feeds as feed}
							<tr class={healthBg(feed.health_status)}>
								<td class="px-3 py-2">
									<input type="checkbox" checked={selectedIds.has(feed.id)} onchange={() => toggleSelect(feed.id)} />
								</td>
								<td class="px-3 py-2">
									<span class="inline-block w-2.5 h-2.5 rounded-full {healthDot(feed.health_status)}" title={feed.health_status}></span>
								</td>
								<td class="px-3 py-2 text-sm font-medium text-gray-900">
									{feed.name}
									{#if !feed.is_active}
										<span class="ml-1 text-xs text-red-500">({$t('admin.feeds.feed_off')})</span>
									{/if}
								</td>
								<td class="px-3 py-2 text-xs text-gray-500 max-w-[200px] truncate" title={feed.url}>{feed.url}</td>
								<td class="px-3 py-2 text-xs text-gray-600">{typeLabel($t, feed.source_type)}</td>
								<td class="px-3 py-2 text-xs text-gray-600">{feed.category}</td>
								<td class="px-3 py-2 text-xs text-gray-600">{feed.locale.toUpperCase()}</td>
								<td class="px-3 py-2 text-xs text-gray-500" title={feed.last_error ?? ''}>{formatTime(feed.last_crawled_at)}</td>
								<td class="px-3 py-2 text-xs text-gray-500">
									{feed.avg_latency_ms != null ? `${Math.round(feed.avg_latency_ms)}ms` : '-'}
								</td>
								<td class="px-3 py-2 text-xs space-x-2">
									<button class="text-blue-600 hover:text-blue-800" onclick={() => openEditModal(feed)}>
										{$t('admin.feeds.edit_feed')}
									</button>
									<button class="text-red-600 hover:text-red-800" onclick={() => { deleteFeedId = feed.id; showDeleteConfirm = true; }}>
										{$t('admin.feeds.delete_feed')}
									</button>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>

			<!-- Pagination -->
			{#if feedsTotal > feedsPageSize}
				<div class="flex items-center justify-between mt-4">
					<span class="text-sm text-gray-600">{$t('admin.users.total')}: {feedsTotal}</span>
					<div class="flex gap-2">
						<button
							class="text-sm px-3 py-1 border rounded disabled:opacity-50"
							disabled={feedsPage <= 1}
							onclick={() => (feedsPage = feedsPage - 1)}
						>{$t('admin.users.prev')}</button>
						<span class="text-sm py-1">{feedsPage} / {Math.ceil(feedsTotal / feedsPageSize)}</span>
						<button
							class="text-sm px-3 py-1 border rounded disabled:opacity-50"
							disabled={feedsPage >= Math.ceil(feedsTotal / feedsPageSize)}
							onclick={() => (feedsPage = feedsPage + 1)}
						>{$t('admin.users.next')}</button>
					</div>
				</div>
			{/if}
		{/if}
	{/if}
</div>

<!-- Create/Edit Modal -->
{#if showModal}
	<div class="fixed inset-0 z-50 bg-black/40 flex items-center justify-center" onclick={(e) => { if (e.target === e.currentTarget) showModal = false; }}>
		<div class="bg-white rounded-lg shadow-xl p-6 w-full max-w-lg">
			<h3 class="text-lg font-bold mb-4">
				{modalMode === 'create' ? $t('admin.feeds.add_feed') : $t('admin.feeds.edit_feed')}
			</h3>
			<div class="space-y-3">
				<div>
					<label class="block text-sm font-medium text-gray-700 mb-1">{$t('admin.feeds.col_name')}</label>
					<input type="text" class="w-full text-sm border border-gray-300 rounded px-3 py-2" bind:value={editFeed.name} />
				</div>
				<div>
					<label class="block text-sm font-medium text-gray-700 mb-1">{$t('admin.feeds.col_url')}</label>
					<input type="text" class="w-full text-sm border border-gray-300 rounded px-3 py-2" bind:value={editFeed.url} />
				</div>
				<div class="grid grid-cols-3 gap-3">
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">{$t('admin.feeds.col_type')}</label>
						<select class="w-full text-sm border border-gray-300 rounded px-2 py-2" bind:value={editFeed.source_type} disabled={modalMode === 'edit'}>
							{#each SOURCE_TYPES as st}
								<option value={st}>{typeLabel($t, st)}</option>
							{/each}
						</select>
					</div>
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">{$t('admin.feeds.col_category')}</label>
						<select class="w-full text-sm border border-gray-300 rounded px-2 py-2" bind:value={editFeed.category}>
							{#each CATEGORIES as cat}
								<option value={cat}>{cat}</option>
							{/each}
						</select>
					</div>
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">{$t('admin.feeds.col_locale')}</label>
						<select class="w-full text-sm border border-gray-300 rounded px-2 py-2" bind:value={editFeed.locale}>
							{#each LOCALES as loc}
								<option value={loc}>{loc.toUpperCase()}</option>
							{/each}
						</select>
					</div>
				</div>
				<div class="flex items-center gap-4">
					<label class="flex items-center gap-2 text-sm">
						<input type="checkbox" bind:checked={editFeed.is_active} />
						{$t('admin.users.active')}
					</label>
					<label class="flex items-center gap-2 text-sm">
						{$t('admin.feeds.priority')}:
						<input type="number" class="w-16 text-sm border border-gray-300 rounded px-2 py-1" bind:value={editFeed.priority} />
					</label>
				</div>
			</div>
			<div class="flex justify-end gap-3 mt-6">
				<button class="text-sm px-4 py-2 border rounded text-gray-600 hover:bg-gray-50" onclick={() => (showModal = false)}>
					{$t('admin.feeds.cancel')}
				</button>
				<button class="text-sm px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700" onclick={saveFeed}>
					{$t('admin.feeds.save')}
				</button>
			</div>
		</div>
	</div>
{/if}

<!-- Delete Confirm Modal -->
{#if showDeleteConfirm}
	<div class="fixed inset-0 z-50 bg-black/40 flex items-center justify-center" onclick={(e) => { if (e.target === e.currentTarget) showDeleteConfirm = false; }}>
		<div class="bg-white rounded-lg shadow-xl p-6 w-full max-w-sm">
			<h3 class="text-lg font-bold mb-2">{$t('admin.feeds.delete_feed')}</h3>
			<p class="text-sm text-gray-600 mb-4">{$t('admin.feeds.delete_confirm')}</p>
			<div class="flex justify-end gap-3">
				<button class="text-sm px-4 py-2 border rounded text-gray-600 hover:bg-gray-50" onclick={() => (showDeleteConfirm = false)}>
					{$t('admin.feeds.cancel')}
				</button>
				<button class="text-sm px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700" onclick={confirmDelete}>
					{$t('admin.feeds.confirm_delete')}
				</button>
			</div>
		</div>
	</div>
{/if}

<ErrorModal open={errorOpen} errorCode={errorCode} messageKey="error.server" onClose={() => (errorOpen = false)} onRetry={() => { hasError = false; fetchFeeds(); }} />
