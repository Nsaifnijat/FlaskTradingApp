import gc
import json
import logging
import websocket
import time
from datetime import datetime, timedelta, timezone
import pandas as pd
import pandas_ta as ta

from binance.client import Client
from threading import Thread, Event


class BinanceDataStream(Thread):
    def __init__(self, config, coin):
        Thread.__init__(self)
        self.symbol = coin.binance_name
        self.interval_fast = config['interval_fast']
        self.interval_slow = config['interval_slow']
        self.api_key = config['api_key']
        self.api_secret = config['api_secret']
        self.api_passphrase = config['api_passphrase']

        self.socket = "wss://stream.binance.com:9443/ws/{}@kline_{}".format(self.symbol.lower(), self.interval_fast)
        self.stopped = Event()

        self.data = None
        self.initial_collect_data()
        self.check_for_action = False

        self.live_trade = config['mode'] == 'live'
        self.backtest = config['mode'] == 'backtest'

    def run(self):
        logging.info(f'{self.symbol}: Started Binance Data Stream!')

        def on_message(ws, message):
            """Adds stream candlestick data to the dataframe"""
            json_message = json.loads(message)
            if json_message['k']['x']:  # if candle is closed
                try:
                    self.record_data(json_message['k'])
                    self.check_for_action = True
                except Exception as e:
                    print('Exception in Binance Data Stream:', self.symbol, datetime.now(), e)
            else:
                self.check_for_action = False

        def on_open(ws):
            message = f'{self.symbol}: Binance Websocket Connection Established!'
            print(message)
            logging.info(message)

        if self.live_trade:
            while True:
                try:
                    websocket.enableTrace(False)
                    ws = websocket.WebSocketApp(self.socket, on_message=on_message, on_open=on_open)
                    ws.run_forever(skip_utf8_validation=True, ping_interval=10, ping_timeout=8)
                except Exception as e:
                    gc.collect()
                    message = f"{self.symbol}: Binance Websocket connection Error: {e}"
                    print(message)
                    logging.debug(message)

                message = f"{self.symbol}: Reconnecting Binance Websocket After 5 Sec!"
                print(message)
                logging.debug(message)
                time.sleep(5)

        elif self.backtest:
            # get historical data for period, feed one by one\
            self.initial_collect_data(1)
            whole_data = self.data.copy()
            print(self.symbol, 'Total data points in whole_data: ', len(whole_data))
            for i in range(200, len(whole_data)):
                self.data = whole_data.iloc[i-200:i]
                self.check_for_action = True

                while self.check_for_action:  # wait fake trade to happen and only after feed next candle
                    pass
            print(self.symbol, 'Finished simulation')

    def binance_historical_data(self, test_days=0):
        print('binance_historical_data')
        client = Client('', '', tld='com')

        if not test_days:
            fromdate = str(datetime.utcnow() - timedelta(days=2))
        else:
            fromdate = str(datetime.utcnow() - timedelta(days=test_days))

        klines = client.get_historical_klines(self.symbol, self.interval_fast, fromdate)
        df = pd.DataFrame(klines,
                          columns=['DateTime', 'Open', 'High', 'Low', 'Close', 'Volume', 'closeTime',
                                   'quoteAssetVolume',
                                   'Trades', 'takerBuyBaseVol', 'takerBuyQuoteVol', 'ignore'])

        df.index = pd.to_datetime(df.DateTime, unit='ms')
        column_names = ['Open', 'High', 'Low', 'Close', 'Volume', 'Trades']
        df = df.reindex(columns=column_names)
        self.data = df.astype(float, errors='ignore').iloc[:-1]

    # def HA_slow(self):
    #     print('HA_slow')
    #
    #     window = int(int(self.interval_slow[:-1]) / int(self.interval_fast[:-1]))
    #
    #     self.data['HA_Close_slow'] = (self.data['Open_slow'] + self.data['High_slow'] + self.data['Low_slow'] +
    #                                   self.data['Close_slow']) / 4
    #     idx = self.data.index.name
    #
    #     self.data.reset_index(inplace=True)
    #
    #     for i in range(0, len(self.data)):
    #         if i < 2 * window:
    #             self.data.at[i, 'HA_Open_slow'] = (self.data.at[i, 'Open_slow'] + self.data.at[i, 'Close_slow']) / 2
    #         else:
    #             self.data.at[i, 'HA_Open_slow'] = (self.data.at[i - window, 'HA_Open_slow'] + self.data.at[
    #                 i - window, 'HA_Close_slow']) / 2
    #     if idx:
    #         self.data.set_index(idx, inplace=True)
    #
    #     self.data['HA_High_slow'] = self.data[['HA_Open_slow', 'HA_Close_slow', 'High_slow']].max(axis=1)
    #     self.data['HA_Low_slow'] = self.data[['HA_Open_slow', 'HA_Close_slow', 'Low_slow']].min(axis=1)
    #     return self.data

    # def HA_fast(self):
    #     print('HA_fast')
    #
    #     self.data['HA_Close'] = (self.data['Open'] + self.data['High'] + self.data['Low'] + self.data['Close']) / 4
    #     idx = self.data.index.name
    #     self.data.reset_index(inplace=True)
    #
    #     for i in range(0, len(self.data)):
    #         if i == 0:
    #             self.data.at[i, 'HA_Open'] = (self.data.at[i, 'Open'] + self.data.at[i, 'Close']) / 2
    #         else:
    #             self.data.at[i, 'HA_Open'] = (self.data.at[i - 1, 'HA_Open'] + self.data.at[i - 1, 'HA_Close']) / 2
    #     if idx:
    #         self.data.set_index(idx, inplace=True)
    #
    #     self.data['HA_High'] = self.data[['HA_Open', 'HA_Close', 'High']].max(axis=1)
    #     self.data['HA_Low'] = self.data[['HA_Open', 'HA_Close', 'Low']].min(axis=1)
    #     return self.data

    # def add_indicators(self):
    #     print('add_indicators')
    #     self.data['EMA5'] = self.data.ta.ema(close='Close', length=5)
    #     self.data['EMA9'] = self.data.ta.ema(close='Close', length=9)
    #     self.data['EMA10'] = self.data.ta.ema(close='Close', length=10)
    #     self.data['EMA12'] = self.data.ta.ema(close='Close', length=12)
    #     self.data['EMA50'] = self.data.ta.ema(close='Close', length=50)
    #     self.data['EMA10_Volume'] = self.data.ta.ema(close='Volume', length=10)
    #     self.data['EMA60_Volume'] = self.data.ta.ema(close='Volume', length=60)
    #     self.data['EMA10_Trades'] = self.data.ta.ema(close='Trades', length=10)
    #     self.data['EMA60_Trades'] = self.data.ta.ema(close='Trades', length=60)

    def initial_collect_data(self, days=0):
        print('initial_collect_data')

        self.binance_historical_data(days)  # get historical data when starting the bot not to wait stream
        # self.add_indicators()
        # self.add_slow_data()
        # self.HA_fast()
        # self.HA_slow()

    def record_data(self, message):
        print('record_data')

        # print('Record Data!')
        date_time = datetime.fromtimestamp(message['t'] // 1e3, tz=timezone.utc).replace(second=0)
        row = pd.Series({
            'Open': float(message['o']),
            'High': float(message['h']),
            'Close': float(message['c']),
            'Low': float(message['l']),
            'Volume': float(message['v']),
            'Trades': float(message['n'])},
            name=date_time)

        self.data = self.data.append(row)
        self.data = self.data.iloc[-200:]
        # self.add_indicators()
        # self.add_slow_data()
        # self.HA_fast()
        # self.HA_slow()

    # def add_slow_data(self):
    #     print('add_slow_data')
    #
    #     try:
    #         window = int(int(self.interval_slow[:-1]) / int(self.interval_fast[:-1]))
    #
    #         self.data['Open_slow'] = self.data.Open
    #         shift_data = self.data.shift(1 - window).fillna(method='ffill')
    #         self.data['Close_slow'] = shift_data.Close
    #         self.data['High_slow'] = shift_data.High.rolling(window=window).apply(lambda x: max(x))
    #         self.data['Low_slow'] = shift_data.Low.rolling(window=window).apply(lambda x: min(x))
    #     except Exception as e:
    #         print(e)
