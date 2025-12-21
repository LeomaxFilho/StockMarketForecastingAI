"""Utility helpers used by the news pipeline.

This module contains small, focused functions to perform Google Custom
Search queries, fetch web pages asynchronously, and extract article text
from the resulting HTML. Functions are intentionally minimal so they can
be composed by a higher-level pipeline (see `src/news/news_data.py`).

Public functions
- `fetch_search`  : asynchronous generator that performs Custom Search queries
                    and yields raw API response objects and result URLs.
- `fetch_news`    : concurrently fetch multiple URLs and return page contents.
- `get_url`       : fetch a single URL using an aiohttp session.
- `soup_articles` : extract simple article metadata and cleaned text from HTML.

Environment and dependencies
- Google Custom Search API: the calling code must provide a valid API key
  and CX (search engine id).
- Python packages: `requests`, `aiohttp`, `beautifulsoup4` (`bs4`), and the
  standard library modules `sys`, `json`, and `asyncio`.

Design notes
- Functions prefer explicit return values over side effects; the caller is
  responsible for persisting results (for example, saving raw JSON to disk).
- Error handling is conservative: many network errors are treated as fatal
  (the current code calls `sys.exit()` on some errors). Callers can adapt
  this behavior if needed.
"""

import asyncio
import json
from collections.abc import AsyncGenerator
from datetime import datetime

import aiohttp
import bs4
import requests
from bs4 import BeautifulSoup, Tag

timeout_config = aiohttp.ClientTimeout(10.0)
timeout_conf: int = 120


def _fetch_search(
    api_custom_search: str,
    url_custom_search: str,
    cx_custom_search: str,
    local: str,
    q: list[str],
) -> tuple[dict[str, str], list[str]]:
    """Perform a Google Custom Search and persist the JSON response.

    This is a synchronous, helper function that issues a single request to
    the Google Custom Search API, writes the raw JSON response to `local`,
    and returns the parsed JSON plus the top result links.

    Parameters
    ----------
    api_custom_search : str
        API key for Google Custom Search.
    url_custom_search : str
        Base URL for the Custom Search API (for example:
        'https://customsearch.googleapis.com/customsearch/v1').
    cx_custom_search : str
        Custom Search Engine ID (the `cx` parameter).
    local : str
        Filesystem path where the raw JSON response will be written.
    q : list[str]
        Query terms to send with the request.

    Returns
    -------
    tuple[dict, list[str]]
        A tuple (data, urls) where `data` is the parsed JSON response (dict)
        and `urls` is a list of the top result links (list of strings).

    Raises
    ------
    SystemExit
        The implementation calls `sys.exit()` after logging HTTP or connection
        errors. Callers that require non-fatal failure should change this
        behavior.
    """

    param_custom_search = {
        'key': api_custom_search,
        'cx': cx_custom_search,
        'q': q,
        'start': 0,
    }

    try:
        response = requests.get(url=url_custom_search, params=param_custom_search, timeout=timeout_conf)
        response.raise_for_status()
        data = response.json()

    except requests.exceptions.HTTPError as ex:
        print(f'\033[91m fetch_search error: {ex}\033[0m')
    except requests.exceptions.ConnectionError as ex:
        print(f'\033[91m fetch_search error: {ex}\033[0m')

    with open(local, 'w', encoding='utf-8') as file:
        json.dump(response.json(), file, indent=4)

    urls = [data['items'][i]['link'] for i in range(10)]

    return data, urls


