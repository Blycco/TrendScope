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
	article_count: number;
	direction: 'rising' | 'steady' | 'declining';
	status: 'exploding' | 'rising' | 'stable' | 'declining' | 'peaked';
}

export interface TrendListResponse {
	items: TrendItem[];
	next_cursor: string | null;
	total: number;
}

export interface TimelinePoint {
	timestamp: string;
	article_count: number;
	source_count: number;
}

export interface TrendTimelineResponse {
	group_id: string;
	interval: string;
	points: TimelinePoint[];
}

export interface SentimentDistribution {
	positive: number;
	neutral: number;
	negative: number;
	total: number;
}

// ---------------------------------------------------------------------------
// Forecast types
// ---------------------------------------------------------------------------

export interface ForecastPoint {
	date: string;
	yhat: number;
	yhat_lower: number;
	yhat_upper: number;
}

export interface ForecastResponse {
	group_id: string;
	horizon_days: number;
	points: ForecastPoint[];
}

// ---------------------------------------------------------------------------
// Dashboard types
// ---------------------------------------------------------------------------

export interface DashboardSummaryResponse {
	total_trends: number;
	total_news: number;
	avg_score: number;
	top_category: string | null;
	early_signal_count: number;
	category_counts: Record<string, number>;
	source_counts: Record<string, number>;
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

// ---------------------------------------------------------------------------
// Keyword Graph types
// ---------------------------------------------------------------------------

export interface KeywordNode {
	term: string;
	score: number;
	frequency: number;
}

export interface KeywordEdge {
	source: string;
	target: string;
	weight: number;
}

export interface KeywordGraphResponse {
	group_id: string;
	nodes: KeywordNode[];
	edges: KeywordEdge[];
}
