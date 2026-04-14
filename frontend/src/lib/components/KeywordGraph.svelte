<script lang="ts">
	/**
	 * KeywordGraph — SVG force-directed keyword co-occurrence graph.
	 * Physics engine adapted from TrendMap.svelte.
	 */
	import { t } from 'svelte-i18n';
	import { onMount } from 'svelte';
	import { apiRequest, ApiRequestError } from '$lib/api';
	import type { KeywordGraphResponse } from '$lib/api';

	interface GraphNode {
		term: string;
		score: number;
		frequency: number;
		x: number;
		y: number;
		vx: number;
		vy: number;
		radius: number;
	}

	interface GraphEdge {
		source: string;
		target: string;
		weight: number;
	}

	interface Props {
		groupId: string;
	}

	let { groupId }: Props = $props();

	const WIDTH = 600;
	const HEIGHT = 360;
	const MIN_RADIUS = 8;
	const MAX_RADIUS = 30;

	let nodes = $state<GraphNode[]>([]);
	let edges = $state<GraphEdge[]>([]);
	let isLoading = $state(true);
	let hasError = $state(false);
	let hoveredNode = $state<GraphNode | null>(null);
	let tooltipX = $state(0);
	let tooltipY = $state(0);

	let animFrame: number | null = null;

	function computeRadius(frequency: number, maxFreq: number): number {
		if (maxFreq <= 0) return MIN_RADIUS;
		const ratio = frequency / maxFreq;
		return MIN_RADIUS + ratio * (MAX_RADIUS - MIN_RADIUS);
	}

	function initPositions(raw: { term: string; score: number; frequency: number }[]): GraphNode[] {
		const maxFreq = Math.max(...raw.map((n) => n.frequency), 1);
		return raw.map((n, i) => {
			const angle = (2 * Math.PI * i) / Math.max(raw.length, 1);
			const spread = 120;
			return {
				...n,
				x: WIDTH / 2 + Math.cos(angle) * spread,
				y: HEIGHT / 2 + Math.sin(angle) * spread,
				vx: 0,
				vy: 0,
				radius: computeRadius(n.frequency, maxFreq),
			};
		});
	}

	function tick(): void {
		const REPULSION = 3500;
		const ATTRACTION = 0.04;
		const DAMPING = 0.85;
		const CENTER_PULL = 0.005;

		const edgeSet = new Set(edges.map((e) => `${e.source}-${e.target}`));

		nodes = nodes.map((a, i) => {
			let fx = 0;
			let fy = 0;

			for (let j = 0; j < nodes.length; j++) {
				if (i === j) continue;
				const b = nodes[j];
				const dx = a.x - b.x;
				const dy = a.y - b.y;
				const dist = Math.sqrt(dx * dx + dy * dy) || 1;
				fx += (dx / dist) * (REPULSION / (dist * dist));
				fy += (dy / dist) * (REPULSION / (dist * dist));
			}

			for (const b of nodes) {
				if (edgeSet.has(`${a.term}-${b.term}`) || edgeSet.has(`${b.term}-${a.term}`)) {
					const dx = b.x - a.x;
					const dy = b.y - a.y;
					fx += dx * ATTRACTION;
					fy += dy * ATTRACTION;
				}
			}

			fx += (WIDTH / 2 - a.x) * CENTER_PULL;
			fy += (HEIGHT / 2 - a.y) * CENTER_PULL;

			const vx = (a.vx + fx) * DAMPING;
			const vy = (a.vy + fy) * DAMPING;
			const x = Math.max(a.radius, Math.min(WIDTH - a.radius, a.x + vx));
			const y = Math.max(a.radius, Math.min(HEIGHT - a.radius, a.y + vy));
			return { ...a, x, y, vx, vy };
		});

		animFrame = requestAnimationFrame(tick);
	}

	function edgeCoords(
		edge: GraphEdge
	): { x1: number; y1: number; x2: number; y2: number } | null {
		const src = nodes.find((n) => n.term === edge.source);
		const tgt = nodes.find((n) => n.term === edge.target);
		if (!src || !tgt) return null;
		return { x1: src.x, y1: src.y, x2: tgt.x, y2: tgt.y };
	}

	function edgeStrokeWidth(weight: number): number {
		return Math.max(0.5, Math.min(3, weight * 3));
	}

	function edgeOpacity(weight: number): number {
		return Math.max(0.2, Math.min(0.8, weight * 0.8));
	}

	function handleMouseEnter(node: GraphNode, event: MouseEvent): void {
		hoveredNode = node;
		tooltipX = node.x;
		tooltipY = node.y - node.radius - 8;
	}

	function handleMouseLeave(): void {
		hoveredNode = null;
	}

	onMount(() => {
		void (async () => {
			try {
				const data = await apiRequest<KeywordGraphResponse>(
					`/trends/${groupId}/keywords/graph`
				);
				if (data.nodes.length > 0) {
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
				}
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

	function truncate(text: string, max: number): string {
		return text.length > max ? text.slice(0, max - 1) + '\u2026' : text;
	}
</script>

<div class="space-y-3">
	<h2 class="text-base font-semibold text-gray-900">{$t('trends.keyword_graph.title')}</h2>

	{#if isLoading}
		<div class="flex h-48 items-center justify-center rounded-lg border border-gray-200 bg-white">
			<p class="text-sm text-gray-500">{$t('trends.keyword_graph.loading')}</p>
		</div>
	{:else if nodes.length === 0}
		<div class="flex h-48 items-center justify-center rounded-lg border border-gray-200 bg-white">
			<p class="text-sm text-gray-500">{$t('trends.keyword_graph.empty')}</p>
		</div>
	{:else}
		<div class="overflow-hidden rounded-lg border border-gray-200 bg-white">
			<svg
				viewBox="0 0 {WIDTH} {HEIGHT}"
				width="100%"
				height={HEIGHT}
				aria-label={$t('trends.keyword_graph.title')}
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
							stroke="#d1d5db"
							stroke-width={edgeStrokeWidth(edge.weight)}
							opacity={edgeOpacity(edge.weight)}
						/>
					{/if}
				{/each}

				<!-- Nodes -->
				{#each nodes as node}
					<g
						role="img"
						aria-label={node.term}
						onmouseenter={(e) => handleMouseEnter(node, e)}
						onmouseleave={handleMouseLeave}
					>
						<circle
							cx={node.x}
							cy={node.y}
							r={node.radius}
							fill="#eff6ff"
							stroke="#93c5fd"
							stroke-width="2"
						/>
						<text
							x={node.x}
							y={node.y}
							text-anchor="middle"
							dominant-baseline="middle"
							font-size="10"
							font-weight="400"
							fill="#2563eb"
						>
							{truncate(node.term, 8)}
						</text>
					</g>
				{/each}

				<!-- Tooltip -->
				{#if hoveredNode}
					{@const tx = tooltipX}
					{@const ty = tooltipY}
					<g>
						<rect
							x={tx - 50}
							y={ty - 14}
							width="100"
							height="20"
							rx="4"
							fill="rgba(0,0,0,0.75)"
						/>
						<text
							x={tx}
							y={ty}
							text-anchor="middle"
							dominant-baseline="middle"
							font-size="11"
							fill="#ffffff"
						>
							{hoveredNode.term} ({hoveredNode.frequency})
						</text>
					</g>
				{/if}
			</svg>
		</div>
	{/if}
</div>
