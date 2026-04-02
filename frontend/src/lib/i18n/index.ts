import { init, addMessages, getLocaleFromNavigator } from 'svelte-i18n';
import ko from './ko.json';
import en from './en.json';

addMessages('ko', ko);
addMessages('en', en);

export function initI18n(): void {
	const isBrowser = typeof window !== 'undefined';
	init({
		fallbackLocale: 'ko',
		initialLocale: isBrowser ? (getLocaleFromNavigator() ?? 'ko') : 'ko'
	});
}
