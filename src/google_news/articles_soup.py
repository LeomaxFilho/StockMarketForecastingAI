import asyncio
import json

import aiohttp
from bs4 import BeautifulSoup
from model import ArticleModel, load_from_json

# from google_news import Google_news


async def articles_html(articles: list[ArticleModel]) -> list[str]:
    results = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    async with aiohttp.ClientSession() as session:
        for article in articles:
            link = article.link

            async with session.get(link, headers=headers) as response:
                if response.status == 200:
                    text = await response.text(encoding='utf-8')

                    results.append(text)
                else:
                    results.append(f'Error: {response.status}')

    return results


def soup(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, 'html.parser')
    return soup.text


def json_save(articles: list[str]):
    with open('news_html.json', 'w') as f:
        json.dump([article for article in articles], f)


if __name__ == '__main__':

    async def main():
        articles: list[ArticleModel] = load_from_json('news.json')

        connector = aiohttp.TCPConnector(limit=20, limit_per_host=2)

        async with aiohttp.ClientSession(connector=connector) as session:
            links = await asyncio.gather(*[article.resolve_url(session) for article in articles])

        json_save(links)

    asyncio.run(main())
