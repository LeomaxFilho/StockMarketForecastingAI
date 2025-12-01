"""Obtenção e salvamento de séries temporais de ações.

Este módulo baixa dados históricos utilizando a biblioteca `yfinance` e salva
um arquivo CSV por ticker listado em `stock_market_forecasting_ai/data/tickers.json`.
Cada CSV é gravado em `stock_market_forecasting_ai/data/data_<TICKER>.csv`.

Principais pontos
- Período padrão usado no script: ``period='5y'``. O parâmetro ``end`` é
    definido como ``datetime.now()`` no momento da execução.
- Dependências: ``yfinance`` e ``pandas``.
- Em caso de erro específico do `yfinance` (por exemplo, limite de taxa), o
    erro é impresso e o processo é encerrado para evitar resultados incompletos.

Função pública
- ``ticker_crawler(file_locate: str, period: str) -> None``
    - Parâmetros:
        - ``file_locate``: caminho para a pasta que contém ``tickers.json`` e onde
            os CSVs serão salvos (ex.: ``stock_market_forecasting_ai/data``).
        - ``period``: string de período aceita por ``yfinance`` (ex.: ``'1y'``,
            ``'5y'``).

Exemplo de execução
    Execute o módulo como script para baixar os dados dos tickers configurados:

            python3 -m stock_market_forecasting_ai.src.data_crawler.stock_data

Observações e recomendações
- Para facilitar testes e reutilização, considere refatorar a lógica para
    expor funções que retornem ``DataFrame`` em vez de escrever diretamente em
    disco, e adicione logging e política de retry para falhas de rede.

"""

import sys
import json
from datetime import datetime
import yfinance as yf
from yfinance import exceptions as yf_exceptions
import pandas as pd

def ticker_crawler(file_locate : str, time_period : str) -> None:

    """Baixa séries temporais para os tickers listados e salva CSVs.

    Lê um arquivo JSON contendo uma lista de tickers em ``{file_locate}/tickers.json``
    e para cada ticker obtém o histórico via ``yfinance.Ticker.history`` usando o
    parâmetro ``period`` informado e ``end=datetime.now()``. O DataFrame resultante
    é salvo como CSV em ``{file_locate}/data_<TICKER>.csv``.

    Parâmetros
    ----------
    file_locate : str
            Caminho para a pasta que contém ``tickers.json`` e onde os CSVs serão
            gravados (ex.: ``'stock_market_forecasting_ai/data'``).
    period : str
            Período a ser passado para ``yfinance`` (ex.: ``'1y'``, ``'5y'``).

    Observações
    -----------
    - A função grava diretamente em disco. Para facilitar testes e reuso, é
        recomendável refatorar para retornar o ``DataFrame`` ao invés de sempre
        escrever o arquivo.

    Exemplo
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
