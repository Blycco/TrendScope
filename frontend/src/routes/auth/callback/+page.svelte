<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { authStore } from '$lib/stores/auth.svelte';

	onMount(() => {
		const params = $page.url.searchParams;
		const accessToken = params.get('access_token');
		const refreshToken = params.get('refresh_token');

		if (accessToken && refreshToken) {
			localStorage.setItem('access_token', accessToken);
			localStorage.setItem('refresh_token', refreshToken);
			await authStore.initialize();
			goto('/');
		} else {
			goto('/auth/login?error=oauth_failed');
		}
	});
</script>

<div class="flex items-center justify-center py-20">
	<p class="text-gray-500">...</p>
</div>
