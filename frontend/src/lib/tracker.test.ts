import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { trackEvent, flush, startAutoFlush, stopAutoFlush } from './tracker';

// Mock localStorage
const localStorageMock = (() => {
	let store: Record<string, string> = {};
	return {
		getItem: vi.fn((key: string) => store[key] ?? null),
		setItem: vi.fn((key: string, value: string) => { store[key] = value; }),
		removeItem: vi.fn((key: string) => { delete store[key]; }),
		clear: vi.fn(() => { store = {}; })
	};
})();

Object.defineProperty(globalThis, 'localStorage', { value: localStorageMock });

describe('Tracker', () => {
	beforeEach(() => {
		localStorageMock.clear();
		vi.restoreAllMocks();
		globalThis.fetch = vi.fn().mockResolvedValue({ ok: true });
	});

	afterEach(() => {
		stopAutoFlush();
		vi.restoreAllMocks();
	});

	it('trackEvent adds event to queue', () => {
		trackEvent('page_view', { page: 'home' });
		// Flush to verify event was queued
		flush();
		expect(globalThis.fetch).toHaveBeenCalledTimes(1);
	});

	it('flush sends batched events', async () => {
		trackEvent('click', { target: 'button1' });
		trackEvent('click', { target: 'button2' });

		await flush();

		expect(globalThis.fetch).toHaveBeenCalledTimes(1);
		const callArgs = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
		const body = JSON.parse(callArgs[1].body);
		expect(body.events).toHaveLength(2);
		expect(body.events[0].event_type).toBe('click');
		expect(body.events[1].event_type).toBe('click');
	});

	it('flush does nothing when queue is empty', async () => {
		await flush();
		expect(globalThis.fetch).not.toHaveBeenCalled();
	});

	it('includes auth header when token exists', async () => {
		localStorageMock.setItem('access_token', 'test-token');
		trackEvent('test', {});
		await flush();

		const callArgs = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
		expect(callArgs[1].headers['Authorization']).toBe('Bearer test-token');
	});

	it('events have timestamps', async () => {
		trackEvent('test', {});
		await flush();

		const callArgs = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
		const body = JSON.parse(callArgs[1].body);
		expect(body.events[0].timestamp).toBeDefined();
	});

	it('startAutoFlush and stopAutoFlush manage intervals', () => {
		vi.useFakeTimers();
		startAutoFlush();
		trackEvent('test', {});

		// Should not have flushed yet
		expect(globalThis.fetch).not.toHaveBeenCalled();

		// Advance timer past flush interval (30s)
		vi.advanceTimersByTime(31_000);
		expect(globalThis.fetch).toHaveBeenCalled();

		stopAutoFlush();
		vi.useRealTimers();
	});

	it('re-queues events on fetch failure', async () => {
		globalThis.fetch = vi.fn().mockRejectedValue(new Error('network error'));

		trackEvent('important', { data: 1 });
		await flush();

		// Event should be re-queued
		globalThis.fetch = vi.fn().mockResolvedValue({ ok: true });
		await flush();
		expect(globalThis.fetch).toHaveBeenCalledTimes(1);
	});
});
