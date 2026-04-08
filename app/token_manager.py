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

AUTH_URL = os.getenv("AUTH_URL", "http://jwt.thug4ff.xyz/token")

CACHE_DURATION = timedelta(hours=7).seconds
TOKEN_REFRESH_THRESHOLD = timedelta(hours=6).seconds


class TokenCache:
    def __init__(self, servers_config):
        self.cache = TTLCache(maxsize=100, ttl=CACHE_DURATION)
        self.last_refresh = {}
        self.lock = threading.Lock()
        self.session = requests.Session()
        self.servers_config = servers_config

    # 🔥 NON-BLOCKING GET (NO API DELAY)
    def get_tokens(self, server_key):
        now = time.time()

        # ✅ agar cache me valid tokens hain → direct return
        if server_key in self.cache and self.cache[server_key]:
            return self.cache[server_key]

        # 🔥 background me refresh start (LOCK FREE)
        if server_key not in self.last_refresh or (
            now - self.last_refresh.get(server_key, 0)
        ) > 10:   # avoid spam threads

            self.last_refresh[server_key] = now

            threading.Thread(
                target=self._refresh_tokens,
                args=(server_key,),
                daemon=True
            ).start()

        return []  # ❗ fast response (no wait)

    # 🔥 SINGLE TOKEN FETCH (SAFE + FAST)
    def _fetch_single(self, user):
        try:
            params = {
                'uid': user['uid'],
                'password': user['password']
            }

            response = self.session.get(
                AUTH_URL,
                params=params,
                timeout=3   # 🔥 FAST FAIL (IMPORTANT)
            )

            if response.status_code == 200:
                data = response.json()

                if not data.get("error") and data.get("token"):
                    return data["token"]

            else:
                logger.warning(
                    f"Bad response {response.status_code} for {user['uid']}"
                )

        except Exception as e:
            logger.error(f"Token fetch failed for {user['uid']}: {e}")

        return None

    # 🔥 PARALLEL TOKEN FETCH (CONTROLLED)
    def _refresh_tokens(self, server_key):
        try:
            creds = self._load_credentials(server_key)

            if not creds:
                self.cache[server_key] = []
                return

            # 🔥 limit users (IMPORTANT for render stability)
            creds = creds[:8]

            tokens = []

            with ThreadPoolExecutor(max_workers=4) as executor:
                results = list(executor.map(self._fetch_single, creds))

            tokens = [t for t in results if t]

            if tokens:
                self.cache[server_key] = tokens
                logger.info(f"✅ Tokens loaded: {len(tokens)} for {server_key}")

            else:
                logger.warning("⚠️ No tokens fetched → using fallback")

                fallback = os.getenv("FALLBACK_TOKEN")
                if fallback:
                    self.cache[server_key] = [fallback]
                else:
                    self.cache[server_key] = []

        except Exception as e:
            logger.error(f"Critical error: {e}")
            self.cache[server_key] = []

    # 🔥 LOAD UID/PASS
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


# 🔥 FINAL HEADERS (OB52 SAFE)
def get_headers(token: str):
    return {
        'User-Agent': "Dalvik/2.1.0 (Linux; Android 9)",
        'Connection': "Keep-Alive",
        'Accept-Encoding': "gzip",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Unity-Version": "2018.4.11f1",
        "X-GA": "v1 1",
        "ReleaseVersion": "OB52"
    }
