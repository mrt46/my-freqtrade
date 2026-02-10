from __future__ import annotations

from collections.abc import Generator
from unittest.mock import patch

import pytest


@pytest.fixture
def mocker() -> Generator[object, None, None]:
    patchers: list[object] = []

    class SimpleMocker:
        def patch(self, target: str, *args, **kwargs):
            patcher = patch(target, *args, **kwargs)
            mocked = patcher.start()
            patchers.append(patcher)
            return mocked

    yield SimpleMocker()

    for patcher in patchers:
        patcher.stop()
