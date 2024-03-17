import time

from .Data.DataStream import BinanceDataStream
from .Action.KuCoinTrade import MarketAction
from .Data.KucoinSymbols import load_kucoin_binance_symbols
from app.bot.crud import get_coins  # TODO: change to relative path
from config import KucoinConfig

def run_bot(mode='live'):
    """Mode can be live or backtest"""

    config = KucoinConfig()
    config['mode'] = mode

    # TODO: change info to something more robust for accessing threads
    info = dict()

    coin_list = get_coins()
    print("Total Symbols in the list: ", len(coin_list))

    for coin in coin_list:
        try:
            if coin.allow_trade:
                stream = BinanceDataStream(config, coin)
                stream.start()

                actions = MarketAction(stream, config, coin)
                actions.start()
                info[coin.kucoin_name] = {'stream': stream, 'actions': actions}
        except Exception as e:
            print(e)