async def __fetch_search(
    api_custom_search: str,
    url_custom_search: str,
    cx_custom_search: str,
    q_list: list[str],
) -> AsyncGenerator[tuple[dict[str, str], list[str]], None]:
    """Asynchronously perform Google Custom Search queries and yield pages.

    This function is an async generator that paginates over the Custom Search
    API results. For each query term in `q_list` it requests pages of
    results (start=1, 11, 21, ...). For each non-empty page it yields the
    parsed JSON and the list of result URLs found on that page.

    Parameters
    ----------
    api_custom_search : str
        API key for Google Custom Search.
    url_custom_search : str
        Base URL for the Custom Search API.
    cx_custom_search : str
        Custom Search Engine ID.
    q_list : list[str]
        Iterable of query strings to run.

    Yields
    ------
    tuple[dict, list[str]]
        For each page, yields a tuple (data, urls) where `data` is the JSON
        response and `urls` is a list of link strings extracted from that page.

    Notes
    -----
    Network and HTTP errors are logged and currently cause a process exit.
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
                        url_custom_search,
                        params=param_custom_search,
                        timeout=timeout_config,
                    ) as response:
                        response.raise_for_status()
                        data = await response.json()

                except aiohttp.ClientResponseError as ex:
                    print(f'\033[91m fetch_search error: {ex}\033[0m')

                except aiohttp.ClientConnectionError as ex:
                    print(f'\033[91m fetch_search error: {ex}\033[0m')

                items = data.get('items', [])
                if not items:
                    break
                urls = [item.get('link') for item in items if 'link' in item]

                yield data, urls


async def fetch_search(
    api_news_api: str,
    url_news_api: str,
    domains: list[str],
    dates: list[str],
    language: str,
):
    date_format = '%Y-%m-%d %H:%M:%S%z'
    async with aiohttp.ClientSession() as session:
        for date in dates:
            date_datetime = datetime.strptime(date, date_format)
            param = {
                'apiKey': api_news_api,
                'from': f'{date_datetime.strftime("%Y-%m-%d")}T10:00:00',
                'to': f'{date_datetime.strftime("%Y-%m-%d")}T18:25:00',
                'domains': domains,
                'language': language,
            }
            try:
                async with session.get(url_news_api, params=param, timeout=timeout_config) as response:
                    response.raise_for_status()
                    data = await response.json()

            except aiohttp.ClientResponseError as ex:
                print(f'\033[91m fetch_search error: {ex}\033[0m')

            except aiohttp.ClientConnectionError as ex:
                print(f'\033[91m fetch_search error: {ex}\033[0m')

    return data


def save_json(path: str, data: dict[str, str]):
    """Write a Python object to a file as pretty-printed JSON.

    Parameters
    ----------
    path : str
        Destination file path.
    data : dict
        Python object (typically a dict or list) to serialize as JSON.

    This helper uses UTF-8 encoding and an indent of 4 for readability.
    """
    with open(path, 'w', encoding='UTF-8') as file:
        json.dump(data, file, indent=4, ensure_ascii=False)


async def get_url(url: str, session: aiohttp.ClientSession) -> tuple[str, str]:
    """Asynchronously fetch a single URL and return (text, url).

    Performs an HTTP GET using the provided `aiohttp.ClientSession` and
    returns a tuple `(response_text, url)`. The function raises a
    `SystemExit` after logging for several categories of aiohttp errors in
    the current implementation; callers that need resilient behaviour should
    catch exceptions or modify the error handling.

    Parameters
    ----------
    url : str
        The URL to fetch.
    session : aiohttp.ClientSession
        An active aiohttp session used to perform the request.

    Returns
    -------
    tuple[str, str]
        A tuple containing the response body as text and the original URL.

    Raises
    ------
    SystemExit
        The function currently exits the process on ClientResponseError,
        InvalidURL, ConnectionTimeoutError and general ClientError after
        printing an error message.
    """

    try:
        async with session.get(url, timeout=timeout_config) as request:
            request.raise_for_status()
            response = await request.text()

    except aiohttp.ClientResponseError as ex:
        print(f'\033[91m Response Error URL: {ex}\033[0m')

    except aiohttp.InvalidURL as ex:
        print(f'\033[91m Invalid URL: {ex}\033[0m')

    except aiohttp.ConnectionTimeoutError as ex:
        print(f'\033[91m Timeout Error: {ex}\033[0m')

    except aiohttp.ClientError as ex:
        print(f'\033[91m Client Error: {ex}\033[0m')

    return (response, url)


async def fetch_news(urls: list[str]) -> list[tuple[str, str]]:
    """Fetch multiple URLs concurrently and return their results.

    This helper creates an aiohttp session and dispatches parallel GET
    requests for every URL in `urls` using `asyncio.gather` and the helper
    `get_url`. The function returns a list of tuples `(text, url)` in the
    same order as the input `urls`.

    Parameters
    ----------
    urls : list[str]
        A list of URLs to fetch concurrently.

    Returns
    -------
    list[tuple[str, str]]
        A list where each element is a tuple `(response_text, url)` produced
        by `get_url`. The order of results matches the order of the `urls`
        argument.
    """

    async with aiohttp.ClientSession() as connection:
        articles = await asyncio.gather(*[get_url(url, connection) for url in urls])
        return articles


def soup_articles(article: tuple[str, str]) -> dict[str, str]:
    """Extract simple article metadata and cleaned text from HTML.

    The input `article` is expected to be a tuple `(html_text, url)` as
    returned by `get_url`. The function selects a parser based on the URL
    (currently supports 'g1' and 'cnn' detectors) and returns a dictionary
    containing at least the `content` and `url` keys; when available the
    `header` key is also provided.

    Parameters
    ----------
    article : tuple[str, str]
        Tuple with `(html_text, url)`.

    Returns
    -------
    dict
        Dictionary with keys:
        - 'content': cleaned article text (whitespace collapsed)
        - 'url': source URL
        - 'header' (optional): article title when found
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
    """Parse G1-style pages: extract header and main article body.

    This parser attempts several selectors commonly used by G1 and
    WordPress-based templates to find the article body. It also extracts
    the first <h1> as the article header when present.

    Parameters
    ----------
    soup : bs4.BeautifulSoup
        Parsed HTML document.

    Returns
    -------
    dict
        A dictionary with keys:
        - 'header' : str, the H1 text or a fallback message if not found
        - 'content': str, the main article text or a fallback message

    Notes
    -----
    The function iterates over a list of candidate selectors and returns the
    first match. If no container is found the function returns a fallback
    string in the `content` field rather than raising an exception.
    Callers that require stronger guarantees should check the returned
    dictionary before using its values.
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

    header = 'Not Title Avaliable'

    header_tag = soup.find('h1')

    if header_tag:
        header = header_tag.get_text(strip=True)

    content = 'Not Content Avaliable'
    for selector in possible_containers:
        article_content: Tag = soup.find(attrs=selector)

        if article_content:
            photo_tags = article_content.find_all('p', class_='content-media__description')

            for tags in photo_tags:
                _ = tags.decompose()

            paragraphs: bs4.element.ResultSet[Tag] = article_content.find_all('p')

            content: str = ' '.join([paragraph.get_text(strip=True) for paragraph in paragraphs])
            break

        content = 'Not Content Avaliable'

    return {'header': header, 'content': content}


def soup_articles_cnn(soup: BeautifulSoup) -> dict[str, str]:
    """Extract header and paragraph content from CNN-style pages.

    This parser looks for the first <h1> element as the header and then
    searches for a div with `data-single-content="true"` to collect paragraph
    nodes. Paragraph texts are concatenated with single spaces (whitespace
    is collapsed) to produce a compact content string.

    Parameters
    ----------
    soup : bs4.BeautifulSoup
        Parsed HTML document.

    Returns
    -------
    dict
        A dictionary with keys:
        - 'header' : str, the H1 text or a fallback string
        - 'content': str, concatenated paragraph texts or a fallback string

    Notes
    -----
    If the expected content container is missing or the HTML is badly formed,
    the function returns a fallback message in the `content` field. Callers
    should validate the returned dictionary before downstream processing.
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
