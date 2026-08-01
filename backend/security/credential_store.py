from __future__ import annotations

import subprocess
import sys
from typing import Protocol


class CredentialStore(Protocol):
    def set(self, account: str, secret: str) -> None: ...

    def get(self, account: str) -> str: ...

    def delete(self, account: str) -> None: ...


class MacOSKeychainCredentialStore:
    service_name = "com.autodevplatform.models"

    def set(self, account: str, secret: str) -> None:
        if sys.platform != "darwin":
            raise RuntimeError("Model credentials require macOS Keychain")
        secret_hex = secret.encode("utf-8").hex()
        result = subprocess.run(
            ["security", "-i"],
            input=(
                "add-generic-password -U "
                f"-a {account} -s {self.service_name} -X {secret_hex}\n"
            ),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 or self.get(account) != secret:
            raise RuntimeError("Unable to save API key to macOS Keychain")

    def get(self, account: str) -> str:
        if sys.platform != "darwin":
            return ""
        result = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-a",
                account,
                "-s",
                self.service_name,
                "-w",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else ""

    def delete(self, account: str) -> None:
        if sys.platform != "darwin":
            return
        subprocess.run(
            [
                "security",
                "delete-generic-password",
                "-a",
                account,
                "-s",
                self.service_name,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
