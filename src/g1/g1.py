#!/usr/bin/env python3
"""Simple scraper for G1 search results using Selenium.

This module provides a `GUM` class that can perform searches on g1.globo.com,
scroll the results page to load widgets, and extract article links.
"""

import asyncio
import time
import urllib.parse
from datetime import datetime, timedelta

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


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
        max_idle: int = 3,
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


if __name__ == '__main__':
    gum = GUM(query='stock market', period=1, date='2023-01-01')
    results = asyncio.run(gum.search(headless=True))

    print(results)
