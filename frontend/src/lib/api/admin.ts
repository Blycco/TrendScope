/**
 * Admin API client for /admin/v1/* endpoints.
 * RULE 01: API base URL from environment variable.
 * RULE 06: All async functions have try/catch.
 */

const ADMIN_API_BASE = import.meta.env.VITE_ADMIN_API_BASE_URL ?? '/admin/v1';

function getAccessToken(): string | null {
	try {
		return localStorage.getItem('access_token');
	} catch {
		return null;
	}
}

export async function adminRequest<T>(
	path: string,
	options: { method?: string; body?: unknown } = {}
): Promise<T> {
	const { method = 'GET', body } = options;
	const url = `${ADMIN_API_BASE}${path}`;

	const headers: Record<string, string> = {
		'Content-Type': 'application/json'
	};

	const token = getAccessToken();
	if (token) {
		headers['Authorization'] = `Bearer ${token}`;
	}

	try {
		const response = await fetch(url, {
			method,
			headers,
			body: body ? JSON.stringify(body) : undefined
		});

		if (!response.ok) {
			const errorBody = await response.json().catch(() => ({}));
			throw {
				status: response.status,
				code: errorBody.code ?? errorBody.detail?.code ?? 'UNKNOWN',
				message: errorBody.message ?? errorBody.detail?.message ?? response.statusText
			};
		}

		if (response.status === 204) {
			return undefined as T;
		}

		const contentType = response.headers.get('content-type') ?? '';
		if (contentType.includes('text/csv')) {
			return (await response.text()) as T;
		}

		return (await response.json()) as T;
	} catch (error) {
		if (error && typeof error === 'object' && 'status' in error) {
			throw error;
		}
		throw { status: 0, code: 'NETWORK', message: 'Network request failed' };
	}
}

export async function adminDownload(
	path: string,
	filename: string
): Promise<void> {
	const url = `${ADMIN_API_BASE}${path}`;
	const headers: Record<string, string> = {};
	const token = getAccessToken();
	if (token) {
		headers['Authorization'] = `Bearer ${token}`;
	}

	try {
		const response = await fetch(url, { headers });
		if (!response.ok) {
			throw new Error('Download failed');
		}
		const blob = await response.blob();
		const a = document.createElement('a');
		a.href = URL.createObjectURL(blob);
		a.download = filename;
		a.click();
		URL.revokeObjectURL(a.href);
	} catch (error) {
		throw { status: 0, code: 'DOWNLOAD_FAILED', message: 'Download failed' };
	}
}
