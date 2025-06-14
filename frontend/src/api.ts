/**
 * API 呼叫工具函數，包含完整的錯誤處理
 */

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
}

export interface Article {
  link: string;
  title: string;
  title_zh_tw?: string;
  title_en?: string;
  title_zh_cn?: string;
  published: string;
  summary: string;
  content_zh_tw?: string;
  content_en?: string;
  content_zh_cn?: string;
  feed_source?: string;
  original_language?: string;
}

export interface ArticlesResponse {
  articles: Article[];
}

export interface RefreshResponse {
  detail: string;
  new_articles?: number;
  total_articles?: number;
}

/**
 * 通用的 fetch 包裝函數
 */
async function apiCall<T>(url: string, options?: RequestInit): Promise<ApiResponse<T>> {
  try {
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      ...options,
    });

    if (!response.ok) {
      const errorText = await response.text();
      return {
        success: false,
        error: `HTTP ${response.status}: ${errorText || response.statusText}`,
      };
    }

    const data = await response.json();
    return {
      success: true,
      data,
    };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : '未知錯誤',
    };
  }
}

/**
 * 獲取文章列表
 */
export async function getArticles(limit?: number): Promise<ApiResponse<ArticlesResponse>> {
  const url = limit ? `/api/articles?limit=${limit}` : '/api/articles';
  return apiCall<ArticlesResponse>(url);
}

/**
 * 手動刷新文章
 */
export async function refreshArticles(): Promise<ApiResponse<RefreshResponse>> {
  return apiCall<RefreshResponse>('/api/refresh', { method: 'POST' });
}

/**
 * 快速刷新文章（不翻譯）
 */
export async function refreshArticlesFast(): Promise<ApiResponse<RefreshResponse>> {
  return apiCall<RefreshResponse>('/api/refresh-fast', { method: 'POST' });
}

/**
 * 翻譯特定文章
 */
export async function translateArticle(articleUrl: string): Promise<ApiResponse<any>> {
  return apiCall(`/api/translate/${encodeURIComponent(articleUrl)}`, { method: 'POST' });
}

/**
 * 獲取翻譯統計
 */
export async function getTranslationStats(): Promise<ApiResponse<any>> {
  return apiCall('/api/translation-stats');
}

/**
 * 健康檢查
 */
export async function healthCheck(): Promise<ApiResponse<any>> {
  return apiCall('/api/health');
}

// 向後相容的簡單 get 函數
export async function get<T>(url: string): Promise<T> {
  const result = await apiCall<T>(url);
  if (!result.success) {
    throw new Error(result.error || '請求失敗');
  }
  return result.data!;
}