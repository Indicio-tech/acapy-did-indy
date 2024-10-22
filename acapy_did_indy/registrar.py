"""did:indy registrar."""

import json
from os import getenv
from typing import List

from aries_cloudagent.config.settings import Settings
from aries_cloudagent.core.error import BaseError
from aries_cloudagent.core.profile import Profile
from aries_cloudagent.ledger.base import BaseLedger
from aries_cloudagent.protocols.coordinate_mediation.v1_0.models.mediation_record import (
    MediationRecord,
)
from aries_cloudagent.protocols.coordinate_mediation.v1_0.route_manager import (
    RouteManager,
)
from aries_cloudagent.utils.multiformats import multibase, multicodec
from aries_cloudagent.wallet.base import BaseWallet
from aries_cloudagent.wallet.did_info import DIDInfo
from aries_cloudagent.wallet.error import WalletNotFoundError
from aries_cloudagent.wallet.key_type import ED25519
import base58
from indy_vdr import ledger
from pydid.verification_method import Ed25519VerificationKey2020

from .did import INDY


class IndyRegistrarError(BaseError):
    """Raised on errors in registrar."""


class IndyRegistrar:
    """did:indy registrar."""

    def __init__(self, settings: Settings):
        """Initialize the registrar."""
        config = settings.for_plugin("acapy_did_indy")
        namespace = config.get("indy_namespace") or getenv("INDY_NAMESPACE")

        if not namespace:
            raise IndyRegistrarError("Namespace is not configured; cannot init registrar")

        self.namespace = namespace


    async def prepare_didcomm_services(
        self,
        profile: Profile,
        mediation_records: List[MediationRecord] | None = None
    ):
        """Prepare didcomm service for adding to diddocContent."""
        svc_endpoints = []
        default_endpoint = profile.settings.get("default_endpoint")
        if default_endpoint:
            svc_endpoints.append(default_endpoint)
        svc_endpoints.extend(profile.settings.get("additional_endpoints", []))

        route_manager = profile.inject(RouteManager)
        routing_keys: List[str] = []
        if mediation_records:
            for mediation_record in mediation_records:
                (
                    mediator_routing_keys,
                    endpoint,
                ) = await route_manager.routing_info(profile, mediation_record)
                routing_keys = [*routing_keys, *(mediator_routing_keys or [])]
                if endpoint:
                    svc_endpoints = [endpoint]

        services = []
        for index, endpoint in enumerate(svc_endpoints or []):
            services.append(
                {
                    "id": f"#didcomm-{index}",
                    "type": "did-communication",
                    "recipientKeys": ["#key-0"],
                    "routingKeys": routing_keys,
                    "serviceEndpoint": endpoint,
                    "priority": index,
                }
            )
        return services

    async def from_public_nym(
        self,
        profile: Profile,
        nym: str | None,
        *,
        didcomm: bool = True,
        ldp_vc: bool = False,
        mediation_records: List[MediationRecord] | None = None
    ) -> DIDInfo:
        """Create a did:indy from an already published nym.

        If nym is not provided, current public "did" is used.
        """
        if mediation_records and not didcomm:
            raise ValueError("Mediation records passed but didcomm flag not set")

        async with profile.session() as session:
            wallet = session.inject(BaseWallet)
            if nym:
                public_did = await wallet.get_local_did(nym)
            else:
                public_did = await wallet.get_public_did()

            if not public_did:
                raise IndyRegistrarError("No nym provided and public DID not set")
            did = f"did:indy:{self.namespace}:{public_did.did}"

            # Exists?
            try:
                previous = await wallet.get_local_did(did)
                return previous
            except WalletNotFoundError:
                pass

            # Enable ldp-vc issuance?
            if ldp_vc:
                kid = f"{did}#assert"
                key = await wallet.create_key(key_type=ED25519, kid=kid)
                public_key_multibase = multibase.encode(
                    multicodec.wrap("ed25519-pub", base58.b58decode(key.verkey)),
                    "base58btc",
                )
                did_info = DIDInfo(
                    did=did,
                    # TODO ACA-Py's cred issuance signatures currently rely on the verkey of
                    # the DIDInfo object being the signer
                    verkey=key.verkey,
                    metadata={
                        "namespace": self.namespace,
                    },
                    method=INDY,
                    key_type=ED25519,
                )
                await wallet.store_did(did_info)
                vm = Ed25519VerificationKey2020.make(
                    id=kid, controller=did, public_key_multibase=public_key_multibase
                )
                doc_content = {
                    "@context": ["https://w3id.org/security/suites/ed25519-2020/v1"],
                    "verificationMethod": [vm.serialize()],
                    "assertionMethod": [vm.id],
                }
            else:
                did_info = DIDInfo(
                    did=did,
                    verkey=public_did.verkey,
                    metadata={
                        "namespace": self.namespace,
                    },
                    method=INDY,
                    key_type=ED25519,
                )
                await wallet.store_did(did_info)
                doc_content = {}

            if didcomm:
                services = await self.prepare_didcomm_services(profile, mediation_records)
                doc_content["service"] = services

            nym_txn = ledger.build_nym_request(
                public_did.did, public_did.did, diddoc_content=json.dumps(doc_content)
            )
            base_ledger = session.inject(BaseLedger)
            async with base_ledger:
                await base_ledger.txn_submit(nym_txn, sign=True, sign_did=public_did)
                attrib_txn = ledger.build_attrib_request(
                    public_did.did,
                    public_did.did,
                    xhash=None,
                    raw=json.dumps({"diddocContent": doc_content}),
                    enc=None,
                )
                await base_ledger.txn_submit(attrib_txn, sign=True, sign_did=public_did)

            return did_info
