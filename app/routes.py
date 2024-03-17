from threading import Thread

from flask import make_response, request
from flask import current_app as app

from .bot import run_bot
from .models import Coin, TradePair, Trade
from .bot.crud import clear_db, get_trades, clear_coins, get_backtest_trades
from .bot.crud import insert_coin, update_coin, clear_coins_bought_id, insert_trade
from .bot.helper import CoinHelper


@app.route('/')
def index():
    return make_response('; '.join([str(x) for x in Coin.query.all()]), 200)


@app.route('/list_trades')
def list_trades():
    return make_response('; '.join([str(x) for x in get_trades()]))


@app.route('/list_backtest_trades')
def list_backtest_trades():
    return make_response('; '.join([str(x) for x in get_backtest_trades()]))


@app.route('/insert_coins')
def insert_coins():
    coins = request.get_json().get('coins')
    for coin in coins:
        insert_coin(**coin)
    return make_response('SDA', 200)


@app.route('/test_update')
def update_c():
    update_coin('', 'ADA-USDT')
    return make_response('SDA', 200)


@app.route('/list_tps')
def list_tps():
    return make_response('; '.join([str(x) for x in TradePair.query.all()]), 200)


@app.route('/insert_tp')
def insert_pt():
    coins = request.get_json().get('items')
    for coin in coins:
        insert_trade(**coin)
    return make_response('SDA', 200)


@app.route('/init_bot')
def init_bot():
    t1 = Thread(target=run_bot, daemon=True)
    t1.start()
    return make_response('Bot started successfuly!', 200)


############# TEST ############
@app.route('/backtest')
def backtest_bot():
    run_bot(mode='backtest')
    return make_response('Backtest Run !', 200)


@app.route('/clear_trades_from_db')
def clear_trades():
    clear_db()
    return make_response('; '.join([str(x) for x in Trade.query.all()]), 200)


@app.route('/clear_database')
def clear_database():
    clear_coins()
    return make_response('; '.join([str(x) for x in Coin.query.all()]), 200)




from .bot.Action.KuCoinTrade import MarketAction
from config import KucoinConfig
import time


@app.route('/test_buy_sell')
def test_buy_sell():
    config = KucoinConfig()
    config['mode'] = 'live'
    for coin in Coin.query.all():
        try:
            actions = MarketAction('', config, coin)
            actions.create_order('buy', funds=10)
            time.sleep(1)
            actions.create_order('sell', size=actions.trade_amount)
        except Exception as e:
            print(coin, e)
        break
    return make_response('; '.join([str(x) for x in Trade.query.all()]), 200)


@app.route('/sell_all')
def sell_all():
    """Exchange all coins to USDT"""
    config = KucoinConfig()
    MarketAction.init_class_variables(config)
    MarketAction.sell_everything()
    clear_coins_bought_id()
    return make_response('Sold', 200)


@app.route('/get_balance')
def return_balance():
    """Return Total Balance of the Trade Account in USDT"""
    if not MarketAction.user:
        config = KucoinConfig()
        MarketAction.init_class_variables(config)
    balance = MarketAction.calculate_total_balance()
    return make_response(str(balance), 200)


####################  Vision ###################

@app.route('/buy_coin')
def buy():
    config = KucoinConfig()
    config['mode'] = 'live'
    coin = CoinHelper(request.args.get('kucoin_name'))

    actions = MarketAction('', config, coin)
    actions.create_order('buy', funds=10)

    data = actions.buy_order_id + ',' + str(actions.trade_amount)
    return make_response(data, 200)


@app.route('/sell_coin')
def sell():
    config = KucoinConfig()
    config['mode'] = 'live'

    coin = CoinHelper(request.args.get('kucoin_name'),
                      request.args.get('bought_id'),
                      request.args.get('trade_amount'),
                      )

    actions = MarketAction('', config, coin)

    print(coin.trade_amount, coin.bought_id)

    try:
        actions.buy_order_id = coin.bought_id
        actions.trade_amount = coin.trade_amount
        actions.create_order('sell', size=actions.trade_amount)
        return make_response('true', 200)
    except:
        return make_response('false', 200)
