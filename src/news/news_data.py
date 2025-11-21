"""News data pipeline: search and download articles.

This module orchestrates a Google Custom Search query and concurrently
downloads the pages returned by that search. It delegates the actual
HTTP and concurrency work to `fetch_search` and `fetch_news` in
``utils.functions``.

Environment variables
- ``APICUSTOMSEARCH`` : Google Custom Search API key.
- ``CUSTOM_SEARCH_ID`` : Custom Search Engine ID (cx).

Outputs
- ``data/news.json`` : raw JSON response from the Custom Search API.
- ``data/articles.json`` : list with the raw HTML/text of the fetched pages;
    failed downloads are represented by the string ``'Error'``.
"""

import os
import json
import asyncio
from dotenv import load_dotenv
from utils.functions import (
        fetch_news, fetch_search
)

if __name__ == '__main__':
    load_dotenv()

    APICUSTOMSEARCH = os.getenv('APICUSTOMSEARCH')
    URLCUSTOMSEARCH = 'https://customsearch.googleapis.com/customsearch/v1'
    CXCUSTOMSEARCH = os.getenv('CUSTOM_SEARCH_ID')

    data, urls = fetch_search(
        APICUSTOMSEARCH, URLCUSTOMSEARCH, CXCUSTOMSEARCH, 'data/news.json'
    )

    articles = asyncio.run(fetch_news(urls))
    #articles = [soup_articles(article) for article in articles]

    with open('data/articles.json', 'w', encoding='utf-8') as file:
        json.dump(articles, file, indent= 4, ensure_ascii= False)
