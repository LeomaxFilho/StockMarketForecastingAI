"""Utility functions for searching and downloading news articles.

This module provides a small set of helpers used by the news pipeline:

- ``fetch_search(api_custom_search, url_custom_search, cx_custom_search, local)``
    : Perform a Google Custom Search, save the raw JSON response to ``local``
        and return the parsed JSON along with the top-10 result URLs.

- ``get_url(url, session)`` : Asynchronously GET a single URL using an
    ``aiohttp.ClientSession`` and return the response body as text or the
    string ``'Error'`` if the request fails (the function logs the error).

- ``fetch_news(urls)`` : Concurrently fetch multiple URLs using
    ``get_url`` and return a list of page contents (or ``'Error'`` markers).

- ``soup_articles(article)`` : Extract visible text from HTML using
    BeautifulSoup and collapse whitespace for a simple article text string.

Dependencies
- ``requests``, ``aiohttp``, ``beautifulsoup4`` (``bs4``), and the Python
    standard library modules ``sys``, ``json`` and ``asyncio``.

Usage example
 - Import the helpers from ``utils.functions`` and integrate them into a
     script or pipeline; see ``src/news/news_data.py`` for an example orchestration
     that calls ``fetch_search`` and ``fetch_news``.

"""

import asyncio
import json
import sys
from collections.abc import AsyncGenerator

import aiohttp
import requests
from bs4 import BeautifulSoup

timeout_config = aiohttp.ClientTimeout(10.0)


def _fetch_search(
    api_custom_search: str,
    url_custom_search: str,
    cx_custom_search: str,
    local: str,
    q: list[str],
) -> tuple[dict[str, str], list[str]]:
    """Perform a Google Custom Search and persist the JSON response.

    Sends a request to the Google Custom Search API using the provided
    credentials and query parameters. The raw JSON response is written to
    ``local`` and the function returns the parsed response along with a list
    of the top 10 result URLs.

    Args:
        api_custom_search: API key for Google Custom Search.
        url_custom_search: Base URL for the Custom Search API (e.g.:
            ``'https://customsearch.googleapis.com/customsearch/v1'``).
        cx_custom_search: Custom search engine ID (cx parameter).
        local: Path where the full JSON response will be saved.

    Returns:
        A tuple ``(data, urls)`` where ``data`` is the parsed JSON response
        (a dict) and ``urls`` is a list of the top 10 result links (list of
        strings).

    Notes:
        On HTTP or connection errors the function prints the error and calls
        ``sys.exit()`` to stop the program. Timeout is set to 120 seconds.
    """

    param_custom_search = {
        'key': api_custom_search,
        'cx': cx_custom_search,
        'q': q,
        'start': 0,
    }

    try:
        response = requests.get(url=url_custom_search, params=param_custom_search, timeout=120)
        response.raise_for_status()
        data = response.json()

    except requests.exceptions.HTTPError as ex:
        print(f'\033[91m fetch_search error: {ex}\033[0m')
        sys.exit()
    except requests.exceptions.ConnectionError as ex:
        print(f'\033[91m fetch_search error: {ex}\033[0m')
        sys.exit()

    with open(local, 'w', encoding='utf-8') as file:
        json.dump(response.json(), file, indent=4)

    urls = [data['items'][i]['link'] for i in range(10)]

    return data, urls


async def fetch_search(
    api_custom_search: str,
    url_custom_search: str,
    cx_custom_search: str,
    q_list: list[str],
) -> AsyncGenerator[tuple[dict[str, str], list[str]], None]:
    """Perform a Google Custom Search yielding results page by page.

    Args:
        api_custom_search: API key for Google Custom Search.
        url_custom_search: Base URL for the Custom Search API.
        cx_custom_search: Custom search engine ID.
        q: List of query terms.

    Yields:
        A tuple ``(data, urls)`` for each page found.
    """

    async with aiohttp.ClientSession() as session:
        for q in q_list:
            for index in range(1, 100, 10):
                param_custom_search = {
                    'key': api_custom_search,
                    'cx': cx_custom_search,
                    'q': q,
                    'start': index,
                }

                try:
                    async with session.get(
                        url_custom_search, params=param_custom_search, timeout=timeout_config
                    ) as response:
                        response.raise_for_status()
                        data = await response.json()

                except aiohttp.ClientResponseError as ex:
                    print(f'\033[91m fetch_search error: {ex}\033[0m')
                    sys.exit()
                except aiohttp.ClientConnectionError as ex:
                    print(f'\033[91m fetch_search error: {ex}\033[0m')
                    sys.exit()

                items = data.get('items', [])
                if not items:
                    break
                urls = [item.get('link') for item in items if 'link' in item]

                yield data, urls


def save_json(path: str, data: dict[str, str]):
    """function to save data as json in a file"""
    with open(path, 'w', encoding='UTF-8') as file:
        json.dump(data, file, indent=4)


