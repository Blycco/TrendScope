<script lang="ts">
	import { t } from 'svelte-i18n';

	interface Props {
		onSelect: (role: string) => void;
	}

	let { onSelect }: Props = $props();

	const roles = [
		{ key: 'marketer', labelKey: 'role.marketer' },
		{ key: 'creator', labelKey: 'role.creator' },
		{ key: 'business_owner', labelKey: 'role.business_owner' },
		{ key: 'general', labelKey: 'role.general' }
	];
</script>

<div class="space-y-4">
	<h2 class="text-lg font-semibold text-gray-900">{$t('label.role')}</h2>
	<div class="grid grid-cols-2 gap-3">
		{#each roles as role}
			<button
				onclick={() => onSelect(role.key)}
				class="rounded-lg border border-gray-200 bg-white p-4 text-center hover:border-blue-500 hover:shadow-md transition-all"
			>
				<span class="text-sm font-medium text-gray-900">{$t(role.labelKey)}</span>
			</button>
		{/each}
	</div>
</div>
