<script lang="ts">
	interface Props {
		values: number[];
		width?: number;
		height?: number;
		color?: string;
		strokeWidth?: number;
	}

	let {
		values,
		width = 80,
		height = 24,
		color = '#3b82f6',
		strokeWidth = 1.5,
	}: Props = $props();

	let pathD = $derived.by(() => {
		if (values.length < 2) return '';
		const max = Math.max(...values);
		const min = Math.min(...values);
		const range = max - min || 1;
		const stepX = width / (values.length - 1);
		const padding = strokeWidth;
		const drawHeight = height - padding * 2;

		return values
			.map((v, i) => {
				const x = i * stepX;
				const y = padding + drawHeight - ((v - min) / range) * drawHeight;
				return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
			})
			.join(' ');
	});
</script>

{#if values.length >= 2}
	<svg
		viewBox="0 0 {width} {height}"
		class="inline-block"
		style="width: {width}px; height: {height}px;"
		role="img"
		aria-hidden="true"
	>
		<path d={pathD} fill="none" stroke={color} stroke-width={strokeWidth} stroke-linecap="round" stroke-linejoin="round" />
	</svg>
{/if}
