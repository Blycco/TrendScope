/**
 * Shared locale formatting utilities.
 * Reads the active svelte-i18n locale store so that date/number formatting
 * always matches the UI language — no hardcoded BCP-47 tags in components.
 */
import { locale } from 'svelte-i18n';
import { get } from 'svelte/store';

/**
 * Returns the BCP-47 locale tag for Intl date/number formatting.
 * Falls back to 'ko-KR' if svelte-i18n locale is not set.
 */
export function getFormattingLocale(): string {
	const current = get(locale);
	if (current === 'en') return 'en-US';
	return 'ko-KR';
}

export function formatDate(
	date: string | Date,
	options?: Intl.DateTimeFormatOptions
): string {
	const loc = getFormattingLocale();
	return new Date(date).toLocaleDateString(loc, options);
}

export function formatDateTime(date: string | Date): string {
	const loc = getFormattingLocale();
	return new Date(date).toLocaleString(loc);
}
