import time
from decimal import Decimal
import pandas as pd
import numpy as np

from threading import Thread

from kucoin.client import Trade, Market, User
from app.bot.crud import insert_trade, insert_tp, update_coin, backtest_insert_tp
from app.bot.helper import clean_trade_dict


class MarketAction(Thread):
    user = None
    market = None
    client = None
    api_key = ''
    api_secret = ''
    api_passphrase = ''

    start_balance = None
    allow_trade = True
    config = None

    backtest_profit = 0  # TODO: remove

    def __init__(self, stream, config, coin):
        Thread.__init__(self)
        MarketAction.init_class_variables(config)

        self.coin = coin
        self.symbol = coin.kucoin_name
        self.funds = config['funds']
        self.stream = stream
        self.coef = config['coef']
        self.window = config['window']

        self.quoteIncrement = self.calculate_increment()  # TODO: correct precision
        self.order_ids = []
        self.buy_order_id = ''
        self.stop_loss_order_id = ''
        self.trade_amount = ''
        self.live_trade = config['mode'] == 'live'
        self.backtest = config['mode'] == 'backtest'
        self.stop = False
        self.indicator = ''

    def run(self):
        self.indicator = Indicator(self.stream.data, self.buy_order_id)

        if self.live_trade:
            print(f'Trading in Live for {self.symbol}')
            self.initialize_trade_info(self.coin)

            while not self.stop:
                if self.stream.check_for_action:
                    self.indicator.is_bought = self.buy_order_id  # update buy status
                    self.indicator.data = self.stream.data

                    # if self.buy_order_id:
                    #     print(self.symbol, ': MarketAction buy_order_id', self.buy_order_id, 'Indicator:', self.indicator.is_bought)

                    # print(f'Action -> Checking for action! {self.symbol}')
                    if self.indicator.buy() and self.allow_trade:

                        self.create_order('buy', funds=self.funds)

                    elif self.indicator.sell():
                        self.create_order('sell', size=self.trade_amount)

                    self.stream.check_for_action = False
                time.sleep(0.5)

        elif self.backtest:
            print('Back testing bot')
            while not self.stop:
                if self.stream.check_for_action:
                    self.indicator.data = self.stream.data
                    self.indicator.is_bought = self.buy_order_id  # update buy status

                    # print(f'Action -> Checking for action! {self.symbol}')
                    if self.indicator.buy() and self.allow_trade:
                        self.backtest_create_order('buy', funds=self.funds)

                    elif self.indicator.sell():
                        self.backtest_create_order('sell', funds=self.funds)
                        print('backtest_profit:', MarketAction.backtest_profit)

                    self.stream.check_for_action = False

        print('Action Thread Stopped!')

    def create_order(self, side, **kwargs):
        try:
            if side == 'buy':
                order_data = self.client.create_market_order(self.symbol, side, **kwargs)
                order_id = order_data.get('orderId')
                print(f'{side} {self.symbol}, order_id: {order_id}')

            if side == 'sell':
                stop_executed = False
                if self.stop_loss_order_id:  # Check if stop loss was executed
                    stop_loss_data = self.client.get_order_details(self.stop_loss_order_id)
                    if not stop_loss_data.get('isActive'):  # Check if stop loss was executed
                        print(f'Stop Loss Executed for {self.symbol}')
                        stop_executed = True
                        order_id = stop_loss_data.get('id')  # Set order Id for saving correct trade in database

                if not stop_executed:  # Create sell order and cancel stop loss
                    print(f'Stop Loss DID NOT Execute for {self.symbol}')
                    order_data = self.client.create_market_order(self.symbol, side, **kwargs)
                    order_id = order_data.get('orderId')
                    print(f'{side} {self.symbol}, order_id: {order_id}')
                    self.client.cancel_order(self.stop_loss_order_id)
                    self.stop_loss_order_id = ''

        except Exception as e:
            message = f'Exception (in create_order): {side} {self.symbol} {e}'
            print(message)

        else:
            if side == 'buy':
                while True:  # wait for order to fill
                    order_data = self.client.get_order_details(order_id)
                    if not order_data.get('isActive'):
                        trade_amount = order_data.get('dealSize')
                        self.trade_amount = self.round_trade_amount(trade_amount, self.quoteIncrement)
                        break
                    time.sleep(0.5)

                self.buy_order_id = order_id
                self.stop_loss_order_id = self.create_stop_loss(order_data)  # Create Stop Loss order

                # TODO: Monitor
                update_coin(kucoin_name=self.symbol, trade_id=self.buy_order_id)
                insert_trade(**clean_trade_dict(order_data))

            elif side == 'sell':
                while True:  # wait for order to fill
                    order_data = self.client.get_order_details(order_id)
                    if not order_data.get('isActive'):
                        break
                    time.sleep(0.5)

                # TODO: Monitor
                update_coin(kucoin_name=self.symbol, trade_id='')
                insert_trade(**clean_trade_dict(order_data))

                if self.buy_order_id:  # if sell trade has pair buy save in pairs
                    buy_id = self.buy_order_id
                    sell_id = order_id
                    profit = self.calculate_pair_profit(buy_id=buy_id, sell_id=sell_id)
                    insert_tp(buy_id=buy_id, sell_id=sell_id, profit=profit)

                self.buy_order_id = ''
                self.trade_amount = '0'
                self.update_trade_allowance()

    def create_stop_loss(self, data, coef=0.96):
        stop_price = float(data.get('dealFunds')) / float(data.get('dealSize')) * coef
        kwargs = {'symbol': self.symbol,
                  'side': 'sell',
                  'funds': self.trade_amount,
                  'stopPrice': stop_price,
                  }

        order_data = self.client.create_market_stop_order(**kwargs)
        stop_order_id = order_data.get('orderId')
        self.stop_loss_order_id = stop_order_id
        return stop_order_id

    def calculate_pair_profit(self, buy_id, sell_id):
        """ Calculates and returns relative profit in percentage"""
        sell_trade = self.client.get_order_details(sell_id)
        buy_trade = self.client.get_order_details(buy_id)

        total_profit = float(sell_trade.get('dealFunds')) - \
                       float(sell_trade.get('fee')) - \
                       float(buy_trade.get('dealFunds')) - \
                       float(buy_trade.get('fee'))

        relative_profit_perc = total_profit / float(buy_trade.get('dealFunds')) * 100
        return relative_profit_perc

    def calculate_increment(self):
        increments = {data.get('symbol'): data.get('quoteIncrement') for data in self.market.get_symbol_list()}
        return increments.get(self.symbol)

    def initialize_trade_info(self, coin):
        """If coin is bought get information about trade when initialising"""
        try:
            if coin.bought_id:
                order_data = self.client.get_order_details(coin.bought_id)
                if not order_data.get('isActive'):
                    trade_amount = order_data.get('dealSize')
                    trade_amount = self.round_trade_amount(trade_amount, self.quoteIncrement)
            else:  # if is not bought make trade amount empty string
                trade_amount = ''
        except Exception as e:
            self.buy_order_id = ''
            self.trade_amount = '0'
            message = f'Exception in loading Trade info from CSV for {self.symbol}: {e}'
            if '400100' not in str(e):  # if different error than: 'order not exist'
                print(message)
        else:
            if trade_amount:
                self.buy_order_id = coin.bought_id
                self.trade_amount = trade_amount

    def backtest_create_order(self, side, **kwargs):
        print('backtest_create_order')
        if side == 'buy':
            print('--------------- buy')
            self.buy_order_id = 'buy_id'
            self.backtest_buy_price = self.stream.data.Close.iloc[-1]
            self.backtest_buy_time = self.stream.data.index[-1]

        if side == 'sell':
            print('--------------- sell')

            sell_price = self.stream.data.Close.iloc[-1]
            relative_profit_perc = (sell_price / self.backtest_buy_price - 1.002) * 100
            MarketAction.backtest_profit += relative_profit_perc
            # print(self.symbol, relative_profit_perc)

            data_kwargs = {'symbol': self.symbol,
                           'buy_time': self.backtest_buy_time,
                           'sell_time':self.stream.data.index[-1],
                           'profit': relative_profit_perc,
                           }
            backtest_insert_tp(**data_kwargs)

            self.buy_order_id = ''
            self.backtest_buy_time = ''
            self.backtest_buy_price = 0

    @staticmethod
    def round_trade_amount(funds, increment):
        # use maximum of '0.0001' and value returned from Kucoin as values got from Kucoin are incorrect 
        increment = max(increment, '0.0001')
        return str(Decimal(funds).quantize(Decimal(increment), rounding='ROUND_DOWN'))

    @classmethod
    def sell_everything(cls, quote='USDT', account_type='trade'):
        price_dict = dict()
        for data in cls.market.get_all_tickers().get('ticker'):
            symbol = data.get('symbol')
            price_dict[symbol] = float(data.get('sell'))

        account_balance = cls.user.get_account_list(account_type=account_type)
        for data in account_balance:
            currency = data.get('currency')
            if currency != quote:
                if f'{currency}-{quote}' in price_dict.keys():
                    symbol = f'{currency}-{quote}'
                    price = price_dict[symbol]
                    balance = float(data.get('balance')) * price
                    if balance > 5:
                        cls.client.create_market_order(symbol, 'sell', funds=cls.round_trade_amount(balance, '0.001'))
                        print(f'Sold {symbol}')
                elif f'{quote}-{currency}' in price_dict.keys():
                    symbol = f'{quote}-{currency}'
                    price = price_dict[symbol]
                    balance = float(data.get('balance')) / price
                    if balance > 5:
                        cls.client.create_market_order(symbol, 'buy', size=cls.round_trade_amount(balance, '0.001'))
                        print(f'Sold {symbol}')

        print('Done Selling!')

    @classmethod
    def calculate_total_balance(cls, quote='USDT', account_type='trade'):
        price_dict = dict()
        for data in cls.market.get_all_tickers().get('ticker'):
            symbol = data.get('symbol')
            price_dict[symbol] = float(data.get('sell'))

        account_balance = cls.user.get_account_list(account_type=account_type)
        balance = 0
        for data in account_balance:
            currency = data.get('currency')
            if currency != quote:
                if f'{currency}-{quote}' in price_dict.keys():
                    price = price_dict[f'{currency}-{quote}']
                    balance += float(data.get('balance')) * price
                elif f'{quote}-{currency}' in price_dict.keys():
                    price = price_dict[f'{quote}-{currency}']
                    balance += float(data.get('balance')) / price
            else:
                balance += float(data.get('balance'))
        message = f'Total Balance is {balance}'
        return balance

    @classmethod
    def update_trade_allowance(cls):
        """check if balance is not very low to allow further trading"""
        cls.allow_trade = cls.calculate_total_balance() > cls.start_balance * 0.8
        # TODO: change allow_trade coefficient to be included in config file

    @classmethod
    def init_class_variables(cls, config):
        """Initialize class variables on the first time"""
        if not MarketAction.user:
            cls.api_key = config['api_key']
            cls.api_secret = config['api_secret']
            cls.api_passphrase = config['api_passphrase']
            cls.user = User(cls.api_key, cls.api_secret, cls.api_passphrase)
            cls.market = Market(cls.api_key, cls.api_secret, cls.api_passphrase)
            cls.client = Trade(cls.api_key, cls.api_secret, cls.api_passphrase)

            cls.start_balance = cls.calculate_total_balance()
            cls.config = config
            print('MarketAction Class Variables Successfully Initialized!')


