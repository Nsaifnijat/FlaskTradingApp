import os
from typing import Any


class Config(object):
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'sulertia'
    LOCAL_DB = os.environ.get('LOCAL_PG','')
    SQLALCHEMY_DATABASE_URI = LOCAL_DB or os.environ.get('DATABASE_URL', '').replace(
        'postgres://', 'postgresql://') \
        or 'sqlite:///bot/database.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class KucoinConfig(object):
    api_key = os.environ.get('API_KEY')
    api_secret = os.environ.get('API_SECRET')
    api_passphrase = os.environ.get('API_PASSPHRASE')
    is_sandbox = False
    coef = 1.5
    window = 3
    funds = 10
    interval_fast = '1m'
    interval_slow = '15m'
    mode = 'live'

    def __getitem__(self, param):
        return getattr(self, param)

    def __setitem__(self, __name: str, __value: Any) -> None:
        setattr(self, __name, __value)
