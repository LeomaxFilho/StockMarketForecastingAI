"""
Bulk Article Scraper - Fetches thousands of articles from Google News.

Strategy:
1. Phase 1: Collect all article metadata/links from all dates using multiple queries
2. Phase 2: Extract article content in batch from all collected links
"""

import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from google_news import Google_news
from model import ArticleModel
from article_scraper import ArticleScraper, ArticleContent, save_articles

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)

# Multiple queries to maximize results per date
QUERIES = [
    'noticia',
    'brasil',
    'economia',
    'politica',
    'mercado',
    'governo',
    'empresa',
    'internacional',
]


@dataclass
class ArticleMetadata:
    """Metadata for an article before content extraction."""
    title: str
    link: str
    pub_date: str
    source_name: str
    source_url: str
    query: str
    search_date: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_article_model(cls, article: ArticleModel, query: str, search_date: str) -> 'ArticleMetadata':
        return cls(
            title=article.title,
            link=article.link,
            pub_date=article.pub_date.isoformat(),
            source_name=article.source['name'],
            source_url=article.source['url'],
            query=query,
            search_date=search_date,
        )


def load_dates(file_path: str) -> list[datetime]:
    """Load dates from JSON file."""
    with open(file_path, 'r') as f:
        dates_str = json.load(f)
    return [datetime.fromisoformat(d) for d in dates_str]


def save_metadata(articles: list[ArticleMetadata], file_path: str) -> None:
    """Save article metadata to JSON."""
    data = [a.to_dict() for a in articles]
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logging.info(f'Saved {len(articles)} metadata entries to {file_path}')


def load_metadata(file_path: str) -> list[ArticleMetadata]:
    """Load article metadata from JSON."""
    with open(file_path, 'r') as f:
        data = json.load(f)
    return [ArticleMetadata(**item) for item in data]


async def fetch_articles_for_date(date: datetime, queries: list[str]) -> list[ArticleMetadata]:
    """Fetch articles for a single date using multiple queries."""
    date_str = date.strftime('%Y-%m-%d')
    all_articles: list[ArticleMetadata] = []
    seen_links: set[str] = set()

    for query in queries:
        try:
            gn = Google_news(
                lang='pt-br',
                period=1,
                date=date,
                geolocalization='BR',
            )
            await gn.get_news(query=query)
            results = gn.get_results()

            for article in results:
                if article.link not in seen_links:
                    seen_links.add(article.link)
                    metadata = ArticleMetadata.from_article_model(article, query, date_str)
                    all_articles.append(metadata)

        except Exception as e:
            logging.error(f'Error fetching {query} for {date_str}: {e}')

    return all_articles


async def phase1_collect_metadata(
    dates: list[datetime],
    queries: list[str],
    output_file: str,
    max_concurrent: int = 5,
) -> list[ArticleMetadata]:
    """
    Phase 1: Collect all article metadata from all dates.
    """
    logging.info(f'=== PHASE 1: Collecting metadata for {len(dates)} dates ===')
    logging.info(f'Using {len(queries)} queries per date: {queries}')

    all_metadata: list[ArticleMetadata] = []
    seen_links: set[str] = set()
    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_date(date: datetime) -> list[ArticleMetadata]:
        async with semaphore:
            date_str = date.strftime('%Y-%m-%d')
            articles = await fetch_articles_for_date(date, queries)
            logging.info(f'  {date_str}: {len(articles)} unique articles')
            return articles

    tasks = [process_date(date) for date in dates]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, list):
            for article in result:
                if article.link not in seen_links:
                    seen_links.add(article.link)
                    all_metadata.append(article)
        elif isinstance(result, Exception):
            logging.error(f'Task failed: {result}')

    # Save metadata
    save_metadata(all_metadata, output_file)
    logging.info(f'=== PHASE 1 COMPLETE: {len(all_metadata)} unique articles collected ===')

    return all_metadata


