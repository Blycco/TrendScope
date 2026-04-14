/**
 * HTTP API client with token management and structured error handling.
 * RULE 01: API base URL from environment variable.
 * RULE 06: All async functions have try/catch.
 * RULE 12: Errors use structured error codes.
 */

import type { ApiError, QuotaExceededError, PlanGateError } from './types';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

// ---------------------------------------------------------------------------
// Custom error classes
// ---------------------------------------------------------------------------

export class ApiRequestError extends Error {
	constructor(
		public status: number,
		public errorCode: string,
		public errorMessage: string,
		public detail?: string
	) {
		super(errorMessage);
		this.name = 'ApiRequestError';
	}
}

export class QuotaExceededRequestError extends ApiRequestError {
	constructor(
		public quotaType: string,
		public limit: number,
		public resetAt: string,
		public upgradeUrl: string
	) {
		super(429, 'QUOTA_EXCEEDED', 'Quota exceeded');
		this.name = 'QuotaExceededRequestError';
	}
}

export class PlanGateRequestError extends ApiRequestError {
	constructor(
		public requiredPlan: string,
		public upgradeUrl: string
	) {
		super(403, 'PLAN_GATE', 'Plan upgrade required');
		this.name = 'PlanGateRequestError';
	}
}

export class NetworkError extends Error {
	constructor(message: string) {
		super(message);
		this.name = 'NetworkError';
	}
}

// ---------------------------------------------------------------------------
// Token storage
// ---------------------------------------------------------------------------

function getAccessToken(): string | null {
	try {
		return localStorage.getItem('access_token');
	} catch {
		return null;
	}
}

function getRefreshToken(): string | null {
	try {
		return localStorage.getItem('refresh_token');
	} catch {
		return null;
	}
}

function setTokens(access: string, refresh: string): void {
	try {
		localStorage.setItem('access_token', access);
		localStorage.setItem('refresh_token', refresh);
	} catch {
		// SSR or storage unavailable
	}
}

export function clearTokens(): void {
	try {
		localStorage.removeItem('access_token');
		localStorage.removeItem('refresh_token');
	} catch {
		// SSR or storage unavailable
	}
}

// ---------------------------------------------------------------------------
// Core fetch wrapper
// ---------------------------------------------------------------------------

async function parseErrorBody(
	response: Response
): Promise<ApiError | QuotaExceededError | PlanGateError> {
	try {
		return await response.json();
	} catch {
		return { code: 'UNKNOWN', message: response.statusText };
	}
}

async function handleErrorResponse(response: Response): Promise<never> {
	const body = await parseErrorBody(response);

	if ('error_code' in body && body.error_code === 'QUOTA_EXCEEDED') {
		const qe = body as QuotaExceededError;
		throw new QuotaExceededRequestError(
			qe.quota_type,
			qe.limit,
			qe.reset_at,
			qe.upgrade_url
		);
	}

	if ('error_code' in body && body.error_code === 'PLAN_GATE') {
		const pg = body as PlanGateError;
		throw new PlanGateRequestError(pg.required_plan, pg.upgrade_url);
	}

	const apiErr = body as ApiError;
	throw new ApiRequestError(
		response.status,
		apiErr.code ?? 'UNKNOWN',
		apiErr.message ?? response.statusText,
		apiErr.detail
	);
}

async function refreshAccessToken(): Promise<boolean> {
	const refreshToken = getRefreshToken();
	if (!refreshToken) return false;

	try {
		const response = await fetch(`${API_BASE}/auth/refresh`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ refresh_token: refreshToken })
		});

		if (!response.ok) {
			clearTokens();
			return false;
		}

		const data = await response.json();
		setTokens(data.access_token, data.refresh_token);
		return true;
	} catch {
		clearTokens();
		return false;
	}
}

interface RequestOptions {
	method?: string;
	body?: unknown;
	headers?: Record<string, string>;
	auth?: boolean;
}

export async function apiRequest<T>(
	path: string,
	options: RequestOptions = {}
): Promise<T> {
	const { method = 'GET', body, headers = {}, auth = true } = options;
	const url = `${API_BASE}${path}`;

	const reqHeaders: Record<string, string> = {
		'Content-Type': 'application/json',
		...headers
	};

	if (auth) {
		const token = getAccessToken();
		if (token) {
			reqHeaders['Authorization'] = `Bearer ${token}`;
		}
	}

	try {
		let response = await fetch(url, {
			method,
			headers: reqHeaders,
			body: body ? JSON.stringify(body) : undefined
		});

		// Attempt token refresh on 401
		if (response.status === 401 && auth) {
			const refreshed = await refreshAccessToken();
			if (refreshed) {
				const newToken = getAccessToken();
				if (newToken) {
					reqHeaders['Authorization'] = `Bearer ${newToken}`;
				}
				response = await fetch(url, {
					method,
					headers: reqHeaders,
					body: body ? JSON.stringify(body) : undefined
				});
			}
		}

		if (!response.ok) {
			await handleErrorResponse(response);
		}

		return (await response.json()) as T;
	} catch (error) {
		if (
			error instanceof ApiRequestError ||
			error instanceof QuotaExceededRequestError ||
			error instanceof PlanGateRequestError
		) {
			throw error;
		}
		throw new NetworkError(
			error instanceof Error ? error.message : 'Network request failed'
		);
	}
}

export async function apiRequestBlob(
	path: string,
	options: RequestOptions = {}
): Promise<Blob> {
	const { method = 'GET', body, headers = {}, auth = true } = options;
	const url = `${API_BASE}${path}`;

	const reqHeaders: Record<string, string> = { ...headers };
	if (auth) {
		const token = getAccessToken();
		if (token) reqHeaders['Authorization'] = `Bearer ${token}`;
	}
	if (body !== undefined && !reqHeaders['Content-Type']) {
		reqHeaders['Content-Type'] = 'application/json';
	}

	try {
		let response = await fetch(url, {
			method,
			headers: reqHeaders,
			body: body ? JSON.stringify(body) : undefined
		});

		if (response.status === 401 && auth) {
			const refreshed = await refreshAccessToken();
			if (refreshed) {
				const newToken = getAccessToken();
				if (newToken) reqHeaders['Authorization'] = `Bearer ${newToken}`;
				response = await fetch(url, {
					method,
					headers: reqHeaders,
					body: body ? JSON.stringify(body) : undefined
				});
			}
		}

		if (!response.ok) {
			await handleErrorResponse(response);
		}

		return await response.blob();
	} catch (error) {
		if (
			error instanceof ApiRequestError ||
			error instanceof QuotaExceededRequestError ||
			error instanceof PlanGateRequestError
		) {
			throw error;
		}
		throw new NetworkError(
			error instanceof Error ? error.message : 'Network request failed'
		);
	}
}

// ---------------------------------------------------------------------------
// Auth helpers
// ---------------------------------------------------------------------------

export async function login(
	email: string,
	password: string
): Promise<{ access_token: string; refresh_token: string }> {
	const data = await apiRequest<{ access_token: string; refresh_token: string }>(
		'/auth/login',
		{
			method: 'POST',
			body: { email, password },
			auth: false
		}
	);
	setTokens(data.access_token, data.refresh_token);
	return data;
}

export async function logout(): Promise<void> {
	try {
		await apiRequest('/auth/logout', { method: 'POST' });
	} finally {
		clearTokens();
	}
}
