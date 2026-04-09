/**
 * Filter store: manages filter state with URL query param sync.
 * Uses Svelte 5 runes ($state, $effect).
 */

import { browser } from '$app/environment';
import { goto } from '$app/navigation';

export type FilterValues = Record<string, string | number | null>;

export interface FilterStore<T extends FilterValues> {
	readonly values: T;
	set<K extends keyof T>(key: K, value: T[K]): void;
	reset(): void;
}

export function createFilterStore<T extends FilterValues>(defaults: T): FilterStore<T> {
	let values = $state<T>({ ...defaults });
	let initialized = false;

	// Read initial values from URL on creation (browser only)
	if (browser) {
		const params = new URLSearchParams(window.location.search);
		const restored = { ...defaults } as T;
		for (const key of Object.keys(defaults)) {
			const raw = params.get(key);
			if (raw !== null) {
				const defaultVal = defaults[key];
				if (typeof defaultVal === 'number' || (defaultVal === null && /^\d+$/.test(raw))) {
					(restored as FilterValues)[key] = Number(raw);
				} else {
					(restored as FilterValues)[key] = raw;
				}
			}
		}
		values = restored;
		initialized = true;
	}

	function syncToUrl(): void {
		if (!browser || !initialized) return;
		const url = new URL(window.location.href);
		let changed = false;
		for (const key of Object.keys(defaults)) {
			const val = values[key];
			const current = url.searchParams.get(key);
			if (val === null || val === defaults[key]) {
				if (current !== null) {
					url.searchParams.delete(key);
					changed = true;
				}
			} else {
				const strVal = String(val);
				if (current !== strVal) {
					url.searchParams.set(key, strVal);
					changed = true;
				}
			}
		}
		if (changed) {
			goto(url.pathname + url.search, { replaceState: true, keepFocus: true, noScroll: true });
		}
	}

	$effect(() => {
		// Track all values to trigger on any change
		const _track = JSON.stringify(values);
		void _track;
		syncToUrl();
	});

	function set<K extends keyof T>(key: K, value: T[K]): void {
		values = { ...values, [key]: value };
	}

	function reset(): void {
		values = { ...defaults };
	}

	return {
		get values() { return values; },
		set,
		reset
	};
}
