"""News data pipeline: orchestrate search and download of news articles.

This module composes lower-level helpers to perform Google Custom Search
queries and concurrently download the resulting pages. It uses functions
from `news.utils.functions` (for example `fetch_search` and `fetch_news`)
to create two output artifacts:

- `data/news.json` : the raw JSON responses returned by the Custom Search API.
- `data/articles.json` : a list of article records with extracted fields
  such as `header`, `content`, and `url`. Failed downloads are represented
  by placeholder values (for example the string `'Error'`).

Configuration
- The calling environment must provide Google Custom Search credentials:
  - API key: environment variable `API_CUSTOM_SEARCH`
  - Custom Search Engine ID: environment variable `CUSTOM_SEARCH_ID`

Usage
- The module exposes an `async def main()` coroutine which demonstrates the
  orchestration and writes the two JSON files under a relative `data/` folder.
  The module can be executed as a script, or its helper functions can be
  imported and reused in other pipelines.

Notes
- This module writes files to disk using relative paths. Adjust file paths or
  refactor to return in-memory objects if you need different integration or
  testing behavior.
"""

import asyncio
import os

from dotenv import load_dotenv
from utils.functions import (
    fetch_news,
    fetch_search,
    save_json,
    soup_articles,
)


async def main():
    _ = load_dotenv()

    API_CUSTOM_SEARCH = os.getenv('API_CUSTOM_SEARCH')
    URL_CUSTOM_SEARCH = 'https://customsearch.googleapis.com/customsearch/v1'
    CX_CUSTOM_SEARCH = os.getenv('CUSTOM_SEARCH_ID')
    # API_CHAT_GPT = f'Bearer {os.getenv("API_CHAT_GPT")}'
    # URL_CHAT_GPT = 'https://api.openai.com/v1/chat/completions'
    # MODEL_CHAT_GTP = 'gpt-5-nano'

    # header = {'Authorization': API_CHAT_GPT}
    # payload = {
    #     'model': MODEL_CHAT_GTP,
    #     'messages': [
    #         {
    #             'role': 'system',
    #             'content': 'voce deve me responder apenas com 0 e 1, com base em se a notícia pode ter alguma nas ações do mercado financeiro brasileiro',
    #         },
    #         {'role': 'user', 'content': 'qual o seu modelo?'},
    #     ],
    # }
    query_list = [
        'Petrobras',
        'Petróleo',
        'Dólar',
        'Guerra',
        'China',
        'Geopolítica',
        'Estoques',
        'Juros',
        'Refino',
    ]
    data: list[str] = []
    urls: list[str] = []

    for query in query_list:
        async for data_pag, urls_pag in fetch_search(API_CUSTOM_SEARCH, URL_CUSTOM_SEARCH, CX_CUSTOM_SEARCH, query):
            data.append(data_pag)
            urls.extend(urls_pag)

    save_json('data/news.json', data)

    articles = await fetch_news(urls)
    articles = [soup_articles(article) for article in articles]

    save_json('data/articles.json', articles)


if __name__ == '__main__':
    asyncio.run(main())
