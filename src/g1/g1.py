#!/usr/bin/env python3
"""Simple scraper for G1 search results using Selenium.

This module provides a `GUM` class that can perform searches on g1.globo.com,
scroll the results page to load widgets, and extract article links.
"""

import asyncio
import json
import time
import urllib.parse
from datetime import datetime, timedelta

import aiohttp
import bs4
from bs4 import BeautifulSoup, Tag
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

timeout_conf: int = 20
timeout_config = aiohttp.ClientTimeout(float(timeout_conf))


class GUM:
    def __init__(self, query: str = '', period: int = 1, date: str | None | datetime = None):
        """
        Parameters
        ----------
        query : str
            Search query.
        period : int
            Number of days from `date` to include in search (keeps previous behavior:
            end date = date + period days).
        date : str | datetime | None
            If str, it must be ISO format parseable by datetime.fromisoformat().
            If None, defaults to now().
        """
        self.__query = query
        self.__period = period
        self.__date: datetime

        if date is None:
            self.__date = datetime.now()
        elif isinstance(date, str):
            self.__date = datetime.fromisoformat(date)
        else:
            self.__date = date

    def load_widgets(
        self,
        driver: WebDriver,
        max_scrolls: int = 100,
        pause: float = 1.5,
        max_idle: int = 5,
        timeout: float = 60.0,
        load_more_selector: str | None = None,
    ) -> list[WebElement]:
        """
        Attempt to load as much dynamic content as possible by repeatedly scrolling
        (and optionally clicking a "load more" button if a selector is provided).

        The function stops when one of the following occurs:
          - no page height change is observed for `max_idle` consecutive attempts
          - `max_scrolls` scroll/click attempts were performed
          - `timeout` seconds have elapsed

        Parameters
        ----------
        driver: WebDriver
            Selenium WebDriver instance.
        max_scrolls: int
            Maximum number of scroll/click attempts.
        pause: float
            Seconds to wait after each scroll/click to let content load.
        max_idle: int
            Maximum number of consecutive attempts with no page height change.
        timeout: float
            Maximum total seconds to keep trying.
        load_more_selector: str|None
            Optional CSS selector for a "load more" button to click, if present.

        Returns
        -------
        list[WebElement]
            Elements matching `li.widget` after the loading attempts.
        """
        start = time.time()
        last_height: int = int(driver.execute_script('return document.body.scrollHeight') or 0)
        idle = 0
        attempts = 0

        while attempts < max_scrolls and (time.time() - start) < timeout:
            # if there is a load-more button, try to click it first
            if load_more_selector:
                try:
                    btn = driver.find_element(By.CSS_SELECTOR, load_more_selector)
                    driver.execute_script('arguments[0].scrollIntoView(true);', btn)
                    driver.execute_script('arguments[0].click();', btn)
                    time.sleep(pause)
                except Exception:
                    # button not present or click failed; continue with scrolling
                    pass

            driver.execute_script('window.scrollTo(0, document.body.scrollHeight);')
            time.sleep(pause)

            new_height: int = int(driver.execute_script('return document.body.scrollHeight') or 0)
            attempts += 1

            if new_height == last_height:
                idle += 1
                if idle >= max_idle:
                    break
            else:
                idle = 0
                last_height = new_height

        items = driver.find_elements(By.CSS_SELECTOR, 'li.widget')
        return items

    def search_g1(
        self,
        headless: bool = False,
        max_scrolls: int = 100,
        pause: float = 1.5,
        max_idle: int = 3,
        timeout: float = 60.0,
        load_more_selector: str | None = None,
    ) -> list[str]:
        """
        Perform a synchronous search on g1.globo.com and return a list of article URLs.

        Parameters
        ----------
        headless : bool
            If True, runs Chrome in headless mode (useful for CI or servers).
        max_scrolls : int
            Maximum number of scroll/click attempts that `load_widgets` will try.
        pause : float
            Seconds to wait after each scroll/click to let content load.
        max_idle : int
            Maximum number of consecutive attempts with no page height change before stopping.
        timeout : float
            Total time limit (in seconds) for loading additional content.
        load_more_selector : str | None
            Optional CSS selector for a "load more" button to click between scrolls.

        Returns
        -------
        list[str]
            Extracted hrefs from result widgets (may be empty).
        """
        query = urllib.parse.quote_plus(self.__query)
        date_end_period = self.__date + timedelta(days=self.__period)
        url = ('https://g1.globo.com/busca/?q={}&from={}T03%3A00%3A00.000Z&to={}T02%3A59%3A59.999Z').format(
            query, self.__date.strftime('%Y-%m-%d'), date_end_period.strftime('%Y-%m-%d')
        )

        options = Options()
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--start-maximized')
        options.add_argument('--window-size=1920,1080')

        options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        options.add_argument('--incognito')

        if headless:
            options.add_argument('--headless=new')
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')

        try:
            driver = webdriver.Chrome(options=options)
        except WebDriverException as exc:
            raise RuntimeError(
                'Could not start Chrome WebDriver. Ensure chromedriver is installed and compatible with your browser.'
            ) from exc

        links: list[str] = []
        try:
            driver.get(url)

            wait = WebDriverWait(driver, 30)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'li.widget')))

            items = self.load_widgets(
                driver,
                max_scrolls=max_scrolls,
                pause=pause,
                max_idle=max_idle,
                timeout=timeout,
                load_more_selector=load_more_selector,
            )
            for item in items:
                try:
                    a = item.find_element(By.CSS_SELECTOR, 'a[href]')
                    href = a.get_attribute('href')
                    if href:
                        links.append(href)
                except NoSuchElementException:
                    continue
                except Exception:
                    continue
        finally:
            try:
                driver.quit()
            except Exception:
                pass

        return links

    async def search(self, *args, **kwargs) -> list[str]:
        """
        Async wrapper that runs the blocking `search_g1` in a thread pool executor.

        Allows usage like `asyncio.run(GUM.search())`.
        Any arguments are forwarded to `search_g1` (for example `headless=True`).
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: self.search_g1(*args, **kwargs))


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
    response = ''
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        async with session.get(url, timeout=timeout_config, headers=headers) as request:
            request.raise_for_status()
            response = await request.text()

    except (aiohttp.ServerTimeoutError, asyncio.TimeoutError, TimeoutError):
        response = 'Timeout Error'
        print(f'\033[91m Timeout Error: {url}\033[0m')

    except aiohttp.ClientResponseError as ex:
        print(f'\033[91m Response Error URL: {ex}\033[0m')

    except aiohttp.InvalidURL as ex:
        print(f'\033[91m Invalid URL: {ex}\033[0m')

    except aiohttp.ClientError as ex:
        print(f'\033[91m Client Error: {ex}\033[0m')

    return (response, url)


def soup_articles_g1(article: str) -> dict[str, str]:
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
    soup = BeautifulSoup(article, 'html.parser')

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


async def fetch_news(urls: list[str], limit: int = 5) -> list[tuple[str, str]]:
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

    semaphore = asyncio.Semaphore(limit)

    async def fetch_with_sem(url: str, session: aiohttp.ClientSession):
        async with semaphore:
            # Pequeno delay aleatório para parecer mais humano
            await asyncio.sleep(0.5)
            return await get_url(url, session)

    async with aiohttp.ClientSession() as connection:
        tasks = [fetch_with_sem(url, connection) for url in urls]
        articles = await asyncio.gather(*tasks)
        return articles


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
    with open('salvo.json', 'w', encoding='UTF-8') as file:
        json.dump(data, file, indent=4, ensure_ascii=False)


if __name__ == '__main__':
    gum = GUM(query='noticias', period=1, date='2023-01-01')
    results = asyncio.run(gum.search(headless=False))
    articles = asyncio.run(fetch_news(results))
    souped = [soup_articles_g1(article[0]) for article in articles if article[0]]
    save_json('salvo.json', {'articles': souped})