class Indicator:
    def __init__(self, data, is_bought):
        self.atr_period = 14
        self.ma_len = 5
        self.ma_source = 'Close'
        self.atr_coef = 3

        self.is_bought = is_bought
        self.stop_price = -np.inf
        self.high_val = -np.inf
        self.data = data

    def atr_ema(self):
        diff1 = self.data['High'] - self.data['Low']
        diff2 = self.data['High'] - self.data['Low'].shift(periods=1)
        diff3 = self.data['Close'] - self.data['Low'].shift(periods=1)

        ATR = pd.DataFrame({'diff1': diff1, 'diff2': diff2, "diff3": diff3})
        ATR['max'] = ATR.max(axis=1)
        ema = ATR.ta.ema(close='max', length=self.atr_period)
        return ema

    def buy(self):
        self.data.loc[:, 'MA'] = self.data.ta.sma(close=self.ma_source, length=self.ma_len)
        self.data.loc[:, 'ATR'] = self.atr_ema()
        self.data.loc[:, 'buy_price'] = self.data['MA'].shift(periods=1) + self.data['ATR']

        if self.is_bought:  # TODO: Move 'if' outside buy function
            self.high_val = max(self.high_val, self.data['Close'].iloc[-1])
            self.stop_price = self.high_val - self.atr_coef * self.data['ATR'].iloc[-1]
        else:
            self.stop_price = -np.inf
            self.high_val = -np.inf

        ######## Buy ############
        self.data.loc[:, 'ind_buy'] = self.data['Close'] > self.data['buy_price']
        # print((self.data['Close'] > self.data['buy_price']).iloc[0], self.data['Close'].iloc[0], self.data['buy_price'].iloc[0])

        ##### EMA ###########
        self.data.loc[:, 'EMA20'] = self.data.ta.sma(close='Close', length=20)
        self.data.loc[:, 'EMA50'] = self.data.ta.sma(close='Close', length=50)
        ind_buy_ema = self.data['EMA50'] < self.data['EMA20'] + self.data['ATR']
        self.data.loc[:, 'ind_buy'] *= ind_buy_ema

        ######### VOLUME ##########
        self.data.loc[:, 'Vol_SMA24'] = self.data.ta.sma(close='Volume', length=24)
        ind_buy_vol = self.data['Volume'] > 1.5 * self.data['Vol_SMA24']
        self.data.loc[:, 'ind_buy'] *= ind_buy_vol

        buy = self.data.loc[:, 'ind_buy'].iloc[-1]

        # b_t1 = (self.data['Close'] > self.data['buy_price']).iloc[-1]
        # if buy:
        #     print(f"""Ping, is_bought -{self.is_bought}-, Close>Buy -{b_t1}-, buy {buy},
        #         Buy Price {self.data['buy_price'].iloc[-1]},
        #         Close {self.data['Close'].iloc[-1]}""")

        if buy and not self.is_bought:
            return True
        return False

    def sell(self):
        buy_price = self.data['buy_price'].iloc[-1]
        sell = self.stop_price > self.data['Low'].iloc[-1] and buy_price > self.data['Low'].iloc[-1]
        if sell and self.is_bought:
            return True
        return False


