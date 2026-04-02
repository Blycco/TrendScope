<script lang="ts">
	import { t } from 'svelte-i18n';
	import type { TrendItem } from '$lib/api';
	import EarlyBadge from './EarlyBadge.svelte';
	import { formatDate } from '$lib/utils/locale';

	interface Props {
		trend: TrendItem;
	}

	let { trend }: Props = $props();

	const formattedDate = $derived(
		formatDate(trend.created_at, { year: 'numeric', month: 'short', day: 'numeric' })
	);
</script>

<div class="rounded-lg border border-gray-200 bg-white p-4 hover:shadow-md transition-shadow">
	<div class="flex items-start justify-between">
		<div class="flex-1">
			<div class="flex items-center gap-2">
				<a href="/trends/{trend.id}/insights" class="text-base font-semibold text-gray-900 hover:text-blue-600">
					{trend.title}
				</a>
				<EarlyBadge score={trend.early_trend_score} />
			</div>

			<div class="mt-2 flex flex-wrap gap-1.5">
				{#each trend.keywords as keyword}
					<span class="inline-flex rounded-md bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
						{keyword}
					</span>
				{/each}
			</div>
		</div>

		<div class="ml-4 text-right">
			<p class="text-sm font-medium text-gray-900">{trend.score.toFixed(1)}</p>
			<p class="text-xs text-gray-500">{$t('trend.score')}</p>
		</div>
	</div>

	<div class="mt-3 flex items-center gap-4 text-xs text-gray-500">
		<span>{$t('trend.category')}: {trend.category}</span>
		<span>{$t('trend.first_seen')}: {formattedDate}</span>
	</div>
</div>
