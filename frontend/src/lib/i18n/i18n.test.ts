import { describe, it, expect } from 'vitest';
import ko from './ko.json';
import en from './en.json';

describe('i18n translations', () => {
	it('ko.json has all required keys', () => {
		expect(ko['nav.sidebar.trends']).toBeDefined();
		expect(ko['nav.sidebar.news']).toBeDefined();
		expect(ko['nav.sidebar.login']).toBeDefined();
		expect(ko['nav.sidebar.logout']).toBeDefined();
		expect(ko['page.home.title']).toBeDefined();
		expect(ko['page.trends.title']).toBeDefined();
		expect(ko['modal.error.title']).toBeDefined();
		expect(ko['modal.quota_exceeded.title']).toBeDefined();
		expect(ko['modal.plan_required.title']).toBeDefined();
		expect(ko['error.auth_required']).toBeDefined();
		expect(ko['button.login']).toBeDefined();
		expect(ko['button.register']).toBeDefined();
		expect(ko['status.loading']).toBeDefined();
	});

	it('en.json has all required keys', () => {
		expect(en['nav.sidebar.trends']).toBeDefined();
		expect(en['nav.sidebar.news']).toBeDefined();
		expect(en['nav.sidebar.login']).toBeDefined();
		expect(en['nav.sidebar.logout']).toBeDefined();
		expect(en['page.home.title']).toBeDefined();
		expect(en['page.trends.title']).toBeDefined();
		expect(en['modal.error.title']).toBeDefined();
		expect(en['modal.quota_exceeded.title']).toBeDefined();
		expect(en['modal.plan_required.title']).toBeDefined();
		expect(en['error.auth_required']).toBeDefined();
		expect(en['button.login']).toBeDefined();
		expect(en['button.register']).toBeDefined();
		expect(en['status.loading']).toBeDefined();
	});

	it('ko and en have the same keys', () => {
		const koKeys = Object.keys(ko).sort();
		const enKeys = Object.keys(en).sort();
		expect(koKeys).toEqual(enKeys);
	});

	it('no empty translation values in ko', () => {
		for (const [key, value] of Object.entries(ko)) {
			expect(value, `ko key "${key}" should not be empty`).toBeTruthy();
		}
	});

	it('no empty translation values in en', () => {
		for (const [key, value] of Object.entries(en)) {
			expect(value, `en key "${key}" should not be empty`).toBeTruthy();
		}
	});
});