def generate_report(
    metadata: list[ArticleMetadata],
    contents: list[ArticleContent],
    start_time: datetime,
    end_time: datetime,
) -> dict:
    """Generate extraction report."""
    from collections import Counter

    # Count by date
    dates_metadata = Counter(m.search_date for m in metadata)
    dates_extracted = Counter(
        c.pub_date[:10] if c.pub_date else 'unknown' for c in contents
    )

    # Count by source
    sources = Counter(c.source['name'] for c in contents)

    return {
        'summary': {
            'total_metadata': len(metadata),
            'total_extracted': len(contents),
            'success_rate': f'{len(contents) / len(metadata) * 100:.1f}%',
            'extraction_time': str(end_time - start_time),
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
        },
        'by_date': {
            'metadata_count': dict(sorted(dates_metadata.items())),
            'extracted_count': dict(sorted(dates_extracted.items())),
        },
        'by_source': dict(sources.most_common(50)),
        'queries_used': list(set(m.query for m in metadata)),
    }


async def phase2_extract_content(
    metadata_file: str,
    output_file: str,
    report_file: str,
    max_concurrent: int = 10,
    batch_size: int = 50,
) -> list[ArticleContent]:
    """
    Phase 2: Extract content from all collected articles.
    Saves only one final file and a report.
    """
    metadata = load_metadata(metadata_file)
    logging.info(f'=== PHASE 2: Extracting content from {len(metadata)} articles ===')

    start_time = datetime.now()
    all_contents: list[ArticleContent] = []
    failed_count = 0

    # Process in batches
    total_batches = (len(metadata) + batch_size - 1) // batch_size

    async with ArticleScraper(max_concurrent=max_concurrent, headless=True) as scraper:
        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(metadata))
            batch = metadata[start_idx:end_idx]

            logging.info(f'Processing batch {batch_num + 1}/{total_batches} ({len(batch)} articles) - Total extracted: {len(all_contents)}')

            # Convert metadata to ArticleModel for scraper
            articles = []
            for m in batch:
                try:
                    article = ArticleModel(
                        title=m.title,
                        link=m.link,
                        pub_date=datetime.fromisoformat(m.pub_date).strftime('%a, %d %b %Y %H:%M:%S GMT'),
                        source_name=m.source_name,
                        source_url=m.source_url,
                    )
                    articles.append(article)
                except Exception as e:
                    logging.warning(f'Skipping invalid metadata: {e}')
                    failed_count += 1

            # Fetch content
            contents = await scraper.fetch_articles(articles)
            all_contents.extend(contents)
            failed_count += len(articles) - len(contents)

    end_time = datetime.now()

    # Save final file
    save_articles(all_contents, output_file)
    logging.info(f'Saved {len(all_contents)} articles to {output_file}')

    # Generate and save report
    report = generate_report(metadata, all_contents, start_time, end_time)
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    logging.info(f'Saved report to {report_file}')

    logging.info(f'=== PHASE 2 COMPLETE: {len(all_contents)} articles extracted ({failed_count} failed) ===')

    return all_contents


async def main():
    """Main entry point - runs both phases."""
    # Configuration
    dates_file = Path(__file__).parent / 'PETR4.SA_date.json'
    metadata_file = Path(__file__).parent / 'articles_metadata.json'
    output_file = Path(__file__).parent / 'articles.json'
    report_file = Path(__file__).parent / 'extraction_report.json'

    # Load dates
    dates = load_dates(str(dates_file))
    logging.info(f'Loaded {len(dates)} dates from {dates_file}')

    # Phase 1: Collect metadata (skip if file already exists)
    if metadata_file.exists():
        metadata = load_metadata(str(metadata_file))
        logging.info(f'Skipping Phase 1 - metadata file already exists with {len(metadata)} articles')
    else:
        metadata = await phase1_collect_metadata(
            dates=dates,
            queries=QUERIES,
            output_file=str(metadata_file),
            max_concurrent=5,
        )

    if len(metadata) < 100:
        logging.warning(f'Only {len(metadata)} articles found. Consider adding more queries.')

    # Phase 2: Extract content
    await phase2_extract_content(
        metadata_file=str(metadata_file),
        output_file=str(output_file),
        report_file=str(report_file),
        max_concurrent=10,
        batch_size=50,
    )


if __name__ == '__main__':
    asyncio.run(main())
