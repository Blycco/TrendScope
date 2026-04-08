<script lang="ts">
	import { t } from 'svelte-i18n';
	import RegionalMap from '$lib/components/RegionalMap.svelte';
</script>

<svelte:head>
	<title>{$t('regional.page.title')} | TrendScope</title>
</svelte:head>

<div class="space-y-6">
	<div>
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">
			{$t('regional.page.title')}
		</h1>
	</div>
	<RegionalMap />
</div>
