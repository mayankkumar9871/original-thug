# app/protobuf_utils.py
import app.protobuf.uid_generator_pb2 as uid_generator_pb2
import app.protobuf.like_pb2 as like_pb2
import app.protobuf.like_count_pb2 as like_count_pb2
from google.protobuf.message import DecodeError
import logging
from .crypto_utils import encrypt_aes # Import relatif puisque crypto_utils.py est dans le même dossier

logger = logging.getLogger(__name__)

def create_protobuf(uid: str, region=None):
    if region:
        msg = like_pb2.like()
        msg.uid = int(uid)
        msg.region = region
    else:
        msg = uid_generator_pb2.uid_generator()
        msg.saturn_ = int(uid)
        msg.garena = 1
    return msg.SerializeToString()

def encode_uid(uid: str) -> str:
    return encrypt_aes(create_protobuf(uid))

def decode_info(data: bytes):
    try:
        text = data.decode(errors='ignore')
        if "invalid" in text.lower():
            logger.warning(f"⚠️ Server Response: {text}")
            return None

        # Try protobuf
        try:
            info = like_count_pb2.Info()
            info.ParseFromString(data)
            logger.info("✅ Decoded with Info")
            return info
        except:
            pass

        try:
            info = uid_generator_pb2.uid_generator()
            info.ParseFromString(data)
            logger.info("✅ Decoded with uid_generator")
            return info
        except:
            pass

        logger.error("❌ Unknown protobuf format")
        return None

    except Exception as e:
        logger.error(f"Decode failed: {e}")
        return None
