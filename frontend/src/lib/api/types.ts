/** API response and request types matching backend schemas. */

// ---------------------------------------------------------------------------
// Error types
// ---------------------------------------------------------------------------

export interface ApiError {
	code: string;
	message: string;
	detail?: string;
}

export interface QuotaExceededError {
	error_code: 'QUOTA_EXCEEDED';
	message_key: string;
	quota_type: string;
	limit: number;
	reset_at: string;
	upgrade_url: string;
}

export interface PlanGateError {
	error_code: 'PLAN_GATE';
	message_key: string;
	required_plan: string;
	upgrade_url: string;
}

// ---------------------------------------------------------------------------
// Auth types
// ---------------------------------------------------------------------------

export interface TokenResponse {
	access_token: string;
	refresh_token: string;
	token_type: string;
}

export interface UserResponse {
	id: string;
	email: string;
	display_name: string | null;
	role: string;
	locale: string;
	plan: string;
}

export interface TwoFARequiredResponse {
	requires_2fa: boolean;
	challenge_token: string;
}

// ---------------------------------------------------------------------------
// Trend types
// ---------------------------------------------------------------------------

export interface TrendItem {
	id: string;
	title: string;
	category: string;
	summary: string | null;
	score: number;
	early_trend_score: number;
	keywords: string[];
	created_at: string;
}

export interface TrendListResponse {
	items: TrendItem[];
	next_cursor: string | null;
	total: number;
}

// ---------------------------------------------------------------------------
// News types
// ---------------------------------------------------------------------------

export interface NewsItem {
	id: string;
	title: string;
	url: string;
	source: string | null;
	publish_time: string;
	summary: string | null;
	article_count: number;
}

export interface NewsListResponse {
	items: NewsItem[];
	next_cursor: string | null;
}

// ---------------------------------------------------------------------------
// Insight types
// ---------------------------------------------------------------------------

export interface MarketerInsight {
	ad_opportunities: string[];
	source_urls: string[];
}

export interface CreatorInsight {
	title_drafts: string[];
	timing: string;
	seo_keywords: string[];
	source_urls: string[];
}

export interface OwnerInsight {
	consumer_reactions: string[];
	product_hints: string[];
	market_ops: string[];
	source_urls: string[];
}

export interface GeneralInsight {
	sns_drafts: string[];
	engagement_methods: string[];
	source_urls: string[];
}

export type InsightContent =
	| MarketerInsight
	| CreatorInsight
	| OwnerInsight
	| GeneralInsight;

export interface InsightResponse {
	keyword: string;
	role: string;
	locale: string;
	content: InsightContent;
	cached: boolean;
	degraded: boolean;
	generated_at: string;
}

// ---------------------------------------------------------------------------
// Pagination
// ---------------------------------------------------------------------------

export interface CursorParams {
	cursor?: string;
	limit?: number;
}

// ---------------------------------------------------------------------------
// Events
// ---------------------------------------------------------------------------

export interface BehaviorEvent {
	event_type: string;
	payload: Record<string, unknown>;
	timestamp?: string;
}
