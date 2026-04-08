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
logging.basicConfig(level=logging.INFO)

AUTH_URL = os.getenv("AUTH_URL", "http://jwt.thug4ff.xyz/token")

CACHE_DURATION = timedelta(hours=7).seconds


class TokenCache:
    def __init__(self, servers_config):
        self.cache = TTLCache(maxsize=100, ttl=CACHE_DURATION)
        self.last_refresh = {}
        self.session = requests.Session()
        self.servers_config = servers_config

    # 🚀 FAST NON-BLOCKING
    def get_tokens(self, server_key):
        now = time.time()

        if server_key in self.cache and self.cache[server_key]:
            logger.info(f"✅ Using cached tokens: {len(self.cache[server_key])}")
            return self.cache[server_key]

        # background refresh
        if server_key not in self.last_refresh or now - self.last_refresh.get(server_key, 0) > 10:
            self.last_refresh[server_key] = now

            logger.info("🔄 Starting background token refresh...")

            threading.Thread(
                target=self._refresh_tokens,
                args=(server_key,),
                daemon=True
            ).start()

        return []

    # 🔥 SINGLE FETCH + DEBUG
    def _fetch_single(self, user):
        try:
            params = {
                'uid': user['uid'],
                'password': user['password']
            }

            logger.info(f"➡️ Requesting token for UID: {user['uid']}")

            response = self.session.get(
                AUTH_URL,
                params=params,
                timeout=5
            )

            logger.info(f"⬅️ Status: {response.status_code} | UID: {user['uid']}")

            if response.status_code == 200:
                try:
                    data = response.json()
                except Exception:
                    logger.error(f"❌ Invalid JSON response: {response.text}")
                    return None

                # DEBUG FULL RESPONSE
                logger.info(f"📦 Response: {data}")

                if not data.get("error") and data.get("token"):
                    logger.info(f"✅ Token OK for UID: {user['uid']}")
                    return data["token"]
                else:
                    logger.warning(f"⚠️ API error for UID {user['uid']}: {data}")

            else:
                logger.warning(f"❌ Bad status {response.status_code}: {response.text}")

        except requests.exceptions.Timeout:
            logger.error(f"⏱️ Timeout for UID: {user['uid']}")
        except Exception as e:
            logger.error(f"❌ Exception for UID {user['uid']}: {e}")

        return None

    # 🔥 PARALLEL FETCH
    def _refresh_tokens(self, server_key):
        try:
            creds = self._load_credentials(server_key)

            if not creds:
                logger.warning("❌ No credentials found")
                self.cache[server_key] = []
                return

            # 🔥 limit load (IMPORTANT)
            creds = creds[:6]

            logger.info(f"🚀 Fetching tokens for {len(creds)} accounts")

            with ThreadPoolExecutor(max_workers=3) as executor:
                results = list(executor.map(self._fetch_single, creds))

            tokens = [t for t in results if t]

            if tokens:
                self.cache[server_key] = tokens
                logger.info(f"🎉 Tokens loaded: {len(tokens)}")

            else:
                logger.warning("⚠️ No tokens fetched, using fallback")

                fallback = os.getenv("FALLBACK_TOKEN")
                if fallback:
                    logger.info("🧷 Using fallback token")
                    self.cache[server_key] = [fallback]
                else:
                    self.cache[server_key] = []

        except Exception as e:
            logger.error(f"🔥 Critical error: {e}")
            self.cache[server_key] = []

    # 🔥 LOAD UID/PASS
    def _load_credentials(self, server_key):
        try:
            config_data = os.getenv(f"{server_key}_CONFIG")

            if config_data:
                logger.info("📂 Loaded credentials from ENV")
                return json.loads(config_data)

            config_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'config',
                f'{server_key.lower()}_config.json'
            )

            if os.path.exists(config_path):
                logger.info(f"📂 Loading config file: {config_path}")
                with open(config_path, 'r') as f:
                    return json.load(f)

            logger.warning(f"❌ No config found for {server_key}")
            return []

        except Exception as e:
            logger.error(f"❌ Config load error: {e}")
            return []


# 🔥 HEADERS FIX (OB52)
def get_headers(token: str):
    return {
        'User-Agent': "Dalvik/2.1.0 (Linux; Android 9)",
        'Connection': "Keep-Alive",
        'Accept-Encoding': "gzip",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Unity-Version": "2018.4.11f1",
        "X-GA": "v1 1",
        "ReleaseVersion": "OB53"
    }
