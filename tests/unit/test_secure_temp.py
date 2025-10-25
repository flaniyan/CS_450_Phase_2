import io
import os
import zipfile
import tempfile
import boto3
from moto import mock_aws
from src.services.secure_temp import (
    encrypt_bytes_to_files,
    decrypt_file_to_bytes,
    safe_delete,
)


@mock_aws
def test_encrypt_decrypt_zip_roundtrip(monkeypatch):
    # Arrange: KMS key
    kms = boto3.client("kms", region_name=os.getenv("AWS_REGION", "us-east-1"))
    key = kms.create_key(Description="unit-test")["KeyMetadata"]["KeyId"]
    monkeypatch.setenv("KMS_KEY_ID", key)

    # Create an in-memory zip
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("a.txt", "hello")
    zip_bytes = buf.getvalue()

    with tempfile.TemporaryDirectory() as td:
        cpath = os.path.join(td, "pkg.zip.enc")
        mpath = os.path.join(td, "pkg.zip.meta.json")
        # Act
        encrypt_bytes_to_files(
            zip_bytes, {"Service": "validator", "Target": "X"}, cpath, mpath
        )
        out = decrypt_file_to_bytes(cpath, mpath)
        # Assert
        assert out == zip_bytes
        # cleanup
        safe_delete(cpath, mpath)


@mock_aws
def test_no_plaintext_zip_on_disk(monkeypatch):
    """Ensure no plaintext ZIP files are written to disk during encryption"""
    # Arrange: KMS key
    kms = boto3.client("kms", region_name=os.getenv("AWS_REGION", "us-east-1"))
    key = kms.create_key(Description="unit-test")["KeyMetadata"]["KeyId"]
    monkeypatch.setenv("KMS_KEY_ID", key)

    # Create test ZIP content
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("test.txt", "sensitive data")
        z.writestr("config.json", '{"secret": "value"}')
    zip_bytes = buf.getvalue()

    with tempfile.TemporaryDirectory() as td:
        cpath = os.path.join(td, "test.zip.enc")
        mpath = os.path.join(td, "test.zip.meta.json")

        # Act: Encrypt the ZIP
        encrypt_bytes_to_files(
            zip_bytes, {"Service": "validator", "Target": "test"}, cpath, mpath
        )

        # Assert: No plaintext ZIP file exists
        plaintext_zip = os.path.join(td, "test.zip")
        assert not os.path.exists(plaintext_zip)

        # Assert: Only encrypted files exist
        assert os.path.exists(cpath)
        assert os.path.exists(mpath)

        # Assert: Encrypted file is not the same as original
        with open(cpath, "rb") as f:
            encrypted_content = f.read()
        assert encrypted_content != zip_bytes

        # Assert: Can decrypt back to original
        decrypted = decrypt_file_to_bytes(cpath, mpath)
        assert decrypted == zip_bytes

        # Cleanup
        safe_delete(cpath, mpath)


@mock_aws
def test_encryption_context_enforcement(monkeypatch):
    """Test that encryption context is properly enforced"""
    # Arrange: KMS key
    kms = boto3.client("kms", region_name=os.getenv("AWS_REGION", "us-east-1"))
    key = kms.create_key(Description="unit-test")["KeyMetadata"]["KeyId"]
    monkeypatch.setenv("KMS_KEY_ID", key)

    test_data = b"test data"
    context = {"Service": "validator", "Target": "test-package"}

    with tempfile.TemporaryDirectory() as td:
        cpath = os.path.join(td, "test.enc")
        mpath = os.path.join(td, "test.meta.json")

        # Act: Encrypt with context
        encrypt_bytes_to_files(test_data, context, cpath, mpath)

        # Assert: Metadata contains the context
        import json
        with open(mpath, "r") as f:
            metadata = json.load(f)
        assert metadata["ctx"] == context
        assert "enk" in metadata

        # Assert: Can decrypt with same context
        decrypted = decrypt_file_to_bytes(cpath, mpath)
        assert decrypted == test_data

        # Cleanup
        safe_delete(cpath, mpath)


def test_safe_delete_handles_missing_files():
    """Test that safe_delete doesn't fail on missing files"""
    # Should not raise any exceptions
    safe_delete("nonexistent1.txt", "nonexistent2.txt", "")


@mock_aws
def test_sigterm_cleanup_registration(monkeypatch):
    """Test that SIGTERM cleanup is properly registered"""
    from src.services.secure_temp import register_sigterm_cleanup, _OPEN_TMP

    # Arrange: KMS key
    kms = boto3.client("kms", region_name=os.getenv("AWS_REGION", "us-east-1"))
    key = kms.create_key(Description="unit-test")["KeyMetadata"]["KeyId"]
    monkeypatch.setenv("KMS_KEY_ID", key)

    # Clear any existing temp files
    _OPEN_TMP.clear()

    # Register cleanup
    register_sigterm_cleanup()

    # Simulate adding temp files
    _OPEN_TMP.extend(["test1.enc", "test1.meta.json"])

    # Verify files are tracked
    assert len(_OPEN_TMP) == 2

    # Cleanup
    safe_delete(*_OPEN_TMP)
    _OPEN_TMP.clear()