async def get_url(url: str, session: aiohttp.ClientSession) -> tuple[str, str]:
    """Fetch a single URL asynchronously and return its text content.

    Uses the provided ``aiohttp.ClientSession`` to perform a GET request and
    returns the response body as a string. On network or client errors the
    function catches the exception, logs a brief message to stdout (red
    colored) and returns the string ``'Error'`` to signal failure.

    Args:
        url: The URL to fetch.
        session: An active ``aiohttp.ClientSession`` instance.

    Returns:
        The response body as a string on success, or the string ``'Error'``
        if the request failed for any handled reason.
    """

    try:
        async with session.get(url, timeout=timeout_config) as request:
            request.raise_for_status()
            response = await request.text()

    except aiohttp.ClientResponseError as ex:
        print(f'\033[91m Response Error URL: {ex}\033[0m')
        sys.exit()

    except aiohttp.InvalidURL as ex:
        print(f'\033[91m Invalid URL: {ex}\033[0m')
        sys.exit()

    except aiohttp.ConnectionTimeoutError as ex:
        print(f'\033[91m Timeout Error: {ex}\033[0m')
        sys.exit()

    except aiohttp.ClientError as ex:
        print(f'\033[91m Client Error: {ex}\033[0m')
        sys.exit()

    return (response, url)


async def fetch_news(urls: list[str]) -> list[tuple[str, str]]:
    """Concurrently fetch multiple URLs and return their HTML content.

    Creates an ``aiohttp.ClientSession`` and concurrently requests all URLs
    provided in the ``urls`` list using :func:`get_url`. The function returns a
    list of strings containing the HTML/text for each URL. If individual
    requests fail, the corresponding entry will be the string ``'Error'``.

    Args:
        urls: A list of URLs to fetch.

    Returns:
        A list of strings, each either the HTML/text content of the fetched
        page or ``'Error'`` for failed requests.
    """

    async with aiohttp.ClientSession() as connection:
        articles = await asyncio.gather(*[get_url(url, connection) for url in urls])
        return articles


def soup_articles(article: tuple[str, str]) -> dict[str, str]:
    """Extract cleaned text from a single HTML document.

    The function parses the supplied HTML string with BeautifulSoup and
    returns the visible text with all line breaks removed. This is useful as
    a simple, fast way to get contiguous article text, but it does not
    attempt advanced boilerplate removal.

    Args:
        article: HTML document as a string.

    Returns:
        A string with the extracted text where line breaks have been removed.
    """

    soup = BeautifulSoup(article[0], 'html.parser')

    parsers = {'g1': soup_articles_g1, 'cnn': soup_articles_cnn}

    article_souped: dict[str, str] = {}

    for key, parser_func in parsers.items():
        if key in article[1]:
            article_souped = parser_func(soup)
            article_text = article_souped['content']
            article_souped['content'] = ' '.join(article_text.split())
            article_souped['url'] = article[1]
            break

    return article_souped


def soup_articles_g1(soup: BeautifulSoup) -> dict[str, str]:
    """Extract header and main article text from G1-style pages.

    This parser tries a sequence of common container selectors used by G1
    (and several WordPress-based templates) to locate the main article body.
    It also extracts the article header from the first ``<h1>`` element.

    Args:
        soup: A ``BeautifulSoup`` object created from the article HTML.

    Returns:
        A dictionary with keys ``'header'`` (the H1 text) and ``'content'``
        (the extracted article text with surrounding whitespace removed).

    Notes:
        - The function checks a list of possible selectors in order and uses
          the first one that matches.
        - If no matching container is found the current implementation will
          return ``content.get_text(strip=True)`` on a ``None`` object and
          raise an exception; callers may want to handle that case upstream.
    """

    possible_containers = [
        {'class_': 'mc-article-body'},  # G1 Novo
        {'itemprop': 'articleBody'},  # Padrão Schema.org
        {'class_': 'materia-conteudo'},  # G1 Antigo
        {'class_': 'entry-content'},  # WordPress Padrão
        {'class_': 'post-content'},
        {'class_': 'article-content'},
        {'id': 'materia-letra'},
    ]

    header_tag = soup.find('h1')
    if header_tag:
        header = header_tag.get_text(strip=True)
    else:
        header = 'Not Title Avaliable'

    for selector in possible_containers:
        content = soup.find(attrs=selector)
        if content:
            content = content.get_text(strip=True)
            break

        content = 'Not Content Avaliable'

    return {'header': header, 'content': content}


def soup_articles_cnn(soup: BeautifulSoup) -> dict[str, str]:
    """Extract header and paragraph content from CNN article pages.

    This parser locates the article header (first ``<h1>``) and then finds
    the container identified by ``data-single-content='true'``. It collects
    all paragraph texts inside that container and joins them using two
    newline characters to preserve paragraph breaks.

    Args:
        soup: A ``BeautifulSoup`` object parsed from the article HTML.

    Returns:
        A dictionary with keys ``'header'`` and ``'content'``. ``'content'``
        contains the joined paragraph texts separated by double newlines.

    Notes:
        - If ``data-single-content`` is not present the call to
          ``content_div.find_all('p')`` will raise an exception; callers may
          want to guard against malformed HTML.
    """

    header_tag = soup.find('h1')
    if header_tag:
        header = header_tag.get_text(strip=True)
    else:
        header = 'Title Not Avaliable'

    content_div = soup.find(name='div', attrs={'data-single-content': 'true'})
    if content_div:
        paragraphs = content_div.find_all('p')
        content = ' '.join([paragraph.get_text(strip=True) for paragraph in paragraphs])
    else:
        content = 'Paragraphs Not Avaliable'

    return {'header': header, 'content': content}
