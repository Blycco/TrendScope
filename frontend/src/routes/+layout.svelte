<script lang="ts">
	import '../app.css';

	let { children } = $props();
</script>

<div class="min-h-screen bg-gray-50">
	<nav class="bg-white border-b border-gray-200">
		<div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
			<div class="flex h-16 items-center justify-between">
				<div class="flex items-center gap-8">
					<a href="/" class="text-xl font-bold text-gray-900">TrendScope</a>
					<div class="hidden sm:flex items-center gap-4">
						<a href="/trends" class="text-sm text-gray-600 hover:text-gray-900">Trends</a>
						<a href="/news" class="text-sm text-gray-600 hover:text-gray-900">News</a>
					</div>
				</div>
				<div class="flex items-center gap-4">
					<a href="/auth/login" class="text-sm text-gray-600 hover:text-gray-900">Login</a>
				</div>
			</div>
		</div>
	</nav>

	<main class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
		{@render children()}
	</main>
</div>
