"""did:indy resolver."""

import re
from typing import Dict, Optional, Pattern, Sequence, Text
from aries_cloudagent.config.injection_context import InjectionContext
from aries_cloudagent.config.ledger import fetch_genesis_transactions
from aries_cloudagent.core.profile import Profile
from aries_cloudagent.messaging.valid import B58
from aries_cloudagent.resolver.base import BaseDIDResolver, DIDNotFound, ResolverError, ResolverType
from indy_vdr import Resolver, VdrError, VdrErrorCode, open_pool


INDY_DID_PATTERN = re.compile(
    rf"^did:indy:(?P<namespace>[^:]+(:[^:]+)?):[{B58}]{{21,22}}$"
)



class IndyResolver(BaseDIDResolver):
    """Indy DID Resolver."""

    SERVICE_TYPE_DID_COMMUNICATION = "did-communication"
    SERVICE_TYPE_DIDCOMM = "DIDComm"
    SERVICE_TYPE_ENDPOINT = "endpoint"
    CONTEXT_DIDCOMM_V2 = "https://didcomm.org/messaging/contexts/v2"

    def __init__(self):
        """Initialize Indy Resolver."""
        super().__init__(ResolverType.NATIVE)
        self._resolver: Resolver | None = None

    async def setup(self, context: InjectionContext):
        """Perform required setup for Indy DID resolution."""
        settings = context.settings.for_plugin("acapy_did_indy")
        auto = settings.get_bool("auto_ledger")
        ledgers: Dict[str, str] | None = settings.get("ledgers")
        if auto:
            resolver = Resolver(autopilot=True)
        elif ledgers:
            resolver = Resolver(pool_map={
                name: await open_pool(transactions=await fetch_genesis_transactions(genesis_url))
                for name, genesis_url in ledgers.items()
            })
        else:
            raise ResolverError(
                "Could not configure indy resolver; missing auto flag or ledger map"
            )

        self._resolver = resolver

    @property
    def resolver(self):
        """Return resolver."""
        assert self._resolver, "Setup should be called before using resolver"
        return self._resolver

    @property
    def supported_did_regex(self) -> Pattern:
        """Return supported_did_regex of Indy DID Resolver."""
        return INDY_DID_PATTERN

    async def _resolve(
        self,
        profile: Profile,
        did: str,
        service_accept: Optional[Sequence[Text]] = None,
    ) -> dict:
        """Resolve an indy DID."""
        try:
            resolve_result = await self.resolver.resolve(did)
        except VdrError as error:
            if error.code == VdrErrorCode.RESOLVER and "Object not found" in str(error):
                raise DIDNotFound(f"DID {did} not found") from error
            raise ResolverError("Unexpected error in Indy resolver") from error

        doc = resolve_result["didDocument"]
        return doc
