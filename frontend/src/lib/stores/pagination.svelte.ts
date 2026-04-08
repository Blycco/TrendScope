/**
 * Pagination store: manages cursor-based pagination state.
 * Uses Svelte 5 runes ($state).
 */

export interface PaginatedResponse<T> {
	items: T[];
	next_cursor: string | null;
}

export type FetchFn<T> = (cursor?: string) => Promise<PaginatedResponse<T>>;

export interface PaginationStore<T> {
	readonly items: T[];
	readonly isLoading: boolean;
	readonly isLoadingMore: boolean;
	readonly hasMore: boolean;
	readonly nextCursor: string | null;
	load(fetchFn: FetchFn<T>): Promise<void>;
	loadMore(fetchFn: FetchFn<T>): Promise<void>;
	reset(): void;
}

export function createPaginationStore<T>(): PaginationStore<T> {
	let items = $state<T[]>([]);
	let nextCursor = $state<string | null>(null);
	let isLoading = $state(false);
	let isLoadingMore = $state(false);

	async function load(fetchFn: FetchFn<T>): Promise<void> {
		isLoading = true;
		try {
			const data = await fetchFn();
			items = data.items;
			nextCursor = data.next_cursor;
		} finally {
			isLoading = false;
		}
	}

	async function loadMore(fetchFn: FetchFn<T>): Promise<void> {
		if (!nextCursor || isLoadingMore) return;
		isLoadingMore = true;
		try {
			const data = await fetchFn(nextCursor);
			items = [...items, ...data.items];
			nextCursor = data.next_cursor;
		} finally {
			isLoadingMore = false;
		}
	}

	function reset(): void {
		items = [];
		nextCursor = null;
		isLoading = false;
		isLoadingMore = false;
	}

	return {
		get items() { return items; },
		get isLoading() { return isLoading; },
		get isLoadingMore() { return isLoadingMore; },
		get hasMore() { return nextCursor !== null; },
		get nextCursor() { return nextCursor; },
		load,
		loadMore,
		reset
	};
}
