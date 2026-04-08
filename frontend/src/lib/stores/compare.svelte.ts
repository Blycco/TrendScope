/**
 * Compare store: manages selected trend IDs for comparison.
 * Uses Svelte 5 runes ($state).
 */

const MAX_TRENDS = 5;

function createCompareStore() {
	let selectedIds = $state<string[]>([]);

	function addTrend(id: string): void {
		if (selectedIds.length >= MAX_TRENDS) return;
		if (selectedIds.includes(id)) return;
		selectedIds = [...selectedIds, id];
	}

	function removeTrend(id: string): void {
		selectedIds = selectedIds.filter((x) => x !== id);
	}

	function clearAll(): void {
		selectedIds = [];
	}

	function setFromUrl(idsParam: string | null): void {
		if (!idsParam) {
			selectedIds = [];
			return;
		}
		const ids = idsParam
			.split(',')
			.map((s) => s.trim())
			.filter((s) => s.length > 0)
			.slice(0, MAX_TRENDS);
		selectedIds = ids;
	}

	function toUrlParam(): string {
		return selectedIds.join(',');
	}

	return {
		get selectedIds() {
			return selectedIds;
		},
		addTrend,
		removeTrend,
		clearAll,
		setFromUrl,
		toUrlParam
	};
}

export const compareStore = createCompareStore();
