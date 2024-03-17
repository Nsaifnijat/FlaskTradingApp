from . import db

class Coin(db.Model):
    __tablename__ = 'coins'

    id = db.Column(db.Integer, primary_key=True)
    kucoin_name = db.Column(db.String, unique=True)
    binance_name = db.Column(db.String)
    allow_trade = db.Column(db.Integer)
    bought_id = db.Column(db.String)
    trades = db.relationship('Trade', backref='coins', lazy=True, cascade='all, delete')

    def __repr__(self):
        return f"""{self.id}:{self.kucoin_name}:{self.binance_name}:{self.allow_trade}:{self.bought_id}"""
    def __str__(self):
        return f"""{self.id}:{self.kucoin_name}:{self.binance_name}:{self.allow_trade}:{self.bought_id}"""


class Trade(db.Model):
    __tablename__ = 'trades'

    id = db.Column(db.String, primary_key=True)
    # coin_id = db.Column(db.Integer, db.ForeignKey('coins.id', ondelete='CASCADE'), nullable=False)
    symbol = db.Column(db.String, db.ForeignKey('coins.kucoin_name', ondelete='CASCADe'), nullable=False)
    opType = db.Column(db.String)
    type = db.Column(db.String)
    side = db.Column(db.String)   
    price = db.Column(db.String)
    size = db.Column(db.String)
    funds = db.Column(db.String)
    dealFunds = db.Column(db.String)
    dealSize = db.Column(db.String)
    fee = db.Column(db.String)
    feeCurrency = db.Column(db.String)
    stp = db.Column(db.String)
    stop = db.Column(db.String)
    stopTriggered = db.Column(db.Integer)
    stopPrice = db.Column(db.String)
    timeInForce = db.Column(db.String)
    postOnly = db.Column(db.Integer)
    hidden = db.Column(db.Integer)
    iceberg = db.Column(db.Integer)
    visibleSize = db.Column(db.String)
    cancelAfter = db.Column(db.Integer)
    channel = db.Column(db.String)
    clientOid = db.Column(db.String)
    remark = db.Column(db.String)
    tags = db.Column(db.String)
    isActive = db.Column(db.Integer)
    cancelExist = db.Column(db.Integer)
    createdAt = db.Column(db.BigInteger)
    tradeType = db.Column(db.String)
    # trade_pairs = db.relationship('TradePair', backref='trades', lazy=True)

    def __repr__(self):
        return f'ID: {self.id}, Symbol: {self.symbol}, Side: {self.side}'

class TradePair(db.Model):
    __tablename__ = 'trade_pairs'

    # TODO: add coin name for easy filtering from dashboard

    id = db.Column(db.Integer, primary_key=True)
    buy_id = db.Column(db.String, db.ForeignKey('trades.id'), nullable=False)
    sell_id = db.Column(db.String, db.ForeignKey('trades.id'), nullable=False)
    profit = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f"{self.buy_id}:{self.sell_id}:{self.profit}"


class BeckTestTrade(db.Model):
    __tablename__ = 'beck_test_trades'

    # TODO: add coin name for easy filtering from dashboard
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String, nullable=False)
    buy_time = db.Column(db.String, nullable=False)
    sell_time = db.Column(db.String, nullable=False)
    profit = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f"{self.id}:{self.symbol}:{self.profit}"