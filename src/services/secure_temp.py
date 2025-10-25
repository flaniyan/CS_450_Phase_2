import json
import os
import signal
import stat
from typing import Dict, Tuple, List

import boto3
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

def _get_kms_client():
    return boto3.client("kms", region_name=AWS_REGION)

def _get_kms_key_id():
    return os.getenv("KMS_KEY_ID")
_OPEN_TMP: List[str] = []


def _0600(path: str) -> None:
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 0600
    except Exception:
        pass


def _zeroize(b: bytearray) -> None:
    for i in range(len(b)):
        b[i] = 0


def encrypt_bytes_to_files(
    payload: bytes,
    context: Dict[str, str],
    out_cipher_path: str,
    out_meta_path: str,
) -> Tuple[str, str]:
    """
    Encrypts bytes with a one-time KMS data key and writes:
      - out_cipher_path : nonce + GCM(ciphertext)
      - out_meta_path   : JSON { enk: <hex>, ctx: {...} }
    Returns (cipher_path, meta_path).
    """
    kms_key_id = _get_kms_key_id()
    if not kms_key_id:
        raise RuntimeError("KMS_KEY_ID not set")
    kms = _get_kms_client()
    resp = kms.generate_data_key(
        KeyId=kms_key_id, KeySpec="AES_256", EncryptionContext=context
    )
    pt_key = bytearray(resp["Plaintext"])
    ct_key = resp["CiphertextBlob"]
    try:
        aesgcm = AESGCM(bytes(pt_key))
        nonce = os.urandom(12)
        aad = json.dumps(context).encode()
        blob = aesgcm.encrypt(nonce, payload, aad)
        with open(out_cipher_path, "wb") as f:
            f.write(nonce + blob)
        _0600(out_cipher_path)
        meta = {"enk": ct_key.hex(), "ctx": context}
        with open(out_meta_path, "w") as f:
            json.dump(meta, f)
        _0600(out_meta_path)
        _OPEN_TMP.extend([out_cipher_path, out_meta_path])
        return out_cipher_path, out_meta_path
    finally:
        _zeroize(pt_key)


def decrypt_file_to_bytes(cipher_path: str, meta_path: str) -> bytes:
    with open(meta_path, "r") as f:
        meta = json.load(f)
    enc_key = bytes.fromhex(meta["enk"])
    ctx = meta["ctx"]
    kms = _get_kms_client()
    resp = kms.decrypt(CiphertextBlob=enc_key, EncryptionContext=ctx)
    pt_key = bytearray(resp["Plaintext"])
    try:
        with open(cipher_path, "rb") as f:
            blob = f.read()
        nonce, gcm = blob[:12], blob[12:]
        aesgcm = AESGCM(bytes(pt_key))
        return aesgcm.decrypt(nonce, gcm, json.dumps(ctx).encode())
    finally:
        _zeroize(pt_key)


def safe_delete(*paths: str) -> None:
    for p in paths:
        if not p:
            continue
        try:
            os.remove(p)
        except FileNotFoundError:
            pass
        except Exception:
            pass


def register_sigterm_cleanup():
    def _handler(signum, frame):
        safe_delete(*list(_OPEN_TMP))
        # Do not force-exit; let the app decide—this is just cleanup.

    signal.signal(signal.SIGTERM, _handler)
