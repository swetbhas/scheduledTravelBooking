# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class CodexCredentialsError(RuntimeError):
    """Raised when shared Codex credentials are requested but unavailable."""


def _candidate_paths() -> list[Path]:
    paths = []
    if value := os.environ.get("CODEX_SHARED_CREDENTIALS_PATH"):
        paths.append(Path(value).expanduser())
    if value := os.environ.get("CODEX_CREDENTIALS_PATH"):
        paths.append(Path(value).expanduser())
    return paths


def load_shared_codex_credentials(required: bool = False) -> dict[str, Any]:
    """Load shared Codex credentials from a runtime-only filesystem path.

    The application never commits or creates this file. Operators provide the
    path with CODEX_SHARED_CREDENTIALS_PATH or CODEX_CREDENTIALS_PATH.
    """
    for path in _candidate_paths():
        if path.is_file():
            with path.open(encoding="utf-8") as credentials_file:
                data = json.load(credentials_file)
            if not isinstance(data, dict):
                raise CodexCredentialsError(f"Credentials file is not an object: {path}")
            return data

    if required:
        raise CodexCredentialsError(
            "Set CODEX_SHARED_CREDENTIALS_PATH to a JSON credentials file."
        )
    return {}
