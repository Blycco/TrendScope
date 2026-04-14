<script lang="ts">
	type Plan = 'free' | 'pro' | 'business' | 'enterprise';

	interface Props {
		plan: Plan;
	}

	let { plan }: Props = $props();

	const LABELS: Record<Plan, string> = {
		free: 'Free',
		pro: 'Pro',
		business: 'Business',
		enterprise: 'Enterprise'
	};

	const STYLES: Record<Plan, string> = {
		free: 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300',
		pro: 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400',
		business: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400',
		enterprise: 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400'
	};
</script>

<span class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium {STYLES[plan]}">
	{LABELS[plan]}
</span>
