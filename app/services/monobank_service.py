import requests
from datetime import datetime, timedelta, timezone

class MonobankService:
    BASE_URL = "https://api.monobank.ua/personal"

    @staticmethod
    def get_client_info(token):
        headers = {'X-Token': token}
        resp = requests.get(f"{MonobankService.BASE_URL}/client-info", headers=headers)
        return resp.json() if resp.status_code == 200 else None

    @staticmethod
    def get_statement(token, account_id="0", days=3):
        headers = {'X-Token': token}
        now = datetime.now(timezone.utc)
        to_time = int(now.timestamp())
        from_time = int((now - timedelta(days=days)).timestamp())
        
        url = f"{MonobankService.BASE_URL}/statement/{account_id}/{from_time}/{to_time}"
        resp = requests.get(url, headers=headers)
        return resp.json() if resp.status_code == 200 else []
