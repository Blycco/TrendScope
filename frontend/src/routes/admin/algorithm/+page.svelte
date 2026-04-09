<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { adminRequest } from '$lib/api/admin';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';

	interface SettingItem {
		key: string;
		value: number | string;
		default_value: number | string;
		updated_at: string;
	}

	interface SettingsResponse {
		settings: SettingItem[];
	}

	// Local state per section
	let allSettings = $state<Record<string, SettingItem>>({});
	let loading = $state(true);
	let saveSuccess = $state('');
	let errorOpen = $state(false);
	let errorCode = $state('');

	// Section drafts (key → value string for editing)
	let cluster = $state<Record<string, number>>({});
	let score = $state<Record<string, number>>({});
	let spam = $state<Record<string, number>>({});
	let decay = $state<Record<string, number>>({});
	let keyword = $state<Record<string, number>>({});

	const CLUSTER_KEYS = [
		'cluster.cosine_weight',
		'cluster.jaccard_weight',
		'cluster.temporal_weight',
		'cluster.source_weight',
		'cluster.jaccard_early_filter',
		'cluster.threshold',
		'cluster.outlier_sigma',
		'cluster.temporal_decay_hours',
		'cluster.louvain_threshold'
	];
	const SCORE_KEYS = [
		'score.weight_freshness',
		'score.weight_burst',
		'score.weight_article_count',
		'score.weight_source_diversity',
		'score.weight_social',
		'score.weight_keyword',
		'score.weight_velocity'
	];
	const SPAM_KEYS = [
		'spam.url_ratio_threshold',
		'spam.keyword_threshold',
		'spam.min_content_length',
		'spam.non_trend_min_hits'
	];
	const DECAY_KEYS = ['decay.breaking', 'decay.politics', 'decay.it', 'decay.default'];
	const KEYWORD_KEYS = ['keyword.title_boost', 'keyword.body_max_chars', 'keyword.top_k'];

	const WEIGHT_KEYS_4 = [
		'cluster.cosine_weight',
		'cluster.jaccard_weight',
		'cluster.temporal_weight',
		'cluster.source_weight'
	];

	function numVal(key: string, draft: Record<string, number>): number {
		return draft[key] ?? Number(allSettings[key]?.value ?? 0);
	}

	function clusterWeightSum(): number {
		return WEIGHT_KEYS_4.reduce((s, k) => s + numVal(k, cluster), 0);
	}

	function scoreWeightSum(): number {
		return SCORE_KEYS.reduce((s, k) => s + numVal(k, score), 0);
	}

	function shortKey(key: string): string {
		return key.split('.').slice(1).join('.');
	}

	async function fetchSettings(): Promise<void> {
		try {
			loading = true;
			const data = await adminRequest<SettingsResponse>('/settings');
			const map: Record<string, SettingItem> = {};
			for (const s of data.settings) map[s.key] = s;
			allSettings = map;
			// Init drafts
			for (const k of CLUSTER_KEYS) cluster[k] = Number(map[k]?.value ?? 0);
			for (const k of SCORE_KEYS) score[k] = Number(map[k]?.value ?? 0);
			for (const k of SPAM_KEYS) spam[k] = Number(map[k]?.value ?? 0);
			for (const k of DECAY_KEYS) decay[k] = Number(map[k]?.value ?? 0);
			for (const k of KEYWORD_KEYS) keyword[k] = Number(map[k]?.value ?? 0);
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		} finally {
			loading = false;
		}
	}

	async function saveSection(
		keys: string[],
		draft: Record<string, number>,
		validate?: () => boolean
	): Promise<void> {
		if (validate && !validate()) return;
		try {
			const settings: Record<string, string> = {};
			for (const k of keys) settings[k] = String(draft[k]);
			await adminRequest('/settings', { method: 'PATCH', body: { settings } });
			saveSuccess = $t('admin.algorithm.save_success');
			setTimeout(() => (saveSuccess = ''), 3000);
			await fetchSettings();
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		}
	}

	async function resetSection(keys: string[]): Promise<void> {
		try {
			const defaults: Record<string, string> = {};
			for (const k of keys) {
				const def = allSettings[k]?.default_value;
				if (def !== undefined) defaults[k] = String(def);
			}
			await adminRequest('/settings', { method: 'PATCH', body: { settings: defaults } });
			saveSuccess = $t('admin.algorithm.save_success');
			setTimeout(() => (saveSuccess = ''), 3000);
			await fetchSettings();
		} catch (err: unknown) {
			const e = err as { code?: string };
			errorCode = e?.code ?? '';
			errorOpen = true;
		}
	}

	function sectionUpdatedAt(keys: string[]): string {
		const timestamps = keys
			.map(k => allSettings[k]?.updated_at)
			.filter(Boolean)
			.map(s => new Date(s!).getTime());
		if (!timestamps.length) return '';
		return new Date(Math.max(...timestamps)).toLocaleString('ko-KR', {
			month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit'
		});
	}

	onMount(fetchSettings);
</script>

