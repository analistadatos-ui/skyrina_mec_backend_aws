# app/core/security.py
import hashlib
import bcrypt

def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt with SHA256 pre-hashing.
    This handles passwords of any length and avoids bcrypt's 72-byte limit.
    """
    # Pre-hash with SHA256 to handle long passwords
    pre_hashed = hashlib.sha256(password.encode('utf-8')).hexdigest()
    # Generate salt and hash
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pre_hashed.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its bcrypt hash.
    """
    # Pre-hash with SHA256 to match the hashing process
    pre_hashed = hashlib.sha256(plain_password.encode('utf-8')).hexdigest()
    try:
        return bcrypt.checkpw(
            pre_hashed.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    except ValueError as e:
        print(f"Password verification error: {e}")
        return False