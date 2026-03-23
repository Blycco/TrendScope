import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
	ApiRequestError,
	QuotaExceededRequestError,
	PlanGateRequestError,
	NetworkError,
	apiRequest,
	clearTokens
} from './client';

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

describe('API Client', () => {
	beforeEach(() => {
		localStorageMock.clear();
		vi.restoreAllMocks();
	});

	afterEach(() => {
		vi.restoreAllMocks();
	});

	describe('Error classes', () => {
		it('ApiRequestError has correct properties', () => {
			const error = new ApiRequestError(400, 'E0001', 'test error', 'detail');
			expect(error.status).toBe(400);
			expect(error.errorCode).toBe('E0001');
			expect(error.errorMessage).toBe('test error');
			expect(error.detail).toBe('detail');
			expect(error.name).toBe('ApiRequestError');
		});

		it('QuotaExceededRequestError has correct properties', () => {
			const error = new QuotaExceededRequestError('daily_trends', 10, '2024-01-01T00:00:00Z', '/pricing');
			expect(error.status).toBe(429);
			expect(error.errorCode).toBe('QUOTA_EXCEEDED');
			expect(error.quotaType).toBe('daily_trends');
			expect(error.limit).toBe(10);
			expect(error.resetAt).toBe('2024-01-01T00:00:00Z');
			expect(error.upgradeUrl).toBe('/pricing');
			expect(error.name).toBe('QuotaExceededRequestError');
		});

		it('PlanGateRequestError has correct properties', () => {
			const error = new PlanGateRequestError('pro', '/pricing');
			expect(error.status).toBe(403);
			expect(error.errorCode).toBe('PLAN_GATE');
			expect(error.requiredPlan).toBe('pro');
			expect(error.upgradeUrl).toBe('/pricing');
			expect(error.name).toBe('PlanGateRequestError');
		});

		it('NetworkError has correct name', () => {
			const error = new NetworkError('connection failed');
			expect(error.name).toBe('NetworkError');
			expect(error.message).toBe('connection failed');
		});
	});

	describe('clearTokens', () => {
		it('removes tokens from localStorage', () => {
			localStorageMock.setItem('access_token', 'test');
			localStorageMock.setItem('refresh_token', 'test');
			clearTokens();
			expect(localStorageMock.removeItem).toHaveBeenCalledWith('access_token');
			expect(localStorageMock.removeItem).toHaveBeenCalledWith('refresh_token');
		});
	});

	describe('apiRequest', () => {
		it('makes successful GET request', async () => {
			const mockResponse = { items: [], next_cursor: null };
			globalThis.fetch = vi.fn().mockResolvedValue({
				ok: true,
				json: () => Promise.resolve(mockResponse)
			});

			const result = await apiRequest('/trends');
			expect(result).toEqual(mockResponse);
			expect(globalThis.fetch).toHaveBeenCalledTimes(1);
		});

		it('includes auth header when token exists', async () => {
			localStorageMock.setItem('access_token', 'my-token');
			globalThis.fetch = vi.fn().mockResolvedValue({
				ok: true,
				json: () => Promise.resolve({})
			});

			await apiRequest('/trends');

			const callArgs = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
			expect(callArgs[1].headers['Authorization']).toBe('Bearer my-token');
		});

		it('throws ApiRequestError on error response', async () => {
			globalThis.fetch = vi.fn().mockResolvedValue({
				ok: false,
				status: 400,
				statusText: 'Bad Request',
				json: () => Promise.resolve({ code: 'E0001', message: 'bad request' })
			});

			await expect(apiRequest('/trends', { auth: false })).rejects.toThrow(ApiRequestError);
		});

		it('throws QuotaExceededRequestError on quota error', async () => {
			globalThis.fetch = vi.fn().mockResolvedValue({
				ok: false,
				status: 429,
				statusText: 'Too Many Requests',
				json: () => Promise.resolve({
					error_code: 'QUOTA_EXCEEDED',
					message_key: 'error.quota_exceeded',
					quota_type: 'daily_trends',
					limit: 10,
					reset_at: '2024-01-01T00:00:00Z',
					upgrade_url: '/pricing'
				})
			});

			await expect(apiRequest('/trends', { auth: false })).rejects.toThrow(QuotaExceededRequestError);
		});

		it('throws PlanGateRequestError on plan gate error', async () => {
			globalThis.fetch = vi.fn().mockResolvedValue({
				ok: false,
				status: 403,
				statusText: 'Forbidden',
				json: () => Promise.resolve({
					error_code: 'PLAN_GATE',
					message_key: 'error.plan_required',
					required_plan: 'pro',
					upgrade_url: '/pricing'
				})
			});

			await expect(apiRequest('/trends', { auth: false })).rejects.toThrow(PlanGateRequestError);
		});

		it('throws NetworkError on fetch failure', async () => {
			globalThis.fetch = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'));

			await expect(apiRequest('/trends', { auth: false })).rejects.toThrow(NetworkError);
		});

		it('sends POST body correctly', async () => {
			globalThis.fetch = vi.fn().mockResolvedValue({
				ok: true,
				json: () => Promise.resolve({ success: true })
			});

			await apiRequest('/auth/login', {
				method: 'POST',
				body: { email: 'test@test.com', password: 'pass' },
				auth: false
			});

			const callArgs = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
			expect(callArgs[1].method).toBe('POST');
			expect(JSON.parse(callArgs[1].body)).toEqual({ email: 'test@test.com', password: 'pass' });
		});

		it('attempts token refresh on 401', async () => {
			localStorageMock.setItem('access_token', 'old-token');
			localStorageMock.setItem('refresh_token', 'refresh-token');

			let callCount = 0;
			globalThis.fetch = vi.fn().mockImplementation((url: string) => {
				if (url.includes('/auth/refresh')) {
					return Promise.resolve({
						ok: true,
						json: () => Promise.resolve({ access_token: 'new-token', refresh_token: 'new-refresh' })
					});
				}
				callCount++;
				if (callCount === 1) {
					return Promise.resolve({
						ok: false,
						status: 401,
						statusText: 'Unauthorized',
						json: () => Promise.resolve({ code: 'E0012', message: 'Token expired' })
					});
				}
				return Promise.resolve({
					ok: true,
					json: () => Promise.resolve({ data: 'success' })
				});
			});

			const result = await apiRequest('/trends');
			expect(result).toEqual({ data: 'success' });
		});
	});
});
