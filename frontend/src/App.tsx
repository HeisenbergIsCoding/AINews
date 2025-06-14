import React, { useEffect, useState } from "react";
import Header, { ThemeProvider, LanguageProvider, useLanguage } from "./components/Header";
import { getArticles, refreshArticles, Article } from "./api";

// 主要內容組件
function MainContent() {
  const [articles, setArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh] = useState<boolean>(true); // 永遠保持開啟，移除 setAutoRefresh
  const [lastRefreshTime, setLastRefreshTime] = useState<Date | null>(null);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const { t, language } = useLanguage();

  // 根據當前語系選擇正確的標題和內容
  const getLocalizedContent = (article: Article) => {
    let title: string;
    let content: string;
    
    // 根據語言選擇對應的標題和內容
    switch (language) {
      case 'zh-TW':
        title = article.title_zh_tw || article.title;
        content = article.content_zh_tw || article.summary;
        break;
      case 'zh-CN':
        title = article.title_zh_cn || article.title;
        content = article.content_zh_cn || article.summary;
        break;
      case 'en':
      default:
        title = article.title_en || article.title;
        content = article.content_en || article.summary;
        break;
    }
    
    return { title, content };
  };

  const loadArticles = async (skipRefresh: boolean = false) => {
    try {
      setLoading(true);
      setError(null);
      
      if (!skipRefresh) {
        // 先呼叫後端 /refresh 端點，讓伺服器抓取最新 RSS
        const refreshResult = await refreshArticles();
        if (!refreshResult.success) {
          console.warn('刷新失敗，但繼續載入現有文章:', refreshResult.error);
        }
      }
      
      // 獲取文章列表
      const articlesResult = await getArticles();
      if (!articlesResult.success) {
        throw new Error(articlesResult.error || '無法載入文章');
      }
      
      setArticles(articlesResult.data?.articles || []);
      setLastRefreshTime(new Date());
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '載入文章時發生未知錯誤';
      setError(errorMessage);
      console.error('載入文章錯誤:', err);
    } finally {
      setLoading(false);
    }
  };

  const autoRefreshArticles = async () => {
    try {
      setRefreshing(true);
      setError(null);
      
      // 自動刷新時只獲取文章，不觸發RSS抓取（由後端調度器處理）
      const articlesResult = await getArticles();
      if (!articlesResult.success) {
        throw new Error(articlesResult.error || '無法載入文章');
      }
      
      setArticles(articlesResult.data?.articles || []);
      setLastRefreshTime(new Date());
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '自動刷新時發生未知錯誤';
      setError(errorMessage);
      console.error('自動刷新錯誤:', err);
    } finally {
      setRefreshing(false);
    }
  };


  // 初始載入
  useEffect(() => {
    loadArticles();
  }, []);

  // 自動刷新效果
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      autoRefreshArticles();
    }, 10 * 60 * 1000); // 10分鐘

    return () => clearInterval(interval);
  }, [autoRefresh]);

  return (
    <main style={{ padding: "2rem", fontFamily: "system-ui, sans-serif", minHeight: "calc(100vh - 80px)" }}>
      <div style={{ maxWidth: "1200px", margin: "0 auto" }}>
        {/* 狀態顯示區域 */}
        <div style={{
          marginBottom: "2rem",
          display: "flex",
          gap: "1rem",
          alignItems: "center",
          flexWrap: "wrap"
        }}>
          {refreshing && (
            <span style={{
              color: "var(--text-secondary, #4a5568)",
              fontSize: "0.875rem",
              display: "flex",
              alignItems: "center",
              gap: "0.5rem"
            }}>
              <span style={{
                display: "inline-block",
                width: "12px",
                height: "12px",
                border: "2px solid #ccc",
                borderTop: "2px solid #007bff",
                borderRadius: "50%",
                animation: "spin 1s linear infinite"
              }}></span>
              {language === 'zh-TW' ? '自動更新中...' :
               language === 'zh-CN' ? '自动更新中...' : 'Auto updating...'}
            </span>
          )}
          
          {lastRefreshTime && (
            <span style={{
              color: "var(--text-secondary, #4a5568)",
              fontSize: "0.875rem"
            }}>
              {language === 'zh-TW' ? '最後更新：' :
               language === 'zh-CN' ? '最后更新：' : 'Last updated: '}
              {lastRefreshTime.toLocaleTimeString()}
            </span>
          )}
        </div>
        
        {error && (
          <div style={{
            color: "var(--error-color, #e53e3e)",
            marginBottom: "1rem",
            padding: "1rem",
            backgroundColor: "var(--error-bg, #fed7d7)",
            border: "1px solid var(--error-border, #feb2b2)",
            borderRadius: "4px"
          }}>
            <strong>{t('error')}:</strong> {error}
          </div>
        )}
        
        {articles.length === 0 && !loading && !error && (
          <div style={{
            textAlign: "center",
            padding: "2rem",
            color: "var(--text-secondary, #4a5568)"
          }}>
            {language === 'zh-TW' ? '目前沒有文章' :
             language === 'zh-CN' ? '目前没有文章' : 'No articles available'}
          </div>
        )}
        <div style={{ display: "grid", gap: "1.5rem" }}>
          {articles.map((article) => {
            const { title, content } = getLocalizedContent(article);
            return (
              <article
                key={article.link}
                style={{
                  padding: "1.5rem",
                  border: "1px solid var(--border-color, #e2e8f0)",
                  borderRadius: "8px",
                  background: "var(--card-bg, #ffffff)",
                  boxShadow: "0 1px 3px rgba(0, 0, 0, 0.1)"
                }}
              >
                <a href={article.link} target="_blank" rel="noreferrer">
                  <h3 style={{
                    margin: "0 0 0.5rem",
                    fontSize: "1.25rem",
                    lineHeight: "1.4",
                    color: "var(--text-primary, #1a202c)"
                  }}>
                    {title}
                  </h3>
                </a>
                <small style={{
                  color: "var(--text-secondary, #4a5568)",
                  fontSize: "0.875rem"
                }}>
                  {new Date(article.published).toLocaleString()}
                </small>
                <p style={{
                  margin: "0.75rem 0 0",
                  lineHeight: "1.6",
                  color: "var(--text-primary, #1a202c)"
                }}>
                  {content}
                </p>
                {/* 顯示原始語言標記（如果有翻譯內容） */}
                {article.original_language && (
                  <div style={{
                    marginTop: "0.5rem",
                    fontSize: "0.75rem",
                    color: "var(--text-secondary, #4a5568)",
                    opacity: 0.7
                  }}>
                    {t('originalLanguage')}: {article.original_language}
                  </div>
                )}
              </article>
            );
          })}
        </div>
      </div>
    </main>
  );
}

// 主應用組件
export default function App() {
  return (
    <ThemeProvider>
      <LanguageProvider>
        <div style={{ minHeight: "100vh" }}>
          <Header />
          <MainContent />
        </div>
      </LanguageProvider>
    </ThemeProvider>
  );
}
