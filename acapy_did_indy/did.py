"""Define DID Methods."""
from aries_cloudagent.wallet.did_method import DIDMethod, HolderDefinedDid
from aries_cloudagent.wallet.key_type import ED25519

INDY = DIDMethod(
    name="indy",
    key_types=[ED25519],
    rotation=True,
    holder_defined_did=HolderDefinedDid.NO,
)
