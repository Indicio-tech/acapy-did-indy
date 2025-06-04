"""did:indy support."""

import logging
from os import getenv

from acapy_agent.config.injection_context import InjectionContext
from acapy_agent.wallet.did_method import DIDMethods
from acapy_agent.resolver.did_resolver import DIDResolver
from acapy_agent.anoncreds.registry import AnonCredsRegistry
from acapy_agent.config.provider import ClassProvider

from did_indy.author.author import Author, AuthorDependencies
from did_indy.ledger import LedgerPool, fetch_genesis_transactions
from did_indy.client.client import IndyDriverAdminClient, IndyDriverClient
from did_indy.cache import BasicCache

DRIVER = getenv("DRIVER", "http://driver")

from .did import INDY
from .registrar import IndyRegistrar
from .registry import IndyRegistry
from .resolver import IndyResolver

LOGGER = logging.getLogger(__name__)


async def setup(context: InjectionContext):
    registry = context.inject_or(AnonCredsRegistry)
    if not registry:
        LOGGER.error("No AnonCredsRegistry instance found in context!!!")
        return
    methods = context.inject(DIDMethods)
    methods.register(INDY)

    indy_resolver = IndyResolver()
    await indy_resolver.setup(context)
    resolver = context.inject(DIDResolver)
    resolver.register_resolver(indy_resolver)
    context.injector.bind_instance(IndyRegistrar, IndyRegistrar(context.settings))

    admin = IndyDriverAdminClient(DRIVER, admin_api_key="insecure-api-key")
    token = (
        await admin.create_client(
            "test",
            schemas=True,
            cred_defs=True,
        )
    ).token
    client = IndyDriverClient(DRIVER, client_token=token)
    NAMESPACE = "indicio:test"
    taa_info = await client.get_taa(NAMESPACE)
    taa = await client.accept_taa(taa_info, "on_file")
    pool = LedgerPool(
        NAMESPACE,
        genesis_transactions=await fetch_genesis_transactions(
            "https://raw.githubusercontent.com/Indicio-tech/indicio-network/main/genesis_files/pool_transactions_testnet_genesis"
        ),
        cache=BasicCache(),
    )

    indy_registry = IndyRegistry(client, pool)
    indy_registry = ClassProvider(
        "acapy_did_indy.registry.IndyRegistry",
        client=client,
        pool=pool,
        # supported_identifiers=[],
        # method_name="did:indy",
    ).provide(context.settings, context.injector)
    await indy_registry.setup(context)
    registry.register(indy_registry)
