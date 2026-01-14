import asyncio
import json
import logging
from datetime import datetime, timedelta

import aiohttp
from bs4 import BeautifulSoup
from model import ArticleModel, save_to_json

TIMEOUT_MAX = aiohttp.ClientTimeout(total=10)


class Google_news:
    def __init__(
        self,
        lang: str = 'pt-br',
        period: int = 1,
        date: str | datetime | None = None,
        *,
        encode: str = 'utf-8',
        geolocalization: str = 'BR',
        max_results: int = 100,
    ) -> None:
        """
        Initialize a Google_news instance and document the class methods.

        Parameters
        ----------
        lang : str, optional
            Language code used for news searches (default: 'pt').
        period : int, optional
            Number of days from `date` to include when fetching news (default: 1).
        date : str | datetime | None, optional
            Initial date for news queries. Accepts an ISO 8601 string or a datetime object.
            If None, the current datetime is used.
        encode : str, optional
            Text encoding to use when processing responses (default: 'utf-8').
        geolocalization : str, optional
            Geolocalization code for news searches (default: 'BR').
        Notes
        -----
        The Google_news class provides the following methods:

        - __user_agent(self) -> str
            Read-only property that returns the default User-Agent header string.

        - set_lang(self, lang: str) -> None
            Set the language code used for searches.

        - set_period(self, period: int) -> None
            Set the number of days to look back when collecting news.

        - set_encode(self, encode: str) -> None
            Set the text encoding used when decoding responses.

        - set_date(self, date: str | datetime) -> None
            Set the initial date. Accepts an ISO 8601 string or a datetime object.

        - get_news(self, *, query: str) -> Coroutine
            Asynchronous method that fetches news for the provided query using aiohttp.
            Returns the response text (str) when awaited.

        Returns
        -------
        None
        """

        self.__links: list[str] = []
        self.__results: list[ArticleModel] = []
        self.__period: int = period
        self.__lang: str = lang
        self.headers: dict[str, str] = {'User-Agent': self.__user_agent}
        self.__encode = encode
        self.gl: str = geolocalization
        self.max_results: int = max_results
        self.__date: datetime

        if date is None:
            self.__date = datetime.now()
        elif isinstance(date, str):
            self.__date = datetime.fromisoformat(date)
        else:
            self.__date = date

    @property
    def __user_agent(self) -> str:
        return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

    def set_lang(self, lang: str):
        """
        Set the language code used for news searches.

        Parameters
        ----------
        lang : str
            Language code (for example 'en' for English or 'pt' for Portuguese).
            This updates the instance attribute used when building search requests.
        """
        self.__lang = lang

        def set_period(self, period: int):
            """
            Set the number of days to look back when collecting news.

            Parameters
            ----------
            period : int
                Number of days from the configured date to include when fetching news.
                This updates the instance attribute used to limit the time range of search results.

            Returns
            -------
            None
            """
            self.__period = period

        def set_encode(self, encode: int):
            """
            Set the text encoding used when decoding responses.

            Parameters
            ----------
            encode : int
                Text encoding name or identifier to use when processing response text (for example 'utf-8').
                This updates the instance attribute that controls how response bytes are decoded.

            Returns
            -------
            None
            """
            self.__encode = encode

        def set_date(self, date: str | datetime):
            """
            Set the initial date for news queries.

            Parameters
            ----------
            date : str | datetime
                Initial date to use when building queries. If a string is provided it must be in ISO 8601
                format and will be parsed with datetime.fromisoformat. If a datetime is provided it will be
                used directly.

            Returns
            -------
            None
            """
            if isinstance(date, str):
                self.__date = datetime.fromisoformat(date)
            else:
                self.__date = date

    def get_results(self) -> list[ArticleModel]:
        """
        Get the list of news results fetched by the get_news method.

        Returns
        -------
        list of dict
            A list of dictionaries containing news items with 'title', 'link', and 'pubDate' keys.
        """
        return [result for result in self.__results]

    async def get_news(self, *, query: str = 'Noticias'):
        """
        Fetch news from Google News RSS for a given query and parse the results.

        This asynchronous method builds a Google News RSS search URL using the instance's
        language, geolocation, date and period settings, then performs an HTTP GET request
        using aiohttp. The response text is passed to soup_news via a thread pool executor
        for XML parsing with BeautifulSoup.

        Parameters
        ----------
        query : str, optional
            Search query to send to Google News (default: 'Noticias').

        Returns
        -------
        list[dict[str, str]] | str
            On success, returns a list of dictionaries (each with 'title', 'link', and
            'pubDate' keys) populated by soup_news. If an exception occurs during the HTTP
            request, a string with an error message is returned.

        Notes
        -----
        - The method uses self.__encode to decode the HTTP response.
        - Network errors and HTTP errors are logged and result in a string being returned.
        - The actual XML parsing is delegated to soup_news and is executed in a thread
          pool to avoid blocking the event loop.
        """
        results = []
        urls = []

        for i in range(self.__period):
            query_params = {
                'query': query,
                'after': (self.__date + timedelta(days=i)).strftime('%Y-%m-%d'),
                'before': (self.__date + timedelta(days=i + 1)).strftime('%Y-%m-%d'),
                'lang': self.__lang,
                'geolocalization': self.gl,
            }
            url = 'https://news.google.com/rss/search?q={query} after%3A{after} before%3A{before}&hl={lang}&gl={geolocalization}'.format(
                **query_params
            )
            urls.append(url)

        async def fetch(session, url):
            try:
                async with session.get(url, headers=self.headers, timeout=TIMEOUT_MAX) as response:
                    response.raise_for_status()
                    return await response.text(encoding=self.__encode)
            except Exception as e:
                logging.error(f'Error fetching {url}: {e}')
                return None

        async with aiohttp.ClientSession() as session:
            tasks = [fetch(session, url) for url in urls]
            results = await asyncio.gather(*tasks)

        loop = asyncio.get_event_loop()

        seen_titles = set()

        for result in results:
            if result is not None:
                souped_result = await loop.run_in_executor(None, self.soup_news, result)

                if souped_result:
                    for item in souped_result:
                        if item.title not in seen_titles:
                            seen_titles.add(item.title)
                            self.__results.append(item)

        return self.__results

    def soup_news(self, news: str) -> list[ArticleModel]:
        """
        Parse an RSS/XML news string with BeautifulSoup and return a list of news item dictionaries.

        Parameters
        ----------
        news : str
            A string containing RSS or XML-formatted news data (for example, the response text
            retrieved from Google News RSS).

        Returns
        -------
        list[dict[str, str]]
            A list of dictionaries where each dictionary represents a news item and contains the
            following keys:
            - 'title': the news title as a string
            - 'link': the URL to the news item as a string
            - 'pubDate': the publication date as a string

        Notes
        -----
        - The method uses BeautifulSoup with the 'lxml-xml' parser to parse the RSS content.
        - Parsed items are appended to self.__results as a side effect.
        - If `news` is falsy or not valid XML, behavior depends on BeautifulSoup and the surrounding code.
        """
        if news:
            features = 'lxml-xml'
            parsed_news: BeautifulSoup = BeautifulSoup(news, features=features)
        items = parsed_news.find_all('item')

        results: list[ArticleModel] = []

        for item in items:
            if item.title:
                title: str = item.title.get_text(strip=True)
            else:
                title = 'Error fetching title.'

            if item.link:
                link: str = item.link.get_text(strip=True)
            else:
                link = 'Error fetching link.'

            if item.pubDate:
                pub_date = item.pubDate.get_text(strip=True)
            else:
                pub_date = 'Error fetching date.'

            if item.source:
                source = item.source.get_text(strip=True)
                source_link = item.source.get('url')
            else:
                source = 'Error fetching source.'

            results.append(
                ArticleModel(title=title, link=link, source_name=source, source_url=source_link, pub_date=pub_date)
            )

        return results


def load_json(file_name: str) -> dict[str, str]:
    try:
        with open(file_name, 'r') as file:
            return json.load(file)

    except FileNotFoundError:
        return {}

    except Exception as e:
        logging.error(f'Error loading JSON: {e}')
        return {}


if __name__ == '__main__':

    async def main():
        google_news = Google_news(lang='pt-br', period=1, date='2025-12-21')
        _ = await google_news.get_news(query='Inteligencia Artificial')
        items = google_news.get_results()
        _ = save_to_json(items, 'news.json')

    asyncio.run(main())
