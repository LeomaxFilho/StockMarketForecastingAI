import asyncio
import logging
from datetime import datetime, timedelta

import aiohttp
from bs4 import BeautifulSoup

TIMEOUT_MAX = aiohttp.ClientTimeout(total=10)


class Google_news:
    def __init__(
        self,
        lang: str = 'pt',
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
        self.__results: list[dict[str, str]] = []
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

    def get_results(self) -> list[dict[str, str]]:
        """
        Get the list of news results fetched by the get_news method.

        Returns
        -------
        list of dict
            A list of dictionaries containing news items with 'title', 'link', and 'pubDate' keys.
        """
        return self.__results

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
        url = 'https://news.google.com/rss/search?q={query} after%3A{after} before%3A{before}&hl={lang}&gl={geolocalization}&num{max_results}'.format(
            query=query,
            after=self.__date.strftime('%Y-%m-%d'),
            lang=self.__lang,
            geolocalization=self.gl,
            before=(self.__date + timedelta(days=self.__period)).strftime('%Y-%m-%d'),
            max_results=self.max_results,
        )
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, headers=self.headers) as response:
                    response.raise_for_status()
                    result: str = await response.text(enconding=self.__encode, timeout=TIMEOUT_MAX)

            except Exception as e:
                logging.error(f'Error fetching news: {e}')
                result = 'Error fetching news.'
                return result

        loop = asyncio.get_event_loop()
        souped_result = await loop.run_in_executor(None, self.soup_news, result)

        return souped_result

    def soup_news(self, news: str) -> list[dict[str, str]]:
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

            self.__results.append({'title': title, 'link': link, 'pubDate': pub_date})

        return self.__results


if __name__ == '__main__':

    async def main():
        google_news = Google_news(lang='en', period=2, max_results=10, date='2025-12-21')
        _ = await google_news.get_news(query='Artificial Intelligence')
        items = google_news.get_results()
        print(items)

    asyncio.run(main())
