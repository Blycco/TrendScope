<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { apiRequest, ApiRequestError, PlanGateRequestError, QuotaExceededRequestError } from '$lib/api';
	import ErrorModal from '$lib/ui/ErrorModal.svelte';
	import SuccessToast from '$lib/ui/SuccessToast.svelte';
	import PlanGate from '$lib/ui/PlanGate.svelte';
	import QuotaExceededModal from '$lib/ui/QuotaExceededModal.svelte';
	import PageStateWrapper from '$lib/ui/PageStateWrapper.svelte';
	import EmptyState from '$lib/ui/EmptyState.svelte';
	import { Shield, Trash2, Plus } from 'lucide-svelte';

	interface BrandItem {
		id: string;
		brand_name: string;
		keywords: string[];
		is_active: boolean;
		slack_webhook: string | null;
		last_alerted_at: string | null;
		created_at: string;
		updated_at: string;
	}

	interface BrandListResponse {
		brands: BrandItem[];
	}

	let brands = $state<BrandItem[]>([]);
	let isLoading = $state(true);
	let deletingName = $state<string | null>(null);

	let formOpen = $state(false);
	let formBrandName = $state('');
	let formKeywords = $state('');
	let formSlackWebhook = $state('');
	let isSubmitting = $state(false);

	let errorOpen = $state(false);
	let errorCode = $state('');
	let errorMessageKey = $state('');
	let successOpen = $state(false);
	let successMessageKey = $state('toast.success.default');
	let planGateOpen = $state(false);
	let planGateRequired = $state('business');
	let planGateUpgradeUrl = $state('/pricing');
	let quotaOpen = $state(false);
	let quotaFeature = $state('');
	let quotaLimit = $state(0);
	let quotaResetTime = $state('');

	function handleApiError(error: unknown): void {
		if (error instanceof PlanGateRequestError) {
			planGateRequired = error.requiredPlan;
			planGateUpgradeUrl = error.upgradeUrl ?? '/pricing';
			planGateOpen = true;
		} else if (error instanceof QuotaExceededRequestError) {
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

	async function loadBrands(): Promise<void> {
		isLoading = true;
		try {
			const data = await apiRequest<BrandListResponse>('/brand');
			brands = data.brands ?? [];
		} catch (error) {
			handleApiError(error);
			brands = [];
		} finally {
			isLoading = false;
		}
	}

	async function submitBrand(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		if (!formBrandName.trim() || isSubmitting) return;
		isSubmitting = true;
		const keywordList = formKeywords
			.split(',')
			.map((k) => k.trim())
			.filter((k) => k.length > 0);
		try {
			await apiRequest('/brand', {
				method: 'POST',
				body: JSON.stringify({
					brand_name: formBrandName.trim(),
					keywords: keywordList,
					slack_webhook: formSlackWebhook.trim() || null
				})
			});
			formBrandName = '';
			formKeywords = '';
			formSlackWebhook = '';
			formOpen = false;
			successMessageKey = 'toast.brand.added';
			successOpen = true;
			await loadBrands();
		} catch (error) {
			handleApiError(error);
		} finally {
			isSubmitting = false;
		}
	}

	async function removeBrand(name: string): Promise<void> {
		deletingName = name;
		try {
			await apiRequest(`/brand/${encodeURIComponent(name)}`, { method: 'DELETE' });
			brands = brands.filter((b) => b.brand_name !== name);
			successMessageKey = 'toast.brand.removed';
			successOpen = true;
		} catch (error) {
			handleApiError(error);
		} finally {
			deletingName = null;
		}
	}

	onMount(() => {
		loadBrands();
	});
</script>

<div class="space-y-6">
	<div class="flex items-start justify-between gap-3">
		<div>
			<div class="flex items-center gap-2">
				<Shield size={20} class="text-blue-600 dark:text-blue-400" />
				<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{$t('brand.title')}</h1>
				<span class="inline-flex items-center rounded-full bg-blue-100 dark:bg-blue-900/30 px-2 py-0.5 text-xs font-medium text-blue-700 dark:text-blue-400">
					Business
				</span>
			</div>
			<p class="mt-1 text-sm text-gray-500 dark:text-gray-400">{$t('brand.desc')}</p>
		</div>
		<button
			type="button"
			onclick={() => (formOpen = !formOpen)}
			class="inline-flex items-center gap-1 rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
		>
			<Plus size={16} />
			{$t('brand.action.add')}
		</button>
	</div>

	{#if formOpen}
		<form
			onsubmit={submitBrand}
			class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 space-y-3"
		>
			<div>
				<label for="brand-name" class="block text-sm font-medium text-gray-700 dark:text-gray-300">{$t('brand.form.name')}</label>
				<input
					id="brand-name"
					type="text"
					bind:value={formBrandName}
					required
					maxlength="100"
					class="mt-1 block w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-3 py-2 text-sm text-gray-900 dark:text-gray-100"
					placeholder={$t('brand.form.name_placeholder')}
				/>
			</div>
			<div>
				<label for="brand-keywords" class="block text-sm font-medium text-gray-700 dark:text-gray-300">{$t('brand.form.keywords')}</label>
				<input
					id="brand-keywords"
					type="text"
					bind:value={formKeywords}
					class="mt-1 block w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-3 py-2 text-sm text-gray-900 dark:text-gray-100"
					placeholder={$t('brand.form.keywords_placeholder')}
				/>
				<p class="mt-1 text-xs text-gray-500 dark:text-gray-400">{$t('brand.form.keywords_hint')}</p>
			</div>
			<div>
				<label for="brand-slack" class="block text-sm font-medium text-gray-700 dark:text-gray-300">{$t('brand.form.slack')}</label>
				<input
					id="brand-slack"
					type="url"
					bind:value={formSlackWebhook}
					class="mt-1 block w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-3 py-2 text-sm text-gray-900 dark:text-gray-100"
					placeholder="https://hooks.slack.com/..."
				/>
			</div>
			<div class="flex justify-end gap-2">
				<button
					type="button"
					onclick={() => (formOpen = false)}
					class="rounded-md border border-gray-200 dark:border-gray-700 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
				>
					{$t('action.cancel')}
				</button>
				<button
					type="submit"
					disabled={isSubmitting || !formBrandName.trim()}
					class="rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
				>
					{isSubmitting ? $t('status.loading') : $t('brand.form.submit')}
				</button>
			</div>
		</form>
	{/if}

	<PageStateWrapper {isLoading} isEmpty={!isLoading && brands.length === 0}>
		{#snippet empty()}
			<EmptyState titleKey="brand.empty.title" descriptionKey="brand.empty.desc" />
		{/snippet}
		{#snippet children()}
			<div class="space-y-3">
				{#each brands as brand (brand.id)}
					<div class="flex items-start justify-between gap-3 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4">
						<a href="/brand/{encodeURIComponent(brand.brand_name)}" class="flex-1 min-w-0 hover:underline">
							<h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100">{brand.brand_name}</h3>
							{#if brand.keywords.length > 0}
								<div class="mt-2 flex flex-wrap gap-1">
									{#each brand.keywords as kw}
										<span class="inline-flex items-center rounded-full bg-gray-100 dark:bg-gray-700 px-2 py-0.5 text-xs text-gray-600 dark:text-gray-300">
											#{kw}
										</span>
									{/each}
								</div>
							{/if}
							{#if brand.last_alerted_at}
								<p class="mt-2 text-xs text-amber-600 dark:text-amber-400">
									{$t('brand.last_alert')}: {new Date(brand.last_alerted_at).toLocaleString()}
								</p>
							{/if}
							<p class="mt-1 text-xs text-gray-400 dark:text-gray-500">
								{new Date(brand.created_at).toLocaleDateString()}
							</p>
						</a>
						<button
							type="button"
							onclick={() => removeBrand(brand.brand_name)}
							disabled={deletingName === brand.brand_name}
							aria-label={$t('brand.action.remove')}
							class="flex-shrink-0 text-gray-400 hover:text-red-500 transition-colors disabled:opacity-50"
						>
							<Trash2 size={16} />
						</button>
					</div>
				{/each}
			</div>
		{/snippet}
	</PageStateWrapper>
</div>

<ErrorModal open={errorOpen} errorCode={errorCode} messageKey={errorMessageKey} onClose={() => (errorOpen = false)} />
<SuccessToast open={successOpen} messageKey={successMessageKey} onClose={() => (successOpen = false)} />
<PlanGate open={planGateOpen} requiredPlan={planGateRequired} upgradeUrl={planGateUpgradeUrl} onClose={() => (planGateOpen = false)} />
<QuotaExceededModal open={quotaOpen} feature={quotaFeature} limit={quotaLimit} resetTime={quotaResetTime} onClose={() => (quotaOpen = false)} />
