"""stock_data — obtenção e salvamento de séries temporais de ações

Este módulo baixa dados históricos de ações usando a biblioteca `yfinance`
e os converte em um DataFrame do `pandas`. Ao ser executado, o módulo salva
duas saídas no diretório de execução:

 - ``data.csv`` : CSV com o histórico obtido via yfinance.
 - ``dados.txt`` : representação em texto do DataFrame (para inspeção rápida).

Principais pontos
 - Ticker usado por padrão: ``PETR4.SA`` (alterar diretamente no código se desejar).
 - Período configurado como ``period='3y'`` e início em ``start='2023-1-1'``.
 - Dependências: ``yfinance`` e ``pandas``.

"""

import sys
from datetime import datetime
import yfinance as yf
from yfinance import exceptions as yf_exceptions
import pandas as pd

pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)

stocks = ['PETR4.SA', 'GGB']
dat = yf.Tickers(stocks)

try:
    end_date = datetime.now()
    temporalSeries = dat.history(period='5y', end=end_date)
    temporalSeries.to_csv('data.csv')

except yf_exceptions.YFRateLimitError as e:
    print(e)
    sys.exit()
except yf_exceptions.YFException as e:
    print(e)
    sys.exit()

with open('dados.txt', 'w', encoding='UTF-8') as file:
    file.write(f'{temporalSeries}')
