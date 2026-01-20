import base64
import hashlib
import sys
from functools import wraps
from pathlib import Path

from sanic import response
from sanic.request import Request
from sanic.response import BaseHTTPResponse
from tomli_w import dump as toml_dump

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from testbench_requirement_service.utils.config import CONFIG_PREFIX


def hash_password(password: str, salt: bytes) -> str:
    """Hashes a password with a given salt using PBKDF2-HMAC with SHA256."""
    pepper = b"\xfb\x0e\xbb\x1cg\x15'\x8f6\x15\xcc\x14\x81\xd8\xfe\x93"
    return hashlib.pbkdf2_hmac("sha256", password.encode() + pepper, salt, 100000).hex()


def save_credentials(password_hash: str, salt: bytes, config_path: Path):
    """Save credentials to both config file and .env file."""
    save_credentials_in_config_file(password_hash, salt, config_path)


def save_credentials_in_config_file(password_hash: str, salt: bytes, config_path: Path) -> None:
    """Save credentials to a config file, supporting both legacy .py and TOML formats."""

    suffix = config_path.suffix.lower()
    if suffix == ".toml":
        save_credentials_in_toml_config(password_hash, salt, config_path)
    else:
        save_credentials_in_python_config(password_hash, salt, config_path)


def save_credentials_in_python_config(password_hash: str, salt: bytes, config_path: Path) -> None:
    """Persist credentials inside the legacy Python config format."""

    salt_encoded = repr(base64.b64encode(salt).decode())

    if config_path.exists():
        with config_path.open("r") as file:
            lines = file.readlines()
    else:
        lines = []

    updated_lines: list[str] = []
    updated_password = False
    updated_salt = False

    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("PASSWORD_HASH"):
            updated_lines.append(f"PASSWORD_HASH = {password_hash!r}\n")
            updated_password = True
        elif stripped.startswith("SALT"):
            updated_lines.append(f"SALT = {salt_encoded}\n")
            updated_salt = True
        else:
            updated_lines.append(line)

    if not updated_password:
        updated_lines.append(f"PASSWORD_HASH = {password_hash!r}\n")
    if not updated_salt:
        updated_lines.append(f"SALT = {salt_encoded}\n")

    with config_path.open("w") as file:
        file.writelines(updated_lines)


def save_credentials_in_toml_config(password_hash: str, salt: bytes, config_path: Path) -> None:
    """Persist credentials inside the TOML config structure."""

    if config_path.exists():
        try:
            with config_path.open("rb") as file:
                config_data = tomllib.load(file)
        except Exception as exc:
            raise ValueError(f"Failed to parse TOML config at '{config_path}'.") from exc
    else:
        config_data = {}

    section = config_data.setdefault(CONFIG_PREFIX, {})
    section["password_hash"] = password_hash
    section["salt"] = base64.b64encode(salt).decode()
    config_data[CONFIG_PREFIX] = section

    with config_path.open("wb") as file:
        toml_dump(config_data, file)


def check_credentials(request: Request, username: str, password: str) -> bool:
    """Check if a username/password combination is valid and stores that if so."""
    app = request.app
    if getattr(app.ctx, "valid_hash", None) == username + password:
        return True
    is_valid = bool(
        hash_password(username + password, base64.b64decode(app.config.SALT))
        == app.config.PASSWORD_HASH
    )
    if is_valid:
        app.ctx.valid_hash = username + password
    return is_valid


def check_auth_for_request(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Basic "):
        return response.json({"message": "Unauthorized"}, status=401)
    try:
        auth_decoded = base64.b64decode(auth_header.split(" ")[1]).decode("utf-8")
        username, password = auth_decoded.split(":", 1)
    except Exception:
        return response.json({"message": "Invalid authentication format"}, status=401)
    try:
        if not check_credentials(request, username, password):
            return response.json({"message": "Invalid credentials"}, status=403)
    except Exception:
        return response.json(
            {"message": "Invalid Configuration! No server credentials set."}, status=500
        )


def protected(wrapped):
    def decorator(f):
        @wraps(f)
        async def decorated_function(request: Request, *args, **kwargs):
            response = check_auth_for_request(request)
            if isinstance(response, BaseHTTPResponse):
                return response
            return await f(request, *args, **kwargs)

        return decorated_function

    return decorator(wrapped)
