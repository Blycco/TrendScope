<script lang="ts">
	/**
	 * TrendMap — SVG-based force-directed trend relationship visualization.
	 * Uses Svelte-native SVG; no D3 dependency required.
	 */
	import { t } from 'svelte-i18n';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { apiRequest, ApiRequestError } from '$lib/api';

	interface TrendNode {
		id: string;
		title: string;
		score: number;
		x: number;
		y: number;
		vx: number;
		vy: number;
	}

	interface TrendEdge {
		source: string;
		target: string;
	}

	interface RelatedTrendsResponse {
		nodes: { id: string; title: string; score: number }[];
		edges: { source: string; target: string }[];
	}

	interface Props {
		trendId: string;
	}

	let { trendId }: Props = $props();

	const WIDTH = 600;
	const HEIGHT = 360;
	const NODE_RADIUS = 22;
	const CENTER_RADIUS = 32;

	let nodes = $state<TrendNode[]>([]);
	let edges = $state<TrendEdge[]>([]);
	let isLoading = $state(true);
	let hasError = $state(false);

	// Simple force-simulation tick
	let animFrame: number | null = null;

	function initPositions(raw: { id: string; title: string; score: number }[]): TrendNode[] {
		return raw.map((n, i) => {
			const angle = (2 * Math.PI * i) / Math.max(raw.length - 1, 1);
			const radius = i === 0 ? 0 : 120;
			return {
				...n,
				x: WIDTH / 2 + (i === 0 ? 0 : Math.cos(angle) * radius),
				y: HEIGHT / 2 + (i === 0 ? 0 : Math.sin(angle) * radius),
				vx: 0,
				vy: 0,
			};
		});
	}

	function tick(): void {
		const REPULSION = 3500;
		const ATTRACTION = 0.04;
		const DAMPING = 0.85;
		const CENTER_PULL = 0.005;

		// Build edge set for quick lookup
		const edgeSet = new Set(edges.map((e) => `${e.source}-${e.target}`));

		nodes = nodes.map((a, i) => {
			let fx = 0;
			let fy = 0;

			// Repulsion between all nodes
			for (let j = 0; j < nodes.length; j++) {
				if (i === j) continue;
				const b = nodes[j];
				const dx = a.x - b.x;
				const dy = a.y - b.y;
				const dist = Math.sqrt(dx * dx + dy * dy) || 1;
				fx += (dx / dist) * (REPULSION / (dist * dist));
				fy += (dy / dist) * (REPULSION / (dist * dist));
			}

			// Attraction along edges
			for (const b of nodes) {
				if (
					edgeSet.has(`${a.id}-${b.id}`) ||
					edgeSet.has(`${b.id}-${a.id}`)
				) {
					const dx = b.x - a.x;
					const dy = b.y - a.y;
					fx += dx * ATTRACTION;
					fy += dy * ATTRACTION;
				}
			}

			// Pull toward center (weak)
			fx += (WIDTH / 2 - a.x) * CENTER_PULL;
			fy += (HEIGHT / 2 - a.y) * CENTER_PULL;

			const vx = (a.vx + fx) * DAMPING;
			const vy = (a.vy + fy) * DAMPING;
			const x = Math.max(NODE_RADIUS, Math.min(WIDTH - NODE_RADIUS, a.x + vx));
			const y = Math.max(NODE_RADIUS, Math.min(HEIGHT - NODE_RADIUS, a.y + vy));
			return { ...a, x, y, vx, vy };
		});

		animFrame = requestAnimationFrame(tick);
	}

	onMount(() => {
		void (async () => {
			try {
				const data = await apiRequest<RelatedTrendsResponse>(
					`/trends/${trendId}/related`
				);
				nodes = initPositions(data.nodes);
				edges = data.edges;
				let frameCount = 0;
				const MAX_FRAMES = 120;
				function limitedTick(): void {
					frameCount++;
					tick();
					if (frameCount < MAX_FRAMES) {
						animFrame = requestAnimationFrame(limitedTick);
					}
				}
				animFrame = requestAnimationFrame(limitedTick);
			} catch (e) {
				if (!(e instanceof ApiRequestError)) {
					hasError = true;
				}
			} finally {
				isLoading = false;
			}
		})();

		return () => {
			if (animFrame !== null) cancelAnimationFrame(animFrame);
		};
	});

	function handleNodeClick(node: TrendNode): void {
		goto(`/trends/${node.id}`);
	}

	function truncate(text: string, max: number): string {
		return text.length > max ? text.slice(0, max - 1) + '...' : text;
	}

	function edgeCoords(edge: TrendEdge): { x1: number; y1: number; x2: number; y2: number } | null {
		const src = nodes.find((n) => n.id === edge.source);
		const tgt = nodes.find((n) => n.id === edge.target);
		if (!src || !tgt) return null;
		return { x1: src.x, y1: src.y, x2: tgt.x, y2: tgt.y };
	}
</script>

<div class="space-y-3">
	<h2 class="text-base font-semibold text-gray-900 dark:text-gray-100">{$t('trends.map.title')}</h2>

	{#if isLoading}
		<div class="flex h-48 items-center justify-center rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
			<p class="text-sm text-gray-500 dark:text-gray-400">{$t('status.loading')}</p>
		</div>
	{:else if nodes.length === 0}
		<div class="flex h-48 items-center justify-center rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
			<p class="text-sm text-gray-500 dark:text-gray-400">{$t('trends.map.empty')}</p>
		</div>
	{:else}
		<div class="overflow-hidden rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
			<svg
				viewBox="0 0 {WIDTH} {HEIGHT}"
				width="100%"
				height={HEIGHT}
				aria-label={$t('trends.map.title')}
			>
				<!-- Edges -->
				{#each edges as edge}
					{@const coords = edgeCoords(edge)}
					{#if coords}
						<line
							x1={coords.x1}
							y1={coords.y1}
							x2={coords.x2}
							y2={coords.y2}
							stroke="var(--chart-edge)"
							stroke-width="1.5"
						/>
					{/if}
				{/each}

				<!-- Nodes -->
				{#each nodes as node, i}
					{@const isCenter = i === 0}
					{@const r = isCenter ? CENTER_RADIUS : NODE_RADIUS}
					<g
						role="button"
						tabindex="0"
						onclick={() => handleNodeClick(node)}
						onkeydown={(e) => e.key === 'Enter' && handleNodeClick(node)}
						class="cursor-pointer"
					>
						<circle
							cx={node.x}
							cy={node.y}
							r={r}
							fill={isCenter ? 'var(--chart-node-center)' : 'var(--chart-node-fill)'}
							stroke={isCenter ? 'var(--chart-node-stroke)' : 'var(--chart-node-border)'}
							stroke-width="2"
						/>
						<text
							x={node.x}
							y={node.y}
							text-anchor="middle"
							dominant-baseline="middle"
							font-size={isCenter ? '11' : '10'}
							font-weight={isCenter ? '600' : '400'}
							fill={isCenter ? '#ffffff' : 'var(--chart-node-text)'}
						>
							{truncate(node.title, isCenter ? 12 : 10)}
						</text>
					</g>
				{/each}
			</svg>
		</div>
	{/if}
</div>
