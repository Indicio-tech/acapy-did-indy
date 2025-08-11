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
from did_indy.driver.api.namespaces import NamespaceInfo

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

    use_ledgers_from_driver = plugin_settings.get("ledgers_from_driver", True)
    LOGGER.debug("Fetching ledgers from did-indy driver...")
    
    # Try to communicate with the driver.
    try:
        driver_ledgers = [
            NamespaceInfo.model_validate(namespace_info)
            for namespace_info in await client.get_namespaces()
        ]

        driver_ledgers = {
            namespace.namespace: LedgerPool(
                name=namespace.namespace,
                genesis_transactions=namespace.genesis_transaction,
                cache=BasicCache()
            )
            for namespace in driver_ledgers
        }
    except Exception as e:
        if use_ledgers_from_driver:
            LOGGER.error(f"Could not fetch namespaces from driver: {e}. Since `ledgers_from_driver` is true, cannot complete setup.")
            return
        else:
            LOGGER.warning(f"Could not fetch namespaces from driver: {e}. Since `ledgers_from_driver` is false, using namespaces from acapy-did-indy plugin.")
            LOGGER.warning("ACA-Py can only support DID resolution.")
            driver_ledgers = None
    
    if use_ledgers_from_driver:
        assert driver_ledgers is not None
        ledgers = driver_ledgers
    else:
        # Load the ledger information from the plugin.
        ledgers = plugin_settings.get("ledgers")
        if ledgers is None:
            LOGGER.error(
                "`ledgers_from_driver` is false, but no ledger was specified in the plugin configuration."
            )
            return

        if driver_ledgers is not None:
            plugin_namespaces = ledgers.keys()
            driver_namespaces = driver_ledgers.keys()
            namespace_diff = plugin_namespaces ^ driver_namespaces

            # If we are able to contact the driver, and the driver and plugin have a 
            # different configuration, we use the driver's
            if namespace_diff:
                LOGGER.warning(
                    f"""\
The plugin and the did-indy driver use different namespaces. Using the driver's configuration.
    The plugin has namespaces: {list(plugin_namespaces)}
    The driver has namespaces: {list(driver_namespaces)}\
"""
                )
                ledgers = driver_ledgers
        else:
            # We only use the plugin configuration if:
            #   1. `ledgers_from_driver` is False
            #   2. We are unable to contact the driver.
            # In this case, we are only able to support DID resolution.
            ledgers = {
                namespace: LedgerPool(
                    name=namespace,
                    genesis_transactions=await fetch_genesis_transactions(ledgers[namespace]),
                    cache=BasicCache(),
                )
                for namespace in ledgers.keys()
            } if ledgers else {}

    ledgers = Ledgers(ledgers)
    LOGGER.debug("Using namespaces %s", list(ledgers.ledgers.keys()))
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
