import { init, register, getLocaleFromNavigator } from 'svelte-i18n';

register('ko', () => import('./ko.json'));
register('en', () => import('./en.json'));

export function initI18n(): void {
	init({
		fallbackLocale: 'ko',
		initialLocale: getLocaleFromNavigator() ?? 'ko'
	});
}
