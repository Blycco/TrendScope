<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount, onDestroy } from 'svelte';
	import { trackEvent, startAutoFlush, stopAutoFlush } from '$lib/tracker';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';
	import QuotaExceededModal from '$lib/ui/QuotaExceededModal.svelte';
	import PageStateWrapper from '$lib/ui/PageStateWrapper.svelte';
	import { apiRequest, ApiRequestError, QuotaExceededRequestError } from '$lib/api';
	import { Bell, BellOff, Trash2, TrendingUp } from 'lucide-svelte';

	interface KeywordItem {
		keyword: string;
		alertSurge: boolean;
		alertDaily: boolean;
	}

	let keywords = $state<KeywordItem[]>([]);
	let newKeyword = $state('');
	let isLoading = $state(true);
	let errorOpen = $state(false);
	let errorCode = $state('');
	let errorMessageKey = $state('');

	let quotaOpen = $state(false);
	let quotaFeature = $state('');
	let quotaLimit = $state(0);
	let quotaResetTime = $state('');

	async function loadKeywords(): Promise<void> {
		try {
			const data = await apiRequest<{ keywords: string[] }>('/notifications/keywords');
			keywords = (data.keywords ?? []).map((kw) => ({ keyword: kw, alertSurge: true, alertDaily: false }));
		} catch {
			// start empty if API fails
			keywords = [];
		} finally {
			isLoading = false;
		}
	}

	async function addKeyword(): Promise<void> {
		const trimmed = newKeyword.trim();
		if (!trimmed) return;
		if (keywords.some((k) => k.keyword === trimmed)) return;

		try {
			await apiRequest('/notifications/keywords', {
				method: 'POST',
				body: { keyword: trimmed },
			});
			keywords = [...keywords, { keyword: trimmed, alertSurge: true, alertDaily: false }];
			newKeyword = '';
			trackEvent('keyword_add', { keyword: trimmed });
		} catch (error) {
			if (error instanceof QuotaExceededRequestError) {
				quotaFeature = error.quotaType;
				quotaLimit = error.limit;
				quotaResetTime = error.resetAt;
				quotaOpen = true;
			} else if (error instanceof ApiRequestError) {
				errorCode = error.errorCode;
				errorMessageKey = 'error.server';
				errorOpen = true;
			} else {
				errorCode = 'ERR_NETWORK';
				errorMessageKey = 'error.network';
				errorOpen = true;
			}
		}
	}

	async function removeKeyword(keyword: string): Promise<void> {
		try {
			await apiRequest(`/notifications/keywords/${encodeURIComponent(keyword)}`, {
				method: 'DELETE',
			});
			keywords = keywords.filter((k) => k.keyword !== keyword);
			trackEvent('keyword_remove', { keyword });
		} catch (error) {
			if (error instanceof ApiRequestError) {
				errorCode = error.errorCode;
				errorMessageKey = 'error.server';
				errorOpen = true;
			}
		}
	}

	function toggleAlert(keyword: string, type: 'surge' | 'daily'): void {
		keywords = keywords.map((k) => {
			if (k.keyword !== keyword) return k;
			return {
				...k,
				alertSurge: type === 'surge' ? !k.alertSurge : k.alertSurge,
				alertDaily: type === 'daily' ? !k.alertDaily : k.alertDaily,
			};
		});
	}

	async function handleSubmit(e: Event): Promise<void> {
		e.preventDefault();
		await addKeyword();
	}

	onMount(async () => {
		startAutoFlush();
		trackEvent('page_view', { page: 'tracker' });
		await loadKeywords();
	});

	onDestroy(() => {
		stopAutoFlush();
	});
</script>

<div class="space-y-6">
	<div>
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{$t('page.tracker.title')}</h1>
		<p class="mt-1 text-sm text-gray-500 dark:text-gray-400">{$t('tracker.empty.desc')}</p>
	</div>

	<form onsubmit={handleSubmit} class="flex gap-3">
		<input
			type="text"
			bind:value={newKeyword}
			placeholder={$t('label.keyword')}
			class="flex-1 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
		/>
		<button
			type="submit"
			class="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
		>
			{$t('tracker.add_keyword')}
		</button>
	</form>

	<div>
		<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">{$t('tracker.my_keywords')}</h2>
		<PageStateWrapper {isLoading} isEmpty={!isLoading && keywords.length === 0}>
			{#snippet empty()}
				<div class="rounded-lg border border-dashed border-gray-300 dark:border-gray-600 p-10 text-center">
					<TrendingUp size={32} class="text-gray-300 dark:text-gray-600 mx-auto mb-3" />
					<p class="text-sm font-medium text-gray-600 dark:text-gray-400">{$t('tracker.empty.title')}</p>
					<p class="text-xs text-gray-400 dark:text-gray-500 mt-1">{$t('tracker.empty.desc')}</p>
				</div>
			{/snippet}
			{#snippet children()}
				<div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
					{#each keywords as item (item.keyword)}
						<div class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4">
							<!-- Keyword header -->
							<div class="flex items-center justify-between mb-3">
								<span class="text-sm font-semibold text-gray-900 dark:text-gray-100">
									#{item.keyword}
								</span>
								<button
									type="button"
									onclick={() => removeKeyword(item.keyword)}
									class="text-gray-400 hover:text-red-500 transition-colors"
									aria-label="remove"
								>
									<Trash2 size={14} />
								</button>
							</div>

							<!-- Alert toggles -->
							<div class="space-y-2">
								<button
									type="button"
									onclick={() => toggleAlert(item.keyword, 'surge')}
									class="w-full flex items-center justify-between rounded-md px-3 py-2 text-xs transition-colors {item.alertSurge ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400' : 'bg-gray-50 dark:bg-gray-700 text-gray-500 dark:text-gray-400'}"
								>
									<span class="flex items-center gap-1.5">
										{#if item.alertSurge}
											<Bell size={12} />
										{:else}
											<BellOff size={12} />
										{/if}
										{$t('tracker.keyword_card.alert_surge')}
									</span>
									<span class="font-medium">{item.alertSurge ? 'ON' : 'OFF'}</span>
								</button>

								<button
									type="button"
									onclick={() => toggleAlert(item.keyword, 'daily')}
									class="w-full flex items-center justify-between rounded-md px-3 py-2 text-xs transition-colors {item.alertDaily ? 'bg-purple-50 dark:bg-purple-900/20 text-purple-700 dark:text-purple-400' : 'bg-gray-50 dark:bg-gray-700 text-gray-500 dark:text-gray-400'}"
								>
									<span class="flex items-center gap-1.5">
										{#if item.alertDaily}
											<Bell size={12} />
										{:else}
											<BellOff size={12} />
										{/if}
										{$t('tracker.keyword_card.alert_daily')}
									</span>
									<span class="font-medium">{item.alertDaily ? 'ON' : 'OFF'}</span>
								</button>
							</div>

							<!-- View link -->
							<a
								href="/trends?category={encodeURIComponent(item.keyword)}"
								class="mt-3 block text-xs text-blue-500 dark:text-blue-400 hover:underline"
							>
								{$t('tracker.keyword_card.view')}
							</a>
						</div>
					{/each}
				</div>
			{/snippet}
		</PageStateWrapper>
	</div>
</div>

<ErrorModal open={errorOpen} errorCode={errorCode} messageKey={errorMessageKey} onClose={() => (errorOpen = false)} />
<QuotaExceededModal open={quotaOpen} feature={quotaFeature} limit={quotaLimit} resetTime={quotaResetTime} onClose={() => (quotaOpen = false)} />
