/**
 * Behavior event tracker.
 * Batches events and sends them to /api/v1/events.
 * RULE 01: No hardcoded secrets.
 * RULE 06: try/catch on all async.
 */

import type { BehaviorEvent } from '$lib/api';

const BATCH_SIZE = 10;
const FLUSH_INTERVAL_MS = 30_000;
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

let eventQueue: BehaviorEvent[] = [];
let flushTimer: ReturnType<typeof setInterval> | null = null;

export function trackEvent(eventType: string, payload: Record<string, unknown> = {}): void {
	eventQueue.push({
		event_type: eventType,
		payload,
		timestamp: new Date().toISOString()
	});

	if (eventQueue.length >= BATCH_SIZE) {
		flush();
	}
}

export async function flush(): Promise<void> {
	if (eventQueue.length === 0) return;

	const batch = [...eventQueue];
	eventQueue = [];

	try {
		const token = localStorage.getItem('access_token');
		const headers: Record<string, string> = {
			'Content-Type': 'application/json'
		};
		if (token) {
			headers['Authorization'] = `Bearer ${token}`;
		}

		await fetch(`${API_BASE}/events`, {
			method: 'POST',
			headers,
			body: JSON.stringify({ events: batch })
		});
	} catch {
		// Re-queue failed events (drop if too many to prevent memory leak)
		if (eventQueue.length < 100) {
			eventQueue = [...batch, ...eventQueue];
		}
	}
}

export function startAutoFlush(): void {
	if (flushTimer) return;
	flushTimer = setInterval(flush, FLUSH_INTERVAL_MS);
}

export function stopAutoFlush(): void {
	if (flushTimer) {
		clearInterval(flushTimer);
		flushTimer = null;
	}
	flush();
}
