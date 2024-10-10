"""did:indy support."""
from aries_cloudagent.config.injection_context import InjectionContext
from aries_cloudagent.wallet.did_method import DIDMethods
from aries_cloudagent.resolver.did_resolver import DIDResolver

from .did import INDY
from .registrar import IndyRegistrar
from .resolver import IndyResolver

async def setup(context: InjectionContext):
    methods = context.inject(DIDMethods)
    methods.register(INDY)

    indy_resolver = IndyResolver()
    await indy_resolver.setup(context)
    resolver = context.inject(DIDResolver)
    resolver.register_resolver(indy_resolver)
    context.injector.bind_instance(IndyRegistrar, IndyRegistrar(context.settings))
