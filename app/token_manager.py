import os
import json
import threading
import time
import logging
import requests
from cachetools import TTLCache
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

AUTH_URL = os.getenv("AUTH_URL", "http://jwt.thug4ff.com/token")

CACHE_DURATION = timedelta(hours=7).seconds
TOKEN_REFRESH_THRESHOLD = timedelta(hours=6).seconds

class TokenCache:
    def __init__(self, servers_config):
        self.cache = TTLCache(maxsize=100, ttl=CACHE_DURATION)
        self.last_refresh = {}
        self.lock = threading.Lock()
        self.session = requests.Session()
        self.servers_config = servers_config

    def get_tokens(self, server_key):
        with self.lock:
            now = time.time()

            # 🔥 Agar cache me hai → direct return (NO WAIT)
            if server_key in self.cache:
                return self.cache[server_key]

            # 🔥 First time load (blocking once only)
            self._refresh_tokens(server_key)
            self.last_refresh[server_key] = now

            return self.cache.get(server_key, [])

    # 🔥 FAST PARALLEL TOKEN FETCH
    def _fetch_single(self, user):
        try:
            params = {'uid': user['uid'], 'password': user['password']}
            response = self.session.get(AUTH_URL, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if not data.get("error") and data.get("token"):
                    return data["token"]

        except Exception as e:
            logger.error(f"Token fetch failed for {user['uid']}: {e}")

        return None

    def _refresh_tokens(self, server_key):
        try:
            creds = self._load_credentials(server_key)

            if not creds:
                self.cache[server_key] = []
                return

            tokens = []

            # 🔥 PARALLEL EXECUTION (FAST)
            with ThreadPoolExecutor(max_workers=5) as executor:
                results = executor.map(self._fetch_single, creds)

            tokens = [t for t in results if t]

            if tokens:
                self.cache[server_key] = tokens
                logger.info(f"✅ Tokens loaded: {len(tokens)} for {server_key}")
            else:
                logger.warning(f"⚠️ No tokens fetched, using fallback")

                # 🔥 FALLBACK TOKEN (IMPORTANT)
                fallback = os.getenv("FALLBACK_TOKEN")
                if fallback:
                    self.cache[server_key] = [fallback]
                else:
                    self.cache[server_key] = []

        except Exception as e:
            logger.error(f"Critical error: {e}")
            self.cache[server_key] = []

    def _load_credentials(self, server_key):
        try:
            config_data = os.getenv(f"{server_key}_CONFIG")
            if config_data:
                return json.loads(config_data)

            config_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'config',
                f'{server_key.lower()}_config.json'
            )

            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    return json.load(f)

            logger.warning(f"No config found for {server_key}")
            return []

        except Exception as e:
            logger.error(f"Error loading credentials: {e}")
            return []

# 🔥 UPDATED HEADERS (OB52 FIX)
def get_headers(token: str):
    return {
        'User-Agent': "Dalvik/2.1.0 (Linux; Android 9)",
        'Connection': "Keep-Alive",
        'Accept-Encoding': "gzip",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Unity-Version": "2018.4.11f1",
        "X-GA": "v1 1",
        "ReleaseVersion": "OB52"  # 🔥 IMPORTANT FIX
    }
