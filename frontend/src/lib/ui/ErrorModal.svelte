<script lang="ts">
	import { t } from 'svelte-i18n';
	import { X } from 'lucide-svelte';

	interface Props {
		open: boolean;
		errorCode?: string;
		messageKey?: string;
		onClose: () => void;
		onRetry?: () => void;
	}

	let { open, errorCode = '', messageKey = 'modal.error.default_message', onClose, onRetry }: Props = $props();
</script>

{#if open}
	<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50" role="dialog" aria-modal="true">
		<div class="mx-4 w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
			<div class="flex items-start justify-between">
				<h2 class="text-lg font-semibold text-gray-900">{$t('modal.error.title')}</h2>
				<button onclick={onClose} class="text-gray-400 hover:text-gray-600" aria-label="close">
					<X size={20} />
				</button>
			</div>

			<p class="mt-3 text-sm text-gray-600">{$t(messageKey)}</p>

			{#if errorCode}
				<p class="mt-2 text-xs text-gray-400">Code: {errorCode}</p>
			{/if}

			<div class="mt-6 flex gap-3 justify-end">
				{#if onRetry}
					<button
						onclick={onRetry}
						class="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
					>
						{$t('modal.error.try_again')}
					</button>
				{/if}
				<button
					onclick={onClose}
					class="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
				>
					{$t('modal.error.close')}
				</button>
			</div>
		</div>
	</div>
{/if}