<div class="max-w-3xl">
	<div class="flex items-center justify-between mb-6">
		<h2 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{$t('admin.algorithm.title')}</h2>
		{#if saveSuccess}
			<span class="text-sm text-green-600 dark:text-green-400">{saveSuccess}</span>
		{/if}
	</div>

	{#if loading}
		<p class="text-gray-500 dark:text-gray-400">Loading...</p>
	{:else}
		<!-- Clustering Weights -->
		<section class="mb-8 bg-white dark:bg-gray-800 rounded-lg shadow p-5">
			<div class="flex items-center justify-between mb-4">
				<h3 class="text-lg font-semibold text-gray-800 dark:text-gray-200">{$t('admin.algorithm.section_cluster')}</h3>
				{#if sectionUpdatedAt(CLUSTER_KEYS)}
					<span class="text-xs text-gray-400 dark:text-gray-500">{$t('admin.algorithm.updated_at')} {sectionUpdatedAt(CLUSTER_KEYS)}</span>
				{/if}
			</div>

			<!-- 4-weight group with sum validator -->
			<div class="mb-4">
				{#each WEIGHT_KEYS_4 as key}
					<div class="flex items-center gap-3 mb-2">
						<span class="w-36 text-sm text-gray-600 dark:text-gray-400">{shortKey(key)}</span>
						<input type="range" min="0" max="1" step="0.05" class="flex-1"
							bind:value={cluster[key]} />
						<span class="w-10 text-sm text-right text-gray-700 dark:text-gray-300">{cluster[key]?.toFixed(2)}</span>
					</div>
				{/each}
				{#if Math.abs(clusterWeightSum() - 1.0) > 0.01}
					<p class="text-xs text-orange-500 mt-1">
						{$t('admin.algorithm.weight_sum_warning', { values: { expected: '1.0', actual: clusterWeightSum().toFixed(2) } })}
					</p>
				{/if}
			</div>

			<!-- Other cluster params -->
			{#each CLUSTER_KEYS.filter(k => !WEIGHT_KEYS_4.includes(k)) as key}
				<div class="flex items-center gap-3 mb-2">
					<span class="w-36 text-sm text-gray-600 dark:text-gray-400">{shortKey(key)}</span>
					<input type="number" step="0.01" class="w-24 text-sm border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded px-2 py-1"
						bind:value={cluster[key]} />
				</div>
			{/each}

			<div class="flex gap-2 mt-4">
				<button class="text-sm bg-blue-600 text-white px-4 py-1.5 rounded hover:bg-blue-700"
					onclick={() => saveSection(CLUSTER_KEYS, cluster)}>
					{$t('admin.algorithm.save')}
				</button>
				<button class="text-sm bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-200 px-3 py-1.5 rounded hover:bg-gray-300 dark:hover:bg-gray-600"
					onclick={() => resetSection(CLUSTER_KEYS)}>
					{$t('admin.algorithm.reset')}
				</button>
			</div>
		</section>

		<!-- Score Weights -->
		<section class="mb-8 bg-white dark:bg-gray-800 rounded-lg shadow p-5">
			<div class="flex items-center justify-between mb-4">
				<h3 class="text-lg font-semibold text-gray-800 dark:text-gray-200">{$t('admin.algorithm.section_score')}</h3>
				{#if sectionUpdatedAt(SCORE_KEYS)}
					<span class="text-xs text-gray-400 dark:text-gray-500">{$t('admin.algorithm.updated_at')} {sectionUpdatedAt(SCORE_KEYS)}</span>
				{/if}
			</div>

			{#each SCORE_KEYS as key}
				<div class="flex items-center gap-3 mb-2">
					<span class="w-36 text-sm text-gray-600 dark:text-gray-400">{shortKey(key)}</span>
					<input type="range" min="0" max="60" step="1" class="flex-1"
						bind:value={score[key]} />
					<span class="w-8 text-sm text-right text-gray-700 dark:text-gray-300">{score[key]}</span>
				</div>
			{/each}

			{#if Math.abs(scoreWeightSum() - 100) > 0.5}
				<p class="text-xs text-red-500 mt-1">
					{$t('admin.algorithm.weight_sum_warning', { values: { expected: '100', actual: String(scoreWeightSum()) } })}
				</p>
			{/if}

			<div class="flex gap-2 mt-4">
				<button
					class="text-sm bg-blue-600 text-white px-4 py-1.5 rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
					disabled={Math.abs(scoreWeightSum() - 100) > 0.5}
					onclick={() => saveSection(SCORE_KEYS, score, () => Math.abs(scoreWeightSum() - 100) <= 0.5)}>
					{$t('admin.algorithm.save')}
				</button>
				<button class="text-sm bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-200 px-3 py-1.5 rounded hover:bg-gray-300 dark:hover:bg-gray-600"
					onclick={() => resetSection(SCORE_KEYS)}>
					{$t('admin.algorithm.reset')}
				</button>
			</div>
		</section>

		<!-- Spam Filter -->
		<section class="mb-8 bg-white dark:bg-gray-800 rounded-lg shadow p-5">
			<div class="flex items-center justify-between mb-4">
				<h3 class="text-lg font-semibold text-gray-800 dark:text-gray-200">{$t('admin.algorithm.section_spam')}</h3>
				{#if sectionUpdatedAt(SPAM_KEYS)}
					<span class="text-xs text-gray-400 dark:text-gray-500">{$t('admin.algorithm.updated_at')} {sectionUpdatedAt(SPAM_KEYS)}</span>
				{/if}
			</div>
			{#each SPAM_KEYS as key}
				<div class="flex items-center gap-3 mb-2">
					<span class="w-44 text-sm text-gray-600 dark:text-gray-400">{shortKey(key)}</span>
					<input type="number" step="0.01" class="w-24 text-sm border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded px-2 py-1"
						bind:value={spam[key]} />
				</div>
			{/each}
			<div class="flex gap-2 mt-4">
				<button class="text-sm bg-blue-600 text-white px-4 py-1.5 rounded hover:bg-blue-700"
					onclick={() => saveSection(SPAM_KEYS, spam)}>
					{$t('admin.algorithm.save')}
				</button>
				<button class="text-sm bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-200 px-3 py-1.5 rounded hover:bg-gray-300 dark:hover:bg-gray-600"
					onclick={() => resetSection(SPAM_KEYS)}>
					{$t('admin.algorithm.reset')}
				</button>
			</div>
		</section>

		<!-- Decay Lambda -->
		<section class="mb-8 bg-white dark:bg-gray-800 rounded-lg shadow p-5">
			<div class="flex items-center justify-between mb-4">
				<h3 class="text-lg font-semibold text-gray-800 dark:text-gray-200">{$t('admin.algorithm.section_decay')}</h3>
				{#if sectionUpdatedAt(DECAY_KEYS)}
					<span class="text-xs text-gray-400 dark:text-gray-500">{$t('admin.algorithm.updated_at')} {sectionUpdatedAt(DECAY_KEYS)}</span>
				{/if}
			</div>
			{#each DECAY_KEYS as key}
				<div class="flex items-center gap-3 mb-2">
					<span class="w-36 text-sm text-gray-600 dark:text-gray-400">{shortKey(key)}</span>
					<input type="range" min="0.01" max="0.20" step="0.01" class="flex-1"
						bind:value={decay[key]} />
					<span class="w-10 text-sm text-right text-gray-700 dark:text-gray-300">{decay[key]?.toFixed(2)}</span>
				</div>
			{/each}
			<div class="flex gap-2 mt-4">
				<button class="text-sm bg-blue-600 text-white px-4 py-1.5 rounded hover:bg-blue-700"
					onclick={() => saveSection(DECAY_KEYS, decay)}>
					{$t('admin.algorithm.save')}
				</button>
				<button class="text-sm bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-200 px-3 py-1.5 rounded hover:bg-gray-300 dark:hover:bg-gray-600"
					onclick={() => resetSection(DECAY_KEYS)}>
					{$t('admin.algorithm.reset')}
				</button>
			</div>
		</section>

		<!-- Keyword Extraction -->
		<section class="mb-8 bg-white dark:bg-gray-800 rounded-lg shadow p-5">
			<div class="flex items-center justify-between mb-4">
				<h3 class="text-lg font-semibold text-gray-800 dark:text-gray-200">{$t('admin.algorithm.section_keyword')}</h3>
				{#if sectionUpdatedAt(KEYWORD_KEYS)}
					<span class="text-xs text-gray-400 dark:text-gray-500">{$t('admin.algorithm.updated_at')} {sectionUpdatedAt(KEYWORD_KEYS)}</span>
				{/if}
			</div>
			{#each KEYWORD_KEYS as key}
				<div class="flex items-center gap-3 mb-2">
					<span class="w-36 text-sm text-gray-600 dark:text-gray-400">{shortKey(key)}</span>
					{#if key === 'keyword.title_boost'}
						<input type="range" min="1.0" max="5.0" step="0.1" class="flex-1"
							bind:value={keyword[key]} />
						<span class="w-10 text-sm text-right text-gray-700 dark:text-gray-300">{keyword[key]?.toFixed(1)}</span>
					{:else}
						<input type="number" step="1" class="w-24 text-sm border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded px-2 py-1"
							bind:value={keyword[key]} />
					{/if}
				</div>
			{/each}
			<div class="flex gap-2 mt-4">
				<button class="text-sm bg-blue-600 text-white px-4 py-1.5 rounded hover:bg-blue-700"
					onclick={() => saveSection(KEYWORD_KEYS, keyword)}>
					{$t('admin.algorithm.save')}
				</button>
				<button class="text-sm bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-200 px-3 py-1.5 rounded hover:bg-gray-300 dark:hover:bg-gray-600"
					onclick={() => resetSection(KEYWORD_KEYS)}>
					{$t('admin.algorithm.reset')}
				</button>
			</div>
		</section>
	{/if}
</div>

<ErrorModal open={errorOpen} errorCode={errorCode} messageKey="error.server" onClose={() => (errorOpen = false)} onRetry={fetchSettings} />
