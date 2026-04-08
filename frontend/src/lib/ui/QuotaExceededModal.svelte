<script lang="ts">
	import { t } from 'svelte-i18n';
	import { X } from 'lucide-svelte';
	import { browser } from '$app/environment';

	interface Props {
		open: boolean;
		feature?: string;
		limit?: number;
		resetTime?: string;
		onClose: () => void;
	}

	let { open, feature = '', limit = 0, resetTime = '', onClose }: Props = $props();

	let dialogEl: HTMLDivElement | undefined = $state();

	function trapFocus(event: KeyboardEvent): void {
		if (!dialogEl) return;
		const focusableSelectors = 'a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex="-1"])';
		const focusable = Array.from(dialogEl.querySelectorAll<HTMLElement>(focusableSelectors));
		if (!focusable.length) return;
		const first = focusable[0];
		const last = focusable[focusable.length - 1];
		if (event.key === 'Tab') {
			if (event.shiftKey && document.activeElement === first) {
				event.preventDefault();
				last.focus();
			} else if (!event.shiftKey && document.activeElement === last) {
				event.preventDefault();
				first.focus();
			}
		}
		if (event.key === 'Escape') {
			onClose();
		}
	}

	$effect(() => {
		if (open && dialogEl && browser) {
			const firstFocusable = dialogEl.querySelector<HTMLElement>(
				'a[href], button:not([disabled])'
			);
			firstFocusable?.focus();
			document.addEventListener('keydown', trapFocus);
			return () => document.removeEventListener('keydown', trapFocus);
		}
	});
</script>

{#if open}
	<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50" role="dialog" aria-modal="true" aria-describedby="quota-dialog-desc" bind:this={dialogEl}>
		<div class="mx-4 w-full max-w-md rounded-lg bg-white dark:bg-gray-800 p-6 shadow-xl">
			<div class="flex items-start justify-between">
				<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">{$t('modal.quota_exceeded.title')}</h2>
				<button onclick={onClose} class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300" aria-label={$t('a11y.close_dialog')}>
					<X size={20} />
				</button>
			</div>

			<p id="quota-dialog-desc" class="mt-3 text-sm text-gray-600 dark:text-gray-400">
				{$t('modal.quota_exceeded.message', { values: { feature, limit: String(limit), resetTime } })}
			</p>

			<p class="mt-2 text-xs text-gray-400">Code: ERR_QUOTA_EXCEEDED</p>

			<div class="mt-6 flex gap-3 justify-end">
				<a
					href="/pricing"
					class="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
				>
					{$t('modal.quota_exceeded.upgrade')}
				</a>
				<button
					onclick={onClose}
					class="rounded-md border border-gray-300 dark:border-gray-600 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
				>
					{$t('modal.error.close')}
				</button>
			</div>
		</div>
	</div>
{/if}
