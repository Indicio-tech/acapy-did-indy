"""did:indy support."""

import logging

from acapy_agent.anoncreds.registry import AnonCredsRegistry
from acapy_agent.config.injection_context import InjectionContext
from acapy_agent.config.provider import ClassProvider
from acapy_agent.core.profile import ProfileSession
from acapy_agent.resolver.did_resolver import DIDResolver
from acapy_agent.wallet.did_method import DIDMethods
from did_indy.author.author import Author
from did_indy.cache import BasicCache
from did_indy.client.client import IndyDriverClient
from did_indy.driver.ledgers import Ledgers
from did_indy.ledger import LedgerPool, fetch_genesis_transactions
from did_indy.resolver import Resolver as DidIndyACResolver

from .author import AcapyAuthorDeps
from .did import INDY
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
        LOGGER.error(
            "No API key found. Please provide an API key using the `api_key` ACA-py plugin variable."
        )
        return

    DRIVER = plugin_settings.get("driver_uri", "http://driver")
    LOGGER.debug("Using driver endpoint " + DRIVER)

    client = IndyDriverClient(DRIVER, client_api_key=API_KEY)
    context.injector.bind_instance(IndyDriverClient, client)

    ledgers = plugin_settings.get("ledgers")
    ledgers = {
        namespace: LedgerPool(
            name=namespace,
            genesis_transactions=await fetch_genesis_transactions(ledgers[namespace]),
            cache=BasicCache(),
        )
        for namespace in ledgers.keys()
    } if ledgers else {}

    ledgers = Ledgers(ledgers)
    context.injector.bind_instance(Ledgers, ledgers)

    context.injector.bind_provider(
        AcapyAuthorDeps,
        ClassProvider(AcapyAuthorDeps, session=ClassProvider.Inject(ProfileSession)),
    )

    resolver = DidIndyACResolver(ledgers)
    context.injector.bind_instance(DidIndyACResolver, resolver)

    context.injector.bind_provider(
        Author,
        ClassProvider(
            Author,
            client=client,
            depends=ClassProvider.Inject(AcapyAuthorDeps),
        ),
    )

    # Registrar
    context.injector.bind_instance(
        IndyRegistrar,
        IndyRegistrar(),
    )

    # Registry
    indy_registry = IndyRegistry()
    await indy_registry.setup(context)
    registry.register(indy_registry)
    context.injector.bind_instance(IndyRegistry, indy_registry)

    LOGGER.debug("acapy_did_indy plugin setup complete")
