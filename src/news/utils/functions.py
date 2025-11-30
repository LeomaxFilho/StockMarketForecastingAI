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

import sys
import json
import asyncio
import requests
import aiohttp
from bs4 import BeautifulSoup

def fetch_search(
        api_custom_search : str, url_custom_search : str, cx_custom_search : str, local : str
    ) -> tuple[dict, list]:
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
    'cx' : cx_custom_search,
    'q': 'Petrobras',
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

async def get_url(url : str, session : aiohttp.ClientSession) -> tuple[str, str]:
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
        async with session.get(url, timeout=10) as request:
            request.raise_for_status()
            response = await request.text()

    except aiohttp.ClientResponseError as ex:
        print(f'\033[91m Response Error URL: {ex}\033[0m')
        return 'Error'

    except aiohttp.InvalidURL as ex:
        print(f'\033[91m Invalid URL: {ex}\033[0m')
        return 'Error'

    except aiohttp.ConnectionTimeoutError as ex:
        print(f'\033[91m Timeout Error: {ex}\033[0m')
        return 'Error'

    except aiohttp.ClientError as ex:
        print(f'\033[91m Client Error: {ex}\033[0m')
        return 'Error'

    return (response, url)

async def fetch_news(urls : list[str]) -> list[str]:
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
        articles = await asyncio.gather(
            *[get_url(url, connection) for url in urls]
        )
        return articles

def soup_articles(article: tuple[str, str]) -> str:
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
    
    parsers = {
        'g1': soup_articles_g1,
        'cnn': soup_articles_cnn
    }

    for key, parser_func in parsers.items():
        if key in article[1]:
            article_souped = parser_func(soup)
            break
    
    article_text = article_souped['content']
    article_souped['content'] = " ".join(article_text.split())
    
    return article_souped

def soup_articles_g1 (soup : BeautifulSoup) -> dict[str, str]:

    possible_containers = [
        {'class_': 'mc-article-body'},    # G1 Novo
        {'itemprop': 'articleBody'},      # Padrão Schema.org
        {'class_': 'materia-conteudo'},   # G1 Antigo
        {'class_': 'entry-content'},      # WordPress Padrão
        {'class_': 'post-content'},       
        {'class_': 'article-content'},
        {'id': 'materia-letra'}           
    ]

    header =  soup.find('h1').get_text(strip=True)
    
    for selector in possible_containers:
        content = soup.find(attrs=selector)
        if content:
            break
    return {'header' : header, 'content' : content.get_text(strip=True)}    


def soup_articles_cnn (soup : BeautifulSoup) -> dict[str, str]:

    header =  soup.find('h1').get_text(strip=True)
    
    content_div = soup.find('div',attrs={'data-single-content' : 'true'})
    paragraphs = content_div.find_all('p')
    
    content = "\n\n".join([p.get_text(strip=True) for p in paragraphs])

    return {'header' : header, 'content' : content}    
