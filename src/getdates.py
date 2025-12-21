import json
import os

import numpy as np
import pandas as pd

path = f'{os.path.dirname(os.path.abspath(__file__))}'

tickers = pd.read_json(f'{path}/../data/tickers.json').to_dict()

for k, ticker in tickers[0].items():
    df = pd.read_csv(f'{path}/../data/data_{ticker}.csv')

    df['Variacao'] = (df['Open'] - df['Close']) / df['Open']

    higher = np.where(np.abs(df['Variacao']) > 0.05)  # Buscar um numero bom para isso
    df_higher = df.loc[higher]
    df_higher['Date'].head()

    to_save = df_higher['Date'].to_list()

    with open(f'{path}/../data/{ticker}_date.json', 'w') as file:
        json.dump(to_save, file, indent=4, ensure_ascii=False, default=str)
