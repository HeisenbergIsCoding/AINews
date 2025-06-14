import React, { createContext, useContext, useState, useEffect } from 'react';
import './Header.css';

// 主題類型定義
type Theme = 'light' | 'dark';
type Language = 'zh-TW' | 'en' | 'zh-CN';

// 主題上下文
interface ThemeContextType {
  theme: Theme;
  toggleTheme: () => void;
}

// 語言上下文
interface LanguageContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  toggleLanguage: () => void;
  t: (key: string) => string;
}

// 翻譯字典
const translations = {
  'zh-TW': {
    title: 'AI Daily News',
    toggleTheme: '切換主題',
    toggleLanguage: '切換語言',
    refresh: '重新整理',
    loading: '載入中...',
    error: '錯誤',
    originalLanguage: '原始語言',
  },
  'en': {
    title: 'AI Daily News',
    toggleTheme: 'Toggle Theme',
    toggleLanguage: 'Toggle Language',
    refresh: 'Refresh',
    loading: 'Loading...',
    error: 'Error',
    originalLanguage: 'Original',
  },
  'zh-CN': {
    title: 'AI Daily News',
    toggleTheme: '切换主题',
    toggleLanguage: '切换语言',
    refresh: '刷新',
    loading: '加载中...',
    error: '错误',
    originalLanguage: '原始语言',
  }
};

// 創建上下文
export const ThemeContext = createContext<ThemeContextType | undefined>(undefined);
export const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

// 自定義 hooks
export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};

export const useLanguage = () => {
  const context = useContext(LanguageContext);
  if (context === undefined) {
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
};

// 主題提供者
export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = localStorage.getItem('theme');
    return (saved as Theme) || 'light';
  });

  const toggleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light');
  };

  useEffect(() => {
    localStorage.setItem('theme', theme);
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};

// 語言提供者
export const LanguageProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [language, setLanguage] = useState<Language>(() => {
    const saved = localStorage.getItem('language');
    return (saved as Language) || 'zh-TW';
  });

  const toggleLanguage = () => {
    setLanguage(prev => {
      switch (prev) {
        case 'zh-TW': return 'en';
        case 'en': return 'zh-CN';
        case 'zh-CN': return 'zh-TW';
        default: return 'zh-TW';
      }
    });
  };

  const t = (key: string): string => {
    return translations[language][key as keyof typeof translations['zh-TW']] || key;
  };

  useEffect(() => {
    localStorage.setItem('language', language);
  }, [language]);

  return (
    <LanguageContext.Provider value={{ language, setLanguage, toggleLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  );
};

// Header 組件
const Header: React.FC = () => {
  const { theme, toggleTheme } = useTheme();
  const { language, toggleLanguage, t } = useLanguage();

  const getLanguageDisplay = () => {
    switch (language) {
      case 'zh-TW': return '繁';
      case 'zh-CN': return '简';
      case 'en': return 'EN';
      default: return 'EN';
    }
  };

  const getThemeText = () => {
    const isDark = theme === 'dark';
    switch (language) {
      case 'zh-TW': return isDark ? '淺色' : '深色';
      case 'zh-CN': return isDark ? '浅色' : '深色';
      case 'en': return isDark ? 'Light' : 'Dark';
      default: return isDark ? 'Light' : 'Dark';
    }
  };

  return (
    <header className="header">
      <div className="header-container">
        <h1 className="header-title">{t('title')}</h1>
        
        <div className="header-controls">
          {/* 語言切換按鈕 */}
          <button
            className="control-button language-button"
            onClick={toggleLanguage}
            title={t('toggleLanguage')}
            aria-label={t('toggleLanguage')}
          >
            <span className="button-icon">🌐</span>
            <span className="button-text">{getLanguageDisplay()}</span>
          </button>

          {/* 主題切換按鈕 */}
          <button
            className="control-button theme-button"
            onClick={toggleTheme}
            title={t('toggleTheme')}
            aria-label={t('toggleTheme')}
          >
            <span className="button-icon">
              {theme === 'light' ? '🌙' : '☀️'}
            </span>
            <span className="button-text">
              {getThemeText()}
            </span>
          </button>
        </div>
      </div>
    </header>
  );
};

export default Header;