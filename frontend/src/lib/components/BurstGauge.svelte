<script lang="ts">
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';

	interface Props {
		score: number; // 0–1
		label?: string;
	}

	let { score, label }: Props = $props();

	let animated = $state(0);

	onMount(() => {
		// Ease-out from 0 to score
		const start = performance.now();
		const duration = 800;
		function step(ts: number) {
			const p = Math.min((ts - start) / duration, 1);
			const eased = 1 - Math.pow(1 - p, 3);
			animated = eased * score;
			if (p < 1) requestAnimationFrame(step);
		}
		requestAnimationFrame(step);
	});

	const stageLabel = $derived(
		animated > 0.8 ? $t('trend.burst.explosive') :
		animated > 0.6 ? $t('trend.burst.surge') :
		animated > 0.4 ? $t('trend.burst.growing') :
		animated > 0.2 ? $t('trend.burst.stable') :
		$t('trend.burst.declining')
	);

	const stageColor = $derived(
		animated > 0.8 ? '#ef4444' :
		animated > 0.6 ? '#f97316' :
		animated > 0.4 ? '#eab308' :
		animated > 0.2 ? '#22c55e' :
		'#9ca3af'
	);

	// SVG semicircle gauge
	const R = 60;
	const cx = 80;
	const cy = 80;
	const strokeW = 14;
	// Arc from -180° to 0° (left to right, upper half)
	const circumference = Math.PI * R;
	const dashOffset = $derived(circumference * (1 - animated));
</script>

<div class="flex flex-col items-center gap-2">
	<svg width="160" height="90" viewBox="0 0 160 90" aria-label={`Burst gauge: ${Math.round(score * 100)}%`}>
		<!-- Background arc -->
		<path
			d="M {cx - R} {cy} A {R} {R} 0 0 1 {cx + R} {cy}"
			fill="none"
			stroke="#e5e7eb"
			stroke-width={strokeW}
			stroke-linecap="round"
			class="dark:stroke-gray-700"
		/>
		<!-- Foreground arc (animated) -->
		<path
			d="M {cx - R} {cy} A {R} {R} 0 0 1 {cx + R} {cy}"
			fill="none"
			stroke={stageColor}
			stroke-width={strokeW}
			stroke-linecap="round"
			stroke-dasharray={circumference}
			stroke-dashoffset={dashOffset}
			style="transition: stroke-dashoffset 0.05s linear; transform-origin: {cx}px {cy}px;"
		/>
		<!-- Score label -->
		<text x={cx} y={cy - 8} text-anchor="middle" class="fill-gray-900 dark:fill-gray-100" font-size="22" font-weight="bold">
			{Math.round(animated * 100)}
		</text>
		<text x={cx} y={cy + 8} text-anchor="middle" class="fill-gray-500" font-size="11">
			{stageLabel}
		</text>
	</svg>

	{#if label}
		<p class="text-xs text-gray-500 dark:text-gray-400 text-center">{label}</p>
	{/if}
</div>
