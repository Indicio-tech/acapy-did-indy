"""did:indy support."""

import logging
from os import getenv

from acapy_agent.config.injection_context import InjectionContext
from acapy_agent.wallet.did_method import DIDMethods
from acapy_agent.resolver.did_resolver import DIDResolver
from acapy_agent.anoncreds.registry import AnonCredsRegistry
from acapy_agent.config.provider import ClassProvider, BaseProvider
from acapy_agent.wallet.base import BaseWallet
from acapy_agent.config.base import BaseSettings, BaseInjector
from acapy_agent.core.error import BaseError

from did_indy.ledger import LedgerPool, fetch_genesis_transactions, BaseLedger
from did_indy.client.client import IndyDriverAdminClient, IndyDriverClient
from did_indy.cache import BasicCache
from did_indy.author.author import Author, AuthorDependencies
from aries_askar import Key
from acapy_agent.core.profile import Profile

from .did import INDY
from .author import AuthorSession
from .registrar import IndyRegistrar
from .registry import IndyRegistry
from .resolver import IndyResolver



DRIVER = getenv("DRIVER", "http://driver")
API_KEY = getenv("API_KEY", None)

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

    admin = IndyDriverAdminClient(DRIVER, admin_api_key="insecure-api-key")
    token = (
        await admin.create_client(
            "test",
            schemas=True,
            cred_defs=True,
            # new_nyms=True,
            # nym_updates=True,
        )
    )
    # client = IndyDriverClient(DRIVER, client_token=token)
    # token = token if API_KEY is None else API_KEY
    LOGGER.debug("[CW] Using API key: %s", token)
    token = token.token

    if token is None:
        LOGGER.error("No API key found. Please provide an API key using the `API_KEY` environment variable.")
        return

    client = IndyDriverClient(DRIVER, client_token=token)
    context.injector.bind_provider(IndyDriverClient, ClassProvider(
        "did_indy.client.client.IndyDriverClient",
        driver_url=DRIVER,
        client_token=token,
    ))
    NAMESPACE = "indicio:test"
    taa_info = await client.get_taa(NAMESPACE)
    taa = await client.accept_taa(taa_info, "on_file")
    # pool = LedgerPool(
    #     NAMESPACE,
    #     genesis_transactions=await fetch_genesis_transactions(
    #         "https://raw.githubusercontent.com/Indicio-tech/indicio-network/main/genesis_files/pool_transactions_testnet_genesis"
    #     ),
    #     cache=BasicCache(),
    # )
    context.injector.bind_provider(LedgerPool, ClassProvider(
        "did_indy.ledger.LedgerPool",
        name=NAMESPACE,
        genesis_transactions=await fetch_genesis_transactions(
            "https://raw.githubusercontent.com/Indicio-tech/indicio-network/main/genesis_files/pool_transactions_testnet_genesis"
        ),
        cache=BasicCache(),
    ))
    context.injector.bind_provider(AuthorSession, ClassProvider(
        "acapy_did_indy.author.AuthorSession",
        client=client,
        taa=taa,
        pool=ClassProvider.Inject(LedgerPool),
        profile=ClassProvider.Inject(Profile),
    ))
    # context.injector.bind_provider(
    #     AuthorSession,
    #     ClassProvider(
    #         "acapy_did_indy.author.AuthorSession",
    #         client=client,
    #         taa=taa,
    #         pool=context.injector.inject(LedgerPool),
    #         profile=context.injector.inject(Profile),
    #     )
    # )

    indy_registry = IndyRegistry(client)
    context.injector.bind_instance(
        IndyRegistrar,
        IndyRegistrar(
            context.settings,
        )
    )
    indy_registry = ClassProvider(
        "acapy_did_indy.registry.IndyRegistry",
        client=client,
        # supported_identifiers=[],
        # method_name="did:indy",
    ).provide(context.settings, context.injector)
    await indy_registry.setup(context)
    registry.register(indy_registry)
