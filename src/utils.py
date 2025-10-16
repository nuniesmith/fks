# src/utils.py

import requests
from datetime import datetime
import pytz

from config import DISCORD_WEBHOOK_URL
from database import Session, Trade

TIMEZONE = pytz.timezone('America/Toronto')

def log_trade(trade_info):
    session = Session()
    try:
        new_trade = Trade(
            date=datetime.now(TIMEZONE),
            action=trade_info['action'],
            symbols=trade_info.get('symbols', ''),
            prices=str(trade_info.get('prices', '')),
            quantities=str(trade_info.get('quantities', '')),
            sl=trade_info.get('sl'),
            tp=trade_info.get('tp')
        )
        session.add(new_trade)
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def send_discord_notification(webhook_url, message):
    if not webhook_url:
        raise Exception("Discord webhook URL not set")
    data = {"content": message}
    response = requests.post(webhook_url, json=data)
    if response.status_code != 204:
        raise Exception(f"Error sending Discord notification: {response.text}")