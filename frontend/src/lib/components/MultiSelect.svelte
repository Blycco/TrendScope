<script lang="ts">
	import { t } from 'svelte-i18n';

	interface Option {
		value: string;
		label: string;
	}

	let {
		options,
		selected = $bindable<string[]>([]),
		placeholder = 'Select',
		multiple = true,
		label = ''
	}: {
		options: Option[];
		selected: string[];
		placeholder?: string;
		multiple?: boolean;
		label?: string;
	} = $props();

	let open = $state(false);
	let wrapperEl = $state<HTMLDivElement | null>(null);

	const displayLabel = $derived(
		selected.length === 0
			? placeholder
			: selected.length === 1
				? (options.find((o) => o.value === selected[0])?.label ?? selected[0])
				: `${label || placeholder} ${selected.length}`
	);

	const isActive = $derived(selected.length > 0);

	function toggle(value: string): void {
		if (multiple) {
			if (selected.includes(value)) {
				selected = selected.filter((v) => v !== value);
			} else {
				selected = [...selected, value];
			}
		} else {
			selected = selected[0] === value ? [] : [value];
			open = false;
		}
	}

	function selectAll(): void {
		selected = options.map((o) => o.value);
	}

	function clearAll(): void {
		selected = [];
	}

	function handleKeydown(e: KeyboardEvent): void {
		if (e.key === 'Escape') open = false;
	}

	$effect(() => {
		if (!open) return;
		function handleOutsideClick(e: MouseEvent): void {
			if (wrapperEl && !wrapperEl.contains(e.target as Node)) {
				open = false;
			}
		}
		document.addEventListener('mousedown', handleOutsideClick);
		return () => document.removeEventListener('mousedown', handleOutsideClick);
	});
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="relative inline-block multiselect-wrapper" bind:this={wrapperEl} onkeydown={handleKeydown}>
	<button
		type="button"
		class="flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1
			{isActive
				? 'border-blue-500 bg-blue-600 text-white'
				: 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700'}"
		onclick={() => (open = !open)}
		aria-haspopup="listbox"
		aria-expanded={open}
	>
		<span class="truncate max-w-32">{displayLabel}</span>
		<svg
			class="h-4 w-4 flex-shrink-0 transition-transform {open ? 'rotate-180' : ''}"
			fill="none"
			stroke="currentColor"
			viewBox="0 0 24 24"
			aria-hidden="true"
		>
			<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
		</svg>
	</button>

	{#if open}
		<div
			class="absolute left-0 top-full z-50 mt-1 min-w-40 rounded-lg border border-gray-200 bg-white py-1 shadow-lg dark:border-gray-700 dark:bg-gray-800"
			role="listbox"
			aria-multiselectable={multiple}
		>
			{#if multiple}
				<div class="flex gap-2 border-b border-gray-100 px-3 py-1.5 dark:border-gray-700">
					<button
						type="button"
						class="text-xs text-blue-600 hover:underline dark:text-blue-400"
						onclick={selectAll}
					>
						{$t('filter.select_all')}
					</button>
					<span class="text-gray-300 dark:text-gray-600">|</span>
					<button
						type="button"
						class="text-xs text-gray-500 hover:underline dark:text-gray-400"
						onclick={clearAll}
					>
						{$t('filter.clear_all')}
					</button>
				</div>
			{/if}

			{#each options as option}
				<button
					type="button"
					role="option"
					aria-selected={selected.includes(option.value)}
					class="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-gray-50 dark:hover:bg-gray-700
						{selected.includes(option.value)
							? 'text-blue-600 dark:text-blue-400'
							: 'text-gray-700 dark:text-gray-200'}"
					onclick={() => toggle(option.value)}
				>
					{#if multiple}
						<span
							class="flex h-4 w-4 flex-shrink-0 items-center justify-center rounded border
								{selected.includes(option.value)
									? 'border-blue-500 bg-blue-600'
									: 'border-gray-300 dark:border-gray-600'}"
						>
							{#if selected.includes(option.value)}
								<svg class="h-3 w-3 text-white" fill="currentColor" viewBox="0 0 12 12">
									<path d="M10 3L5 8.5 2 5.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
								</svg>
							{/if}
						</span>
					{:else}
						<span
							class="flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full border
								{selected.includes(option.value)
									? 'border-blue-500'
									: 'border-gray-300 dark:border-gray-600'}"
						>
							{#if selected.includes(option.value)}
								<span class="h-2 w-2 rounded-full bg-blue-600"></span>
							{/if}
						</span>
					{/if}
					<span>{option.label}</span>
				</button>
			{/each}
		</div>
	{/if}
</div>
