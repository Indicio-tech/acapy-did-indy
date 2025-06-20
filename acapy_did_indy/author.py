"""did:indy support."""

import logging
from typing import cast
from os import getenv

from acapy_agent.wallet.base import BaseWallet
from acapy_agent.core.error import BaseError

from did_indy.ledger import LedgerPool
from did_indy.ledger import TaaAcceptance
from did_indy.client.client import IndyDriverClient
from did_indy.signer import Signer
from did_indy.author.author import Author, AuthorDependencies
from acapy_agent.core.profile import Profile

from did_indy.client import http
import json

original_deserialize = http._deserialize

def patched_deserialize(body, response_type):
    if hasattr(response_type, '__name__') and response_type.__name__ == 'NymResponse':
        if isinstance(body, dict) and 'diddocContent' in body and isinstance(body['diddocContent'], str):
            body = body.copy()
            try:
                body['diddocContent'] = json.loads(body['diddocContent'])
            except json.JSONDecodeError:
                # If it's not valid JSON, leave it as string and let validation fail normally
                pass
    return original_deserialize(body, response_type)

http._deserialize = patched_deserialize

DRIVER = getenv("DRIVER", "http://driver")
API_KEY = getenv("API_KEY", None)

LOGGER = logging.getLogger(__name__)


class IndyRegistryError(BaseError):
    """Raised on errors in registrar."""


class AuthorDependenciesBasic(AuthorDependencies):
    def __init__(self, signer: Signer, pool: LedgerPool):
        self.signer = signer
        self.pool = pool

    async def get_signer(self, did: str) -> Signer:
        return self.signer

    async def get_pool(self, namespace: str) -> LedgerPool:
        return self.pool


class AuthorSession:
    def __init__(self, profile: Profile, client: IndyDriverClient, pool: LedgerPool, taa: TaaAcceptance | None):
        self.client = client
        self._pool = pool
        self._profile = profile
        self.taa = taa
        self._author: Author

    def with_verkey(self, verkey: str) -> "AuthorSession":
        async def sign_transaction(message: bytes) -> bytes:
            """Sign a message."""
            async with self._profile.session() as session:
                wallet = session.inject(BaseWallet)
                return bytes(await wallet.sign_message(message, from_verkey=verkey))
        dependencies = AuthorDependenciesBasic(cast(Signer, sign_transaction), self._pool)
        self._author = Author(self.client, dependencies)
        return self
    
    def get_author(self) -> Author:
        return self._author

    async def __aenter__(self) -> Author:
        return self.get_author()
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # self._author = None
        pass
