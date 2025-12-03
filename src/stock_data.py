"""Stock time series retrieval and CSV export.

This module downloads historical stock data using the `yfinance` package and
writes one CSV file per ticker listed in `tickers.json` inside the specified
data directory. Output files follow the pattern `data_<TICKER>.csv` and are
saved in the same folder as the input `tickers.json`.

Key points
- Example/default period used in the code: ``time_period='5y'``. The ``end``
  parameter is set to ``datetime.now()`` when requesting historical data.
- Dependencies: ``yfinance`` and ``pandas``.
- On `yfinance` specific errors (for example, rate limiting) the error is
  printed and the process exits to avoid partial or inconsistent results.

Public API
- ``ticker_crawler(file_locate: str, time_period: str) -> None``
  - Parameters:
    - ``file_locate``: path to the folder that contains ``tickers.json`` and
      where CSV files will be written (for example
      ``'stock_market_forecasting_ai/data'``).
    - ``time_period``: period string accepted by ``yfinance`` (for example
      ``'1y'``, ``'5y'``).

Usage example
    Run the module as a script to download data for the configured tickers:

        python3 -m stock_market_forecasting_ai.src.data_crawler.stock_data

Notes and recommendations
- For easier testing and reuse, consider refactoring to return pandas
  ``DataFrame`` objects instead of always writing files to disk, and add
  logging plus retry/backoff policies for network-related failures.
"""

import json
import sys
from datetime import datetime

import pandas as pd
import yfinance as yf
from yfinance import exceptions as yf_exceptions


def ticker_crawler(file_locate: str, time_period: str) -> None:
    """Download historical time series for listed tickers and save CSV files.

    Reads a JSON file containing a list of tickers from
    '{file_locate}/tickers.json'. For each ticker the function uses
    ``yfinance.Ticker.history`` with the provided ``time_period`` and
    ``end=datetime.now()`` to obtain historical data. The resulting DataFrame
    for each ticker is saved as a CSV file at
    '{file_locate}/data_<TICKER>.csv'.

    Parameters
    ----------
    file_locate : str
        Path to the directory containing ``tickers.json`` and where CSV files
        will be written (for example 'stock_market_forecasting_ai/data').
    time_period : str
        Period string to pass to ``yfinance`` (for example '1y', '5y').

    Notes
    -----
    - The current implementation writes CSV files directly to disk. For unit
      testing and better reuse it is recommended to refactor this function to
      return the DataFrame objects instead of always persisting them.
    - The function exits the process on certain `yfinance` errors (e.g.
      rate limiting); callers that require non-fatal handling should catch
      exceptions or modify the error/exit behavior.

    Example
    -------
    >>> ticker_crawler('stock_market_forecasting_ai/data', '5y')
    """

    pd.set_option('display.max_rows', None)
    pd.set_option('display.max_columns', None)

    with open(f'{file_locate}/tickers.json', 'r', encoding='UTF-8') as file:
        actions = json.load(file)

    for ticker in actions:
        dat = yf.Ticker(ticker)

        try:
            end_date = datetime.now()
            temporal_series = dat.history(period=time_period, end=end_date)
            temporal_series.to_csv(f'{file_locate}/data_{ticker}.csv')

        except yf_exceptions.YFRateLimitError as e:
            print(e)
            sys.exit()
        except yf_exceptions.YFException as e:
            print(e)
            sys.exit()


if __name__ == '__main__':
    LOCATE = '../data'
    PERIOD = '10y'
    # removed temporarily "RRRP3.SA"

    ticker_crawler(LOCATE, PERIOD)
