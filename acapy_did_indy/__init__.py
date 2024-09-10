from os import getenv
from aiohttp import ClientSession
from aries_cloudagent.config.injection_context import InjectionContext
from aries_cloudagent.wallet.did_method import DIDMethod, DIDMethods, HolderDefinedDid
from aries_cloudagent.wallet.key_type import ED25519

WEB = DIDMethod(
    name="web",
    key_types=[ED25519],
    rotation=True,
    holder_defined_did=HolderDefinedDid.REQUIRED,
)
INDY = DIDMethod(
    name="indy",
    key_types=[ED25519],
    rotation=True,
    holder_defined_did=HolderDefinedDid.NO,
)


async def setup(context: InjectionContext):
    methods = context.inject(DIDMethods)
    methods.register(WEB)
    methods.register(INDY)

    config = context.settings.for_plugin("acapy_did_web")
    server_base_url = config.get("server_base_url") or getenv("DID_WEB_SERVER_URL")
    if not server_base_url:
        raise ValueError("Failed to load did:web server base url")

    context.injector.bind_instance(
        DidWebServerClient, DidWebServerClient(server_base_url)
    )


class DidWebServerClientError(Exception):
    """Raised on errors in the client."""


class DidWebServerClient:
    """Client to DID Web Server."""

    def __init__(self, base_url: str):
        """Init the client."""
        self.base_url = base_url

    async def put_did(self, name: str, document: dict):
        """Put the DID at the named location on the server."""
        async with ClientSession(self.base_url) as session:
            async with session.put(f"/did/{name}", json=document) as resp:
                if not resp.ok:
                    raise DidWebServerClientError(
                        "Failed to put the document: " + await resp.text()
                    )
