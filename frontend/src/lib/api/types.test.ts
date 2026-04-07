import { describe, it, expect } from 'vitest';
import type {
	TrendItem,
	NewsItem,
	InsightResponse,
	ApiError,
	QuotaExceededError,
	CursorParams,
	BehaviorEvent
} from './types';

describe('API Types', () => {
	it('TrendItem shape is correct', () => {
		const trend: TrendItem = {
			id: '1',
			title: 'Test Trend',
			category: 'tech',
			summary: 'AI trend summary',
			score: 0.85,
			early_trend_score: 0.6,
			keywords: ['ai', 'ml'],
			created_at: '2024-01-01T00:00:00Z',
			article_count: 5,
			direction: 'steady'
		};
		expect(trend.id).toBe('1');
		expect(trend.keywords).toHaveLength(2);
		expect(trend.summary).toBe('AI trend summary');
		expect(trend.article_count).toBe(5);
	});

	it('NewsItem shape is correct', () => {
		const news: NewsItem = {
			id: '1',
			title: 'Test News',
			url: 'https://example.com',
			source: 'TestSource',
			publish_time: '2024-01-01T00:00:00Z',
			summary: 'A summary',
			article_count: 3
		};
		expect(news.source).toBe('TestSource');
		expect(news.summary).toBe('A summary');
	});

	it('NewsItem allows null fields', () => {
		const news: NewsItem = {
			id: '1',
			title: 'Test',
			url: 'https://example.com',
			source: null,
			publish_time: '2024-01-01T00:00:00Z',
			summary: null,
			article_count: 1
		};
		expect(news.source).toBeNull();
		expect(news.summary).toBeNull();
	});

	it('ApiError shape is correct', () => {
		const error: ApiError = {
			code: 'E0001',
			message: 'Something went wrong'
		};
		expect(error.code).toBe('E0001');
		expect(error.detail).toBeUndefined();
	});

	it('QuotaExceededError shape is correct', () => {
		const error: QuotaExceededError = {
			error_code: 'QUOTA_EXCEEDED',
			message_key: 'error.quota_exceeded',
			quota_type: 'daily_trends',
			limit: 10,
			reset_at: '2024-01-01T00:00:00Z',
			upgrade_url: '/pricing'
		};
		expect(error.error_code).toBe('QUOTA_EXCEEDED');
		expect(error.limit).toBe(10);
	});

	it('CursorParams shape is correct', () => {
		const params: CursorParams = { cursor: 'abc:123', limit: 20 };
		expect(params.cursor).toBe('abc:123');
		expect(params.limit).toBe(20);
	});

	it('CursorParams allows optional fields', () => {
		const params: CursorParams = {};
		expect(params.cursor).toBeUndefined();
		expect(params.limit).toBeUndefined();
	});

	it('BehaviorEvent shape is correct', () => {
		const event: BehaviorEvent = {
			event_type: 'click',
			payload: { target: 'button' },
			timestamp: '2024-01-01T00:00:00Z'
		};
		expect(event.event_type).toBe('click');
		expect(event.timestamp).toBeDefined();
	});

	it('InsightResponse with marketer content', () => {
		const insight: InsightResponse = {
			keyword: 'AI',
			role: 'marketer',
			locale: 'ko',
			content: {
				ad_opportunities: ['opportunity 1'],
				source_urls: ['https://example.com']
			},
			cached: false,
			degraded: false,
			generated_at: '2024-01-01T00:00:00Z'
		};
		expect(insight.role).toBe('marketer');
		expect('ad_opportunities' in insight.content).toBe(true);
	});
});
