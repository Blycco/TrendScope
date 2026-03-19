/**
 * Auth store: manages user session state.
 * Uses Svelte 5 runes ($state).
 */

import { login as apiLogin, logout as apiLogout, apiRequest, clearTokens } from '$lib/api';
import type { UserResponse } from '$lib/api';

interface AuthState {
	user: UserResponse | null;
	isAuthenticated: boolean;
	isLoading: boolean;
}

function createAuthStore() {
	let state = $state<AuthState>({
		user: null,
		isAuthenticated: false,
		isLoading: false
	});

	async function login(email: string, password: string): Promise<void> {
		state.isLoading = true;
		try {
			await apiLogin(email, password);
			await fetchUser();
		} catch (error) {
			state.isLoading = false;
			throw error;
		}
	}

	async function logout(): Promise<void> {
		try {
			await apiLogout();
		} finally {
			state.user = null;
			state.isAuthenticated = false;
		}
	}

	async function fetchUser(): Promise<void> {
		state.isLoading = true;
		try {
			const user = await apiRequest<UserResponse>('/settings');
			state.user = user;
			state.isAuthenticated = true;
		} catch {
			state.user = null;
			state.isAuthenticated = false;
			clearTokens();
		} finally {
			state.isLoading = false;
		}
	}

	async function initialize(): Promise<void> {
		try {
			const token = localStorage.getItem('access_token');
			if (token) {
				await fetchUser();
			}
		} catch {
			// No token or failed to fetch
		}
	}

	return {
		get user() { return state.user; },
		get isAuthenticated() { return state.isAuthenticated; },
		get isLoading() { return state.isLoading; },
		login,
		logout,
		fetchUser,
		initialize
	};
}

export const authStore = createAuthStore();
