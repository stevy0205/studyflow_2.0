# conftest.py – pytest asyncio Konfiguration
import pytest

# Damit @pytest.mark.asyncio funktioniert
def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: mark test as async")
