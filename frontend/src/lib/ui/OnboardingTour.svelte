<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { X, ChevronLeft, ChevronRight } from 'lucide-svelte';

	interface TourStep {
		target: string;
		titleKey: string;
		descriptionKey: string;
		position: 'top' | 'bottom';
	}

	let { steps }: { steps: TourStep[] } = $props();

	const STORAGE_KEY = 'trendscope_tour_completed';
	const SPOTLIGHT_PAD = 8;

	let visible = $state(false);
	let currentStep = $state(0);
	let tooltipStyle = $state('');
	let spotlightStyle = $state('');
	let activeSteps = $state<TourStep[]>([]);
	let prevTargetEl: HTMLElement | null = null;

	const isLastStep = $derived(currentStep >= activeSteps.length - 1);

	function buildActiveSteps(): TourStep[] {
		const isMobile = window.innerWidth < 640;
		return steps.filter((s) => {
			if (isMobile && s.target === 'nav-links') return false;
			return document.querySelector(`[data-tour="${s.target}"]`) !== null;
		});
	}

	function updatePosition(): void {
		const step = activeSteps[currentStep];
		if (!step) return;

		const el = document.querySelector<HTMLElement>(`[data-tour="${step.target}"]`);
		if (!el) return;

		// Restore previous target
		if (prevTargetEl && prevTargetEl !== el) {
			prevTargetEl.style.removeProperty('position');
			prevTargetEl.style.removeProperty('z-index');
		}

		// Elevate target above overlay
		el.style.position = 'relative';
		el.style.zIndex = '51';
		prevTargetEl = el;

		const rect = el.getBoundingClientRect();

		// Spotlight cutout
		spotlightStyle = `top:${rect.top - SPOTLIGHT_PAD}px;left:${rect.left - SPOTLIGHT_PAD}px;width:${rect.width + SPOTLIGHT_PAD * 2}px;height:${rect.height + SPOTLIGHT_PAD * 2}px`;

		// Tooltip position
		const tooltipW = Math.min(360, window.innerWidth - 32);
		let left = rect.left + rect.width / 2 - tooltipW / 2;
		left = Math.max(16, Math.min(left, window.innerWidth - tooltipW - 16));

		if (step.position === 'bottom') {
			tooltipStyle = `top:${rect.bottom + 12}px;left:${left}px;width:${tooltipW}px`;
		} else {
			tooltipStyle = `bottom:${window.innerHeight - rect.top + 12}px;left:${left}px;width:${tooltipW}px`;
		}
	}

	function scrollAndPosition(): void {
		const step = activeSteps[currentStep];
		if (!step) return;
		const el = document.querySelector<HTMLElement>(`[data-tour="${step.target}"]`);
		if (!el) {
			next();
			return;
		}
		el.scrollIntoView({ behavior: 'smooth', block: 'center' });
		setTimeout(updatePosition, 400);
	}

	function next(): void {
		if (isLastStep) {
			complete();
		} else {
			currentStep++;
			scrollAndPosition();
		}
	}

	function prev(): void {
		if (currentStep > 0) {
			currentStep--;
			scrollAndPosition();
		}
	}

	function complete(): void {
		localStorage.setItem(STORAGE_KEY, 'true');
		cleanup();
		visible = false;
	}

	function cleanup(): void {
		if (prevTargetEl) {
			prevTargetEl.style.removeProperty('position');
			prevTargetEl.style.removeProperty('z-index');
			prevTargetEl = null;
		}
	}

	function handleKeydown(e: KeyboardEvent): void {
		if (!visible) return;
		if (e.key === 'Escape') complete();
		else if (e.key === 'ArrowRight') next();
		else if (e.key === 'ArrowLeft') prev();
	}

	onMount(() => {
		if (localStorage.getItem(STORAGE_KEY)) return;

		const timer = setTimeout(() => {
			activeSteps = buildActiveSteps();
			if (activeSteps.length === 0) return;
			visible = true;
			scrollAndPosition();
		}, 500);

		const onResize = (): void => {
			if (visible) updatePosition();
		};
		window.addEventListener('resize', onResize);

		return () => {
			clearTimeout(timer);
			window.removeEventListener('resize', onResize);
			cleanup();
		};
	});
</script>

<svelte:window onkeydown={handleKeydown} />

{#if visible && activeSteps.length > 0}
	<!-- Backdrop -->
	<div class="fixed inset-0 z-50 bg-black/50" onclick={complete} role="presentation"></div>

	<!-- Spotlight cutout -->
	<div
		class="fixed z-50 rounded-lg ring-4 ring-blue-400/60 pointer-events-none"
		style={spotlightStyle}
	></div>

	<!-- Tooltip -->
	<div class="fixed z-[52] rounded-lg bg-white dark:bg-gray-800 p-4 shadow-xl" style={tooltipStyle}>
		<button
			onclick={complete}
			class="absolute right-2 top-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
			aria-label={$t('tour.skip')}
		>
			<X size={16} />
		</button>

		<h3 class="pr-6 text-sm font-semibold text-gray-900 dark:text-gray-100">
			{$t(activeSteps[currentStep].titleKey)}
		</h3>
		<p class="mt-1 text-xs leading-relaxed text-gray-600 dark:text-gray-400">
			{$t(activeSteps[currentStep].descriptionKey)}
		</p>

		<div class="mt-3 flex items-center justify-between">
			<span class="text-xs text-gray-400">{currentStep + 1} / {activeSteps.length}</span>
			<div class="flex gap-2">
				{#if currentStep > 0}
					<button
						onclick={prev}
						class="flex items-center gap-1 rounded-md border border-gray-300 dark:border-gray-600 px-3 py-1.5 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
					>
						<ChevronLeft size={14} />
						{$t('tour.prev')}
					</button>
				{/if}
				<button
					onclick={next}
					class="flex items-center gap-1 rounded-md bg-blue-600 px-3 py-1.5 text-xs text-white hover:bg-blue-700"
				>
					{$t(isLastStep ? 'tour.finish' : 'tour.next')}
					{#if !isLastStep}<ChevronRight size={14} />{/if}
				</button>
			</div>
		</div>
	</div>
{/if}
