import asyncio
import json
import logging
import random
import re
from datetime import datetime
from typing import Any, override

import aiohttp

semaphore = asyncio.Semaphore(5)

META_REFRESH_RE = re.compile(r'url=(https?://[^"\'>]+)', re.IGNORECASE)


class ArticleModel:
    def __init__(self, title: str, link: str, pub_date: str, source_name: str, source_url: str):
        self.title: str = title
        self.link: str = link
        self.pub_date: datetime = datetime.strptime(pub_date, '%a, %d %b %Y %H:%M:%S GMT')
        self.source: dict[str, str] = {'name': source_name, 'url': source_url}

    @override
    def __str__(self):
        return f'Title: {self.title}\nURL: {self.link}\nDate: {self.pub_date}\nSource: {self.source["name"]}'

    def to_json(self) -> dict[str, Any]:
        return {'title': self.title, 'link': self.link, 'pub_date': self.pub_date.isoformat(), 'source': self.source}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'ArticleModel':
        """
        Alternate constructor: create an ArticleModel from a dict (e.g. loaded from JSON).
        Expects 'pub_date' in ISO format like 'YYYY-MM-DDTHH:MM:SS'. Falls back to other known formats.
        """

        instance = cls.__new__(cls)

        instance.title = data['title']
        instance.link = data['link']
        instance.pub_date = datetime.strptime(data['pub_date'], '%Y-%m-%dT%H:%M:%S')
        instance.source = data['source']

        return instance

    async def resolve_url(self, session: aiohttp.ClientSession) -> str:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
        }

        async with semaphore:
            await asyncio.sleep(random.uniform(0.3, 0.9))

            try:
                async with session.get(
                    self.link, headers=headers, allow_redirects=False, timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    url = str(response.url)

                    return url

            except Exception as e:
                logging.error(f'Error fetching content: {e}')

                return 'Error'


def save_to_json(articles: list[ArticleModel], file_name: str):
    data = [article.to_json() for article in articles]

    try:
        with open(file_name, 'w') as file:
            json.dump(data, file, indent=4, ensure_ascii=False)

    except Exception as e:
        logging.error(f'Error saving JSON: {e}')
        return False

    return True


def load_from_json(file_name: str) -> list[ArticleModel]:
    try:
        with open(file_name, 'r') as file:
            data: list[dict[str, Any]] = json.load(file)
            return [ArticleModel.from_dict(article) for article in data]

    except Exception as e:
        logging.error(f'Error loading JSON: {e}')
        return []
