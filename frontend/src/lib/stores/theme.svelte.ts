/**
 * Theme store: manages dark/light/system theme state.
 * Uses Svelte 5 runes ($state).
 */

type Theme = 'light' | 'dark' | 'system';
type ResolvedTheme = 'light' | 'dark';

const STORAGE_KEY = 'trendscope-theme';

function createThemeStore() {
	let theme = $state<Theme>('system');
	let resolvedTheme = $state<ResolvedTheme>('light');
	let mediaQuery: MediaQueryList | null = null;

	function getSystemTheme(): ResolvedTheme {
		if (typeof window === 'undefined') return 'light';
		return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
	}

	function applyTheme(resolved: ResolvedTheme): void {
		resolvedTheme = resolved;
		if (typeof document === 'undefined') return;
		if (resolved === 'dark') {
			document.documentElement.classList.add('dark');
		} else {
			document.documentElement.classList.remove('dark');
		}
	}

	function resolveAndApply(): void {
		const resolved: ResolvedTheme = theme === 'system' ? getSystemTheme() : theme;
		applyTheme(resolved);
	}

	function handleSystemChange(): void {
		if (theme === 'system') {
			resolveAndApply();
		}
	}

	function initialize(): void {
		if (typeof window === 'undefined') return;

		const stored = localStorage.getItem(STORAGE_KEY);
		if (stored === 'light' || stored === 'dark' || stored === 'system') {
			theme = stored;
		} else {
			theme = 'system';
		}

		mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
		mediaQuery.addEventListener('change', handleSystemChange);

		resolveAndApply();
	}

	function setTheme(t: Theme): void {
		theme = t;
		if (typeof window !== 'undefined') {
			localStorage.setItem(STORAGE_KEY, t);
		}
		resolveAndApply();
	}

	function toggleTheme(): void {
		const order: Theme[] = ['light', 'dark', 'system'];
		const idx = order.indexOf(theme);
		const next = order[(idx + 1) % order.length];
		setTheme(next);
	}

	return {
		get theme() { return theme; },
		get resolvedTheme() { return resolvedTheme; },
		initialize,
		setTheme,
		toggleTheme,
	};
}

export const themeStore = createThemeStore();
