/**
 * Cache store: simple client-side response cache with optional TTL-based expiry.
 * Uses Svelte 5 runes ($state).
 */

interface CacheEntry<T> {
	value: T;
	expiresAt: number | null;
}

export interface CacheStore<T> {
	get(key: string): T | undefined;
	set(key: string, value: T): void;
	invalidate(key: string): void;
	clear(): void;
	readonly size: number;
}

export function createCacheStore<T>(ttlMs?: number): CacheStore<T> {
	let entries = $state<Map<string, CacheEntry<T>>>(new Map());

	function get(key: string): T | undefined {
		const entry = entries.get(key);
		if (!entry) return undefined;
		if (entry.expiresAt !== null && Date.now() > entry.expiresAt) {
			entries.delete(key);
			entries = new Map(entries);
			return undefined;
		}
		return entry.value;
	}

	function set(key: string, value: T): void {
		const expiresAt = ttlMs ? Date.now() + ttlMs : null;
		const next = new Map(entries);
		next.set(key, { value, expiresAt });
		entries = next;
	}

	function invalidate(key: string): void {
		if (entries.has(key)) {
			const next = new Map(entries);
			next.delete(key);
			entries = next;
		}
	}

	function clear(): void {
		entries = new Map();
	}

	return {
		get,
		set,
		invalidate,
		clear,
		get size() { return entries.size; }
	};
}
