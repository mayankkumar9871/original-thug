# app/protobuf_utils.py
import app.protobuf.uid_generator_pb2 as uid_generator_pb2
import app.protobuf.like_pb2 as like_pb2
import app.protobuf.like_count_pb2 as like_count_pb2
from google.protobuf.message import DecodeError
import logging
from .crypto_utils import encrypt_aes  # Import relative

logger = logging.getLogger(__name__)

def create_protobuf(uid: str, region=None):
    """
    Create protobuf message for UID.
    If region is provided, create 'like' message with region field.
    Otherwise, create uid_generator message.
    """
    if region:
        msg = like_pb2.like()
        msg.uid = int(uid)
        msg.region = region
    else:
        msg = uid_generator_pb2.uid_generator()
        msg.saturn_ = int(uid)
        msg.garena = 1
    return msg.SerializeToString()

def encode_uid(uid: str, region=None) -> str:
    """
    Encode UID into encrypted hex string using AES.
    Always pass region if required by server to avoid signature errors.
    """
    return encrypt_aes(create_protobuf(uid, region))

def decode_info(data: bytes):
    try:
        logger.info(f"RAW RESPONSE (HEX): {data[:30].hex()}")
        logger.info(f"RAW RESPONSE (LEN): {len(data)}")
        # Try Info
        try:
            info = like_count_pb2.Info()
            info.ParseFromString(data)
            logger.info("✅ Decoded with Info")
            return info
        except:
            pass

        # Try UID generator
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