# def indicator_buy(self):
#     good_trend = self.trend_v1()  # check if trend is up or flat
#     up_candles = self.stream.data['HA_Close'] > self.stream.data['HA_Open']
#
#     try:  # see if Trades are available
#         indicator = (self.stream.data['Volume'] > self.coef * self.stream.data['EMA60_Volume']) * (
#                 self.stream.data['Trades'] > self.coef * self.stream.data['EMA60_Trades'])
#     except Exception:
#         indicator = self.stream.data['Volume'] > self.coef * self.stream.data['EMA60_Volume']
#
#     indicator *= good_trend * up_candles
#     buy = indicator.iloc[-self.window:].sum() == self.window
#     #         indicator = indicator.rolling(window=window).apply(lambda x: np.sum(x) >= window).fillna(0)
#     return buy
#
# def trend_v1(self):
#     good_trend = self.stream.data['EMA50'].rolling(window=60).apply(
#         lambda x: (x[-1] - x[0]) / x[0] > -10e-3).fillna(0)
#     return good_trend
#
# def trend_v2(self):
#     EMA5 = self.stream.data['EMA5']
#     EMA9 = self.stream.data['EMA9']
#     EMA12 = self.stream.data['EMA12']
#     good_trend = EMA12 < EMA9 < EMA5
#     return good_trend
#
# def indicator_sell(self):
#     lose_momentum = self.lose_momentum_v2()
#     if lose_momentum:
#         return True
#     return False
#
# def lose_momentum_v1(self):
#     lose_momentum = self.stream.data['HA_Close_slow'].iloc[-1] < self.stream.data['HA_Open_slow'].iloc[-1]
#     return lose_momentum
#
# def lose_momentum_v2(self):
#         EMA5 = self.stream.data['EMA5'].iloc[-1]
#         EMA9 = self.stream.data['EMA9'].iloc[-1]
#         EMA12 = self.stream.data['EMA12'].iloc[-1]
#         lose_momentum = EMA12 > EMA9 and EMA12 > EMA5
#         return lose_momentum