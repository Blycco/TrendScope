/**
 * Personalization store: shares user's personalization settings across pages
 * and broadcasts changes so dependent feeds (e.g. /trends) reload automatically.
 */

export interface PersonalizationSettings {
	category_weights: { tech: number; finance: number; entertainment: number; lifestyle: number };
	locale_ratio: number;
}

function createPersonalizationStore() {
	let settings = $state<PersonalizationSettings | null>(null);
	let version = $state(0);

	function set(next: PersonalizationSettings): void {
		settings = next;
		version += 1;
	}

	function clear(): void {
		settings = null;
		version += 1;
	}

	return {
		get settings() { return settings; },
		get version() { return version; },
		set,
		clear,
	};
}

export const personalizationStore = createPersonalizationStore();
