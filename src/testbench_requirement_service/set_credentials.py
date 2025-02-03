import base64
import hashlib
import os
from pathlib import Path

import click


def hash_password(password: str, salt: bytes) -> str:
    """Hash a password using PBKDF2-HMAC with SHA256."""
    pepper = b"\xfb\x0e\xbb\x1cg\x15'\x8f6\x15\xcc\x14\x81\xd8\xfe\x93"
    return hashlib.pbkdf2_hmac("sha256", password.encode() + pepper, salt, 100000).hex()


def save_config(password_hash: str, salt: bytes, config_path: Path):
    """Save user credentials and salt to a YAML config file."""

    with config_path.open("w") as f:
        f.write(f"PASSWORD_HASH = {password_hash!r}\n")
        f.write(f"SALT = {base64.b64encode(salt).decode()!r}\n")
    click.echo(f"Configuration saved to {config_path}")


@click.command()
@click.option(
    "--config", default="config.py", help="Path to the configuration file.", type=click.Path()
)
def main(config):
    """Command-line tool to store user credentials securely."""
    config_path = Path(config)
    user = click.prompt("Enter username", type=str)
    password = click.prompt("Enter password", hide_input=True, confirmation_prompt=True)
    salt = os.urandom(16)
    password_hash = hash_password(user + password, salt)

    save_config(password_hash, salt, config_path)


if __name__ == "__main__":
    main()
