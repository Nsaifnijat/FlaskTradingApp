import pandas as pd
from kucoin.client import Market


def symbols_from_list(config, list_path, quote='USDT'):
    api_key = config['api_key']
    api_secret = config['api_secret']
    api_passphrase = config['api_passphrase']

    market = Market(api_key, api_secret, api_passphrase)
    with open(list_path, 'r') as f:
        coin_names = [name.rstrip('\n') for name in f.readlines()]

    base_names = [name[:-len(quote)] for name in coin_names if name.endswith(quote)]

    all_symbol_list = market.get_symbol_list()
    symbol_data = [s for s in all_symbol_list if s.get('baseCurrency') in base_names and s.get('quoteCurrency') == quote]
    symbol_list = [s.get('symbol') for s in symbol_data]

    return symbol_list, symbol_data


def load_kucoin_binance_symbols(config):
    df = pd.read_csv(config['symbol_csv_path'])
    df.drop_duplicates(inplace=True)
    return df
