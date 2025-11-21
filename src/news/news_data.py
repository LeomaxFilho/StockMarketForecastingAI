import sys
import os
import requests
import json
import aiohttp
import asyncio
from dotenv import load_dotenv
from bs4 import BeautifulSoup

def fetch_search(API_CUSTOMSEARCH : str, URL_CUSTOMSEARCH : str, CX_CUSTOMSEARCH : str, local : str) -> tuple[dict, list]:
    """Perform a Google Custom Search and persist the JSON response.

    Sends a request to the Google Custom Search API using the provided
    credentials and query parameters. The raw JSON response is written to
    ``local`` and the function returns the parsed response along with a list
    of the top 10 result URLs.

    Args:
        API_CUSTOMSEARCH: API key for Google Custom Search.
        URL_CUSTOMSEARCH: Base URL for the Custom Search API (e.g.:
            ``'https://customsearch.googleapis.com/customsearch/v1'``).
        CX_CUSTOMSEARCH: Custom search engine ID (cx parameter).
        local: Path where the full JSON response will be saved.

    Returns:
        A tuple ``(data, urls)`` where ``data`` is the parsed JSON response
        (a dict) and ``urls`` is a list of the top 10 result links (list of
        strings).

    Notes:
        On HTTP or connection errors the function prints the error and calls
        ``sys.exit()`` to stop the program. Timeout is set to 120 seconds.
    """

    param_CUSTOMSEARCH = {
    'key': API_CUSTOMSEARCH,
    'cx' : CX_CUSTOMSEARCH,
    'q': 'Petrobras',
    }

    try:
        response = requests.get(url=URL_CUSTOMSEARCH, params=param_CUSTOMSEARCH, timeout=120)
        response.raise_for_status()
        data = response.json()

    except requests.exceptions.HTTPError as ex:
        print(f'\033[91m error: {ex}\033[0m')
        sys.exit()
    except requests.exceptions.ConnectionError as ex:
        print(f'\033[91m error: {ex}\033[0m')
        sys.exit()

    with open(local, 'w', encoding='utf-8') as file:
        json.dump(response.json(), file, indent=4)

    urls = [data['items'][i]['link'] for i in range(10)]

    return data, urls

async def get_url(url : str, session : aiohttp.ClientSession) -> str:
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

    return response

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

def soup_articles(article: str) -> str:
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

    soup = BeautifulSoup(article, 'html.parser')
    soup_without_blank_lines = ' '.join(soup.text.split())

    return soup_without_blank_lines

if __name__ == '__main__':
    load_dotenv()

    API_CUSTOM_SEARCH = os.getenv('API_CUSTOM_SEARCH')
    URL_CUSTOM_SEARCH = 'https://customsearch.googleapis.com/customsearch/v1'
    CX_CUSTOM_SEARCH = os.getenv('CUSTOM_SEARCH_ID')

    data, urls = fetch_search(API_CUSTOM_SEARCH, URL_CUSTOM_SEARCH, CX_CUSTOM_SEARCH, 'data/news.json')

    articles = asyncio.run(fetch_news(urls))
    #articles = [soup_articles(article) for article in articles]

    with open('data/articles.json', 'w', encoding='utf-8') as file:
        json.dump(articles, file, indent= 4, ensure_ascii= False)
