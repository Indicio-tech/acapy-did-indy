"""did:indy support."""

import logging

from acapy_agent.config.injection_context import InjectionContext
from acapy_agent.wallet.did_method import DIDMethods
from acapy_agent.resolver.did_resolver import DIDResolver
from acapy_agent.anoncreds.registry import AnonCredsRegistry
from acapy_agent.config.provider import ClassProvider

from did_indy.ledger import ReadOnlyLedger, LedgerPool, fetch_genesis_transactions
from did_indy.client.client import IndyDriverClient
from did_indy.cache import BasicCache
from acapy_agent.core.profile import Profile

from .did import INDY
from .author import AuthorSession
from .registrar import IndyRegistrar
from .registry import IndyRegistry
from .resolver import IndyResolver


LOGGER = logging.getLogger(__name__)

async def setup(context: InjectionContext):
    LOGGER.debug("Starting setup for acapy_did_indy plugin")
    plugin_settings = context.settings.for_plugin("acapy_did_indy")
    
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

    API_KEY = plugin_settings.get("api_key")
    if API_KEY is None:
        LOGGER.error("No API key found. Please provide an API key using the `api_key` ACA-py plugin variable.")
        return

    DRIVER = plugin_settings.get("driver_uri", "http://driver")
    LOGGER.debug("Using driver endpoint " + DRIVER)

    client = IndyDriverClient(DRIVER, client_api_key=API_KEY)
    context.injector.bind_instance(IndyDriverClient, client)

    NAMESPACE = plugin_settings.get("indy_namespace")
    if NAMESPACE is None:
        LOGGER.error("Indy namespace not specified. Please do so using the `indy_namespace` ACA-py plugin variable.")
        return 
    LOGGER.debug("Using indy namespace " + NAMESPACE)

    ledger_pool = LedgerPool(
        name=NAMESPACE,
        genesis_transactions=await fetch_genesis_transactions(
            "https://raw.githubusercontent.com/Indicio-tech/indicio-network/main/genesis_files/pool_transactions_testnet_genesis"
        ),
        cache=BasicCache()
    )
    # We bind an instance to take advantage of the caching in LedgerPool
    context.injector.bind_instance(LedgerPool, ledger_pool)

    context.injector.bind_provider(AuthorSession, ClassProvider(
        "acapy_did_indy.author.AuthorSession",
        client=client,
        pool=ledger_pool,
        profile=ClassProvider.Inject(Profile),
    ))

    # Registrar
    context.injector.bind_instance(
        IndyRegistrar,
        IndyRegistrar(
            context.settings,
        )
    )

    # Registry
    indy_registry = IndyRegistry(client)
    indy_registry = ClassProvider(
        "acapy_did_indy.registry.IndyRegistry",
        client=client,
        # supported_identifiers=[],
        # method_name="did:indy",
    ).provide(context.settings, context.injector)
    await indy_registry.setup(context)
    registry.register(indy_registry)
    context.injector.bind_instance(IndyRegistry, indy_registry)

    LOGGER.debug("acapy_did_indy plugin setup complete")
