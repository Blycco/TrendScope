<script lang="ts">
	import { t } from 'svelte-i18n';
	import { CheckCircle2, X } from 'lucide-svelte';

	interface Props {
		open: boolean;
		messageKey?: string;
		durationMs?: number;
		onClose: () => void;
	}

	let { open, messageKey = 'toast.success.default', durationMs = 3000, onClose }: Props = $props();

	let timer: ReturnType<typeof setTimeout> | undefined;

	$effect(() => {
		if (open) {
			timer = setTimeout(onClose, durationMs);
			return () => {
				if (timer) clearTimeout(timer);
			};
		}
	});
</script>

{#if open}
	<div
		class="pointer-events-none fixed inset-x-0 bottom-6 z-50 flex justify-center"
		role="status"
		aria-live="polite"
	>
		<div
			class="pointer-events-auto flex items-center gap-3 rounded-lg bg-green-600 px-4 py-3 text-sm font-medium text-white shadow-lg"
		>
			<CheckCircle2 size={18} />
			<span>{$t(messageKey)}</span>
			<button
				onclick={onClose}
				class="ml-2 text-white/80 hover:text-white"
				aria-label={$t('a11y.close_dialog')}
			>
				<X size={16} />
			</button>
		</div>
	</div>
{/if}
