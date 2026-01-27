"""
Article Scraper using Playwright for content extraction from Google News links.

This module fetches article content from Google News RSS links using Playwright
for better handling of dynamic content and JavaScript-rendered pages.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeout

from google_news import Google_news
from model import ArticleModel

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


@dataclass
class ArticleContent:
    """Represents the extracted content from an article."""
    title: str
    content: str
    url: str
    original_url: str
    pub_date: str
    source: dict[str, str]
    fetch_date: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            'title': self.title,
            'content': self.content,
            'url': self.url,
            'original_url': self.original_url,
            'pub_date': self.pub_date,
            'source': self.source,
            'fetch_date': self.fetch_date,
        }


class ArticleScraper:
    """Scrapes article content using Playwright for robust JS handling."""

    # Selectors for article content (in priority order)
    CONTENT_SELECTORS = [
        '[itemprop="articleBody"]',
        'article .content',
        'article .text',
        '.article-body',
        '.article-content',
        '.post-content',
        '.entry-content',
        '.content-text',
        '.materia-conteudo',
        '.mc-article-body',
        '#article-body',
        '.story-body',
        '.news-content',
        '.texto',
        '.noticia-conteudo',
        'article p',
    ]

    # Elements to remove before extracting content
    REMOVE_SELECTORS = [
        'nav', 'header', 'footer', 'aside',
        '.nav', '.navbar', '.menu', '.sidebar',
        '.header', '.footer', '.advertisement', '.ad',
        '.social-share', '.share-buttons', '.related-articles',
        '.comments', '.comment-section', '#comments',
        '.newsletter', '.subscription', '.signup',
        '.breadcrumb', '.tags', '.tag-list',
        'script', 'style', 'noscript', 'iframe',
        '.mais-lidas', '.most-read', '.trending',
        '.recomendados', '.recommended', '.relacionadas',
        'figure', 'figcaption',
    ]

    def __init__(
        self,
        max_concurrent: int = 5,
        timeout: int = 15000,
        headless: bool = True,
    ):
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.headless = headless
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._browser: Browser | None = None

    async def __aenter__(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.headless)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._browser:
            await self._browser.close()
        await self._playwright.stop()

    async def _resolve_google_news_url(self, page: Page, url: str) -> str:
        """Resolve Google News redirect URL to the actual article URL."""
        try:
            await page.goto(url, wait_until='domcontentloaded', timeout=self.timeout)

            # Wait for redirect - Google News uses JS redirects
            for _ in range(10):
                await page.wait_for_timeout(500)
                current_url = page.url
                # Check if we left Google News domain
                if 'news.google.com' not in current_url:
                    return current_url

            # Try clicking through consent/continue buttons if present
            try:
                continue_btn = await page.query_selector('a[href*="articles"], button:has-text("Continue")')
                if continue_btn:
                    await continue_btn.click()
                    await page.wait_for_timeout(2000)
                    if 'news.google.com' not in page.url:
                        return page.url
            except Exception:
                pass

            return page.url
        except PlaywrightTimeout:
            logging.warning(f'Timeout resolving URL: {url}')
            return url
        except Exception as e:
            logging.error(f'Error resolving URL {url}: {e}')
            return url

    async def _remove_unwanted_elements(self, page: Page) -> None:
        """Remove navigation, ads, and other non-content elements."""
        for selector in self.REMOVE_SELECTORS:
            try:
                await page.evaluate(f'''
                    document.querySelectorAll('{selector}').forEach(el => el.remove());
                ''')
            except Exception:
                continue

    async def _clean_text(self, text: str) -> str:
        """Clean extracted text by removing extra whitespace and common junk."""
        import re

        # Remove multiple newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Remove multiple spaces
        text = re.sub(r' {2,}', ' ', text)
        # Remove common junk patterns
        junk_patterns = [
            r'Continua depois da publicidade',
            r'Leia também:?',
            r'Leia mais:?',
            r'LEIA MAIS:?',
            r'Publicidade',
            r'Assine a newsletter',
            r'Receba .* no seu e-?mail',
            r'Compartilh[ae]r?:?',
            r'Tweet',
            r'WhatsApp',
            r'Telegram',
            r'Facebook',
            r'Ver todos indicadores',
            r'Tags\n',
            r'Notícias Relacionadas',
            r'NOTÍCIAS RELACIONADAS',
            r'VER MAIS',
            r'VER TODAS',
            r'Mais lidas',
            r'MAIS LIDAS',
            r'Últimas notícias',
            r'ÚLTIMAS NOTÍCIAS',
        ]
        for pattern in junk_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)

        return text.strip()

    async def _extract_paragraphs(self, page: Page) -> str:
        """Extract only paragraph text from the page."""
        try:
            paragraphs = await page.evaluate('''
                () => {
                    const article = document.querySelector('article') || document.querySelector('main') || document.body;
                    const paragraphs = article.querySelectorAll('p');
                    let text = [];
                    paragraphs.forEach(p => {
                        const content = p.innerText.trim();
                        if (content.length > 50) {
                            text.push(content);
                        }
                    });
                    return text.join('\\n\\n');
                }
            ''')
            return paragraphs if paragraphs else ''
        except Exception:
            return ''

    async def _extract_content(self, page: Page) -> str:
        """Extract article content using multiple selectors."""
        # First, remove unwanted elements
        await self._remove_unwanted_elements(page)

        # Try specific content selectors
        for selector in self.CONTENT_SELECTORS:
            try:
                element = await page.query_selector(selector)
                if element:
                    text = await element.inner_text()
                    if text and len(text.strip()) > 200:
                        return await self._clean_text(text)
            except Exception:
                continue

        # Try extracting only paragraphs
        paragraphs = await self._extract_paragraphs(page)
        if paragraphs and len(paragraphs) > 200:
            return await self._clean_text(paragraphs)

        # Fallback: get article or main text
        try:
            for fallback in ['article', 'main', '[role="main"]']:
                element = await page.query_selector(fallback)
                if element:
                    text = await element.inner_text()
                    if text and len(text.strip()) > 200:
                        return await self._clean_text(text)
        except Exception:
            pass

        return ''

    async def _extract_title(self, page: Page) -> str:
        """Extract article title."""
        title_selectors = ['h1', 'title', '[itemprop="headline"]', '.article-title']
        for selector in title_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    text = await element.inner_text()
                    if text and len(text.strip()) > 5:
                        return text.strip()
            except Exception:
                continue
        return ''

    async def fetch_article(self, article: ArticleModel) -> ArticleContent | None:
        """Fetch and extract content from a single article."""
        async with self._semaphore:
            if not self._browser:
                raise RuntimeError('Browser not initialized. Use async context manager.')

            context = await self._browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = await context.new_page()

            try:
                # Resolve Google News URL
                resolved_url = await self._resolve_google_news_url(page, article.link)

                # Navigate to actual article
                if resolved_url != article.link:
                    try:
                        await page.goto(resolved_url, wait_until='domcontentloaded', timeout=self.timeout)
                    except PlaywrightTimeout:
                        logging.warning(f'Timeout loading article: {resolved_url}')

                await page.wait_for_timeout(500)

                # Extract content
                content = await self._extract_content(page)
                title = await self._extract_title(page) or article.title

                if not content:
                    logging.warning(f'No content extracted from: {resolved_url}')
                    return None

                return ArticleContent(
                    title=title,
                    content=content,
                    url=resolved_url,
                    original_url=article.link,
                    pub_date=article.pub_date.isoformat(),
                    source=article.source,
                )

            except Exception as e:
                logging.error(f'Error fetching article {article.link}: {e}')
                return None

            finally:
                await context.close()

    async def fetch_articles(self, articles: list[ArticleModel]) -> list[ArticleContent]:
        """Fetch content from multiple articles concurrently."""
        tasks = [self.fetch_article(article) for article in articles]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        contents = []
        for result in results:
            if isinstance(result, ArticleContent):
                contents.append(result)
            elif isinstance(result, Exception):
                logging.error(f'Task failed: {result}')

        return contents


def load_dates(file_path: str) -> list[datetime]:
    """Load dates from JSON file."""
    try:
        with open(file_path, 'r') as f:
            dates_str = json.load(f)
        return [datetime.fromisoformat(d) for d in dates_str]
    except Exception as e:
        logging.error(f'Error loading dates: {e}')
        return []


def save_articles(articles: list[ArticleContent], file_path: str) -> bool:
    """Save articles to JSON file."""
    try:
        data = [article.to_dict() for article in articles]
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logging.error(f'Error saving articles: {e}')
        return False


async def fetch_news_for_date(
    date: datetime,
    query: str,
    scraper: ArticleScraper,
    max_articles: int = 10,
) -> list[ArticleContent]:
    """Fetch news articles for a specific date."""
    logging.info(f'Fetching news for date: {date.strftime("%Y-%m-%d")}')

    google_news = Google_news(
        lang='pt-br',
        period=1,
        date=date,
        geolocalization='BR',
        max_results=max_articles,
    )

    try:
        await google_news.get_news(query=query)
        articles = google_news.get_results()[:max_articles]

        if not articles:
            logging.info(f'No articles found for date: {date.strftime("%Y-%m-%d")}')
            return []

        logging.info(f'Found {len(articles)} articles for {date.strftime("%Y-%m-%d")}')
        contents = await scraper.fetch_articles(articles)
        logging.info(f'Successfully fetched {len(contents)} article contents')

        return contents

    except Exception as e:
        logging.error(f'Error fetching news for {date}: {e}')
        return []


async def fetch_news_for_dates(
    dates: list[datetime],
    query: str,
    output_dir: str = 'articles',
    max_articles_per_date: int = 10,
    max_concurrent_dates: int = 3,
) -> dict[str, list[ArticleContent]]:
    """Fetch news articles for multiple dates."""
    Path(output_dir).mkdir(exist_ok=True)

    all_results: dict[str, list[ArticleContent]] = {}
    date_semaphore = asyncio.Semaphore(max_concurrent_dates)

    async def process_date(date: datetime, scraper: ArticleScraper) -> tuple[str, list[ArticleContent]]:
        async with date_semaphore:
            date_str = date.strftime('%Y-%m-%d')
            contents = await fetch_news_for_date(date, query, scraper, max_articles_per_date)

            if contents:
                file_path = Path(output_dir) / f'{query.replace(" ", "_")}_{date_str}.json'
                save_articles(contents, str(file_path))
                logging.info(f'Saved {len(contents)} articles to {file_path}')

            return date_str, contents

    async with ArticleScraper(max_concurrent=5, headless=True) as scraper:
        tasks = [process_date(date, scraper) for date in dates]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, tuple):
                date_str, contents = result
                all_results[date_str] = contents
            elif isinstance(result, Exception):
                logging.error(f'Date processing failed: {result}')

    return all_results


async def main():
    """Main entry point for the article scraper."""
    # Load dates from JSON
    dates_file = Path(__file__).parent / 'PETR4.SA_date.json'
    dates = load_dates(str(dates_file))

    if not dates:
        logging.error('No dates loaded. Exiting.')
        return

    logging.info(f'Loaded {len(dates)} dates')

    # Fetch news for all dates - using generic query without bias
    query = 'noticia'
    results = await fetch_news_for_dates(
        dates=dates,
        query=query,
        output_dir='articles',
        max_articles_per_date=20,
        max_concurrent_dates=2,
    )

    # Save consolidated results
    all_articles = []
    for date_str, articles in results.items():
        all_articles.extend(articles)

    if all_articles:
        consolidated_file = Path(__file__).parent / 'articles' / 'all_articles.json'
        save_articles(all_articles, str(consolidated_file))
        logging.info(f'Total articles fetched: {len(all_articles)}')
    else:
        logging.warning('No articles were fetched.')


if __name__ == '__main__':
    asyncio.run(main())
