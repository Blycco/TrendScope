<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount, onDestroy } from 'svelte';
	import { trackEvent, startAutoFlush, stopAutoFlush } from '$lib/tracker';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';
	import SuccessToast from '$lib/ui/SuccessToast.svelte';
	import QuotaExceededModal from '$lib/ui/QuotaExceededModal.svelte';
	import PlanGate from '$lib/ui/PlanGate.svelte';
	import PageStateWrapper from '$lib/ui/PageStateWrapper.svelte';
	import EmptyState from '$lib/ui/EmptyState.svelte';
	import { apiRequest, ApiRequestError, QuotaExceededRequestError } from '$lib/api';
	import type { TrendListResponse } from '$lib/api/types';
	import { authStore } from '$lib/stores/auth.svelte';
	import { Bell, BellOff, Trash2 } from 'lucide-svelte';

	interface KeywordItem {
		id: string;
		keyword: string;
		alertSurge: boolean;
		alertDaily: boolean;
	}

	interface KeywordResponse {
		id: string;
		user_id: string;
		keyword: string;
		alert_surge: boolean;
		alert_daily: boolean;
		created_at: string;
	}

	type TrendStatus = 'exploding' | 'rising' | 'stable' | 'declining' | null;

	let keywords = $state<KeywordItem[]>([]);
	let keywordStatuses = $state<Map<string, TrendStatus>>(new Map());
	let newKeyword = $state('');
	let isLoading = $state(true);
	let errorOpen = $state(false);
	let errorCode = $state('');
	let errorMessageKey = $state('');
	let successOpen = $state(false);
	let successMessageKey = $state('toast.success.default');

	let quotaOpen = $state(false);
	let quotaFeature = $state('');
	let quotaLimit = $state(0);
	let quotaResetTime = $state('');

	let planGateOpen = $state(false);
	let planGateRequired = $state('pro');
	const FREE_KEYWORD_LIMIT = 5;

	async function fetchKeywordStatus(keyword: string): Promise<void> {
		try {
			const data = await apiRequest<TrendListResponse>(
				`/trends?keyword=${encodeURIComponent(keyword)}&limit=1`
			);
			const status = (data.items?.[0]?.status ?? null) as TrendStatus;
			keywordStatuses = new Map(keywordStatuses).set(keyword, status);
		} catch {
			// silently hide badge on failure
			keywordStatuses = new Map(keywordStatuses).set(keyword, null);
		}
	}

	async function loadKeywords(): Promise<void> {
		try {
			const data = await apiRequest<{ keywords: KeywordResponse[] }>('/notifications/keywords');
			keywords = (data.keywords ?? []).map((kw) => ({
				id: kw.id,
				keyword: kw.keyword,
				alertSurge: kw.alert_surge,
				alertDaily: kw.alert_daily,
			}));
			// fetch statuses concurrently (best-effort)
			await Promise.allSettled(keywords.map((k) => fetchKeywordStatus(k.keyword)));
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

		// Free plan keyword limit gate
		if (keywords.length >= FREE_KEYWORD_LIMIT && authStore.user?.plan !== 'pro') {
			planGateRequired = 'pro';
			planGateOpen = true;
			return;
		}

		try {
			const created = await apiRequest<KeywordResponse>('/notifications/keywords', {
				method: 'POST',
				body: { keyword: trimmed },
			});
			keywords = [
				...keywords,
				{
					id: created.id,
					keyword: created.keyword,
					alertSurge: created.alert_surge,
					alertDaily: created.alert_daily,
				},
			];
			newKeyword = '';
			trackEvent('keyword_add', { keyword: trimmed });
			fetchKeywordStatus(trimmed);
			successMessageKey = 'toast.keyword.added';
			successOpen = true;
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

	async function removeKeyword(item: KeywordItem): Promise<void> {
		try {
			await apiRequest(`/notifications/keywords/${item.id}`, {
				method: 'DELETE',
			});
			keywords = keywords.filter((k) => k.id !== item.id);
			const next = new Map(keywordStatuses);
			next.delete(item.keyword);
			keywordStatuses = next;
			trackEvent('keyword_remove', { keyword: item.keyword });
			successMessageKey = 'toast.keyword.removed';
			successOpen = true;
		} catch (error) {
			if (error instanceof ApiRequestError) {
				errorCode = error.errorCode;
				errorMessageKey = 'error.server';
				errorOpen = true;
			}
		}
	}

	async function toggleAlert(item: KeywordItem, type: 'surge' | 'daily'): Promise<void> {
		const nextSurge = type === 'surge' ? !item.alertSurge : item.alertSurge;
		const nextDaily = type === 'daily' ? !item.alertDaily : item.alertDaily;
		try {
			const updated = await apiRequest<KeywordResponse>(
				`/notifications/keywords/${item.id}`,
				{
					method: 'PATCH',
					body: { alert_surge: nextSurge, alert_daily: nextDaily },
				}
			);
			keywords = keywords.map((k) =>
				k.id === item.id
					? {
							...k,
							alertSurge: updated.alert_surge,
							alertDaily: updated.alert_daily,
						}
					: k
			);
		} catch (error) {
			if (error instanceof ApiRequestError) {
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

	function getStatusBadge(status: TrendStatus): { icon: string; label: string; cls: string } | null {
		if (!status) return null;
		const map: Record<string, { icon: string; label: string; cls: string }> = {
			exploding: { icon: '🔥', label: 'tracker.status.exploding', cls: 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400' },
			rising:    { icon: '📈', label: 'tracker.status.rising',    cls: 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400' },
			stable:    { icon: '➡️', label: 'tracker.status.stable',    cls: 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400' },
			declining: { icon: '📉', label: 'tracker.status.declining', cls: 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400' },
		};
		return map[status] ?? null;
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
				<EmptyState variant="no_tracker" />
			{/snippet}
			{#snippet children()}
				<div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
					{#each keywords as item (item.keyword)}
						{@const status = keywordStatuses.get(item.keyword) ?? null}
						{@const badge = getStatusBadge(status)}
						<div class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4">
							<!-- Keyword header -->
							<div class="flex items-center justify-between mb-3">
								<div class="flex items-center gap-2 min-w-0">
									<span class="text-sm font-semibold text-gray-900 dark:text-gray-100 truncate">
										#{item.keyword}
									</span>
									{#if badge}
										<span class="flex-shrink-0 inline-flex items-center gap-0.5 rounded-full px-2 py-0.5 text-xs font-medium {badge.cls}">
											{badge.icon} {$t(badge.label)}
										</span>
									{:else if !keywordStatuses.has(item.keyword)}
										<!-- loading skeleton -->
										<span class="flex-shrink-0 h-5 w-14 rounded-full bg-gray-100 dark:bg-gray-700 animate-pulse"></span>
									{/if}
								</div>
								<button
									type="button"
									onclick={() => removeKeyword(item)}
									class="flex-shrink-0 text-gray-400 hover:text-red-500 transition-colors"
									aria-label="remove"
								>
									<Trash2 size={14} />
								</button>
							</div>

							<!-- Alert toggles -->
							<div class="space-y-2">
								<button
									type="button"
									onclick={() => toggleAlert(item, 'surge')}
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
									onclick={() => toggleAlert(item, 'daily')}
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
<SuccessToast open={successOpen} messageKey={successMessageKey} onClose={() => (successOpen = false)} />
<QuotaExceededModal open={quotaOpen} feature={quotaFeature} limit={quotaLimit} resetTime={quotaResetTime} onClose={() => (quotaOpen = false)} />
<PlanGate open={planGateOpen} requiredPlan={planGateRequired} onClose={() => (planGateOpen = false)} />
