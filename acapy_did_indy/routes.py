"""Routes for creating did:web."""

import json
from os import getenv
from urllib.parse import urlparse

from aiohttp import web
from aiohttp_apispec import docs, request_schema, response_schema
from aries_cloudagent.admin.request_context import AdminRequestContext
from aries_cloudagent.ledger.base import BaseLedger
from aries_cloudagent.messaging.models.openapi import OpenAPISchema
from aries_cloudagent.utils.multiformats import multibase, multicodec
from aries_cloudagent.wallet.base import BaseWallet
from aries_cloudagent.wallet.did_info import DIDInfo
from aries_cloudagent.wallet.error import WalletNotFoundError
from aries_cloudagent.wallet.key_type import ED25519
import base58
from marshmallow import fields
from pydid import DIDDocumentBuilder
from pydid.verification_method import Ed25519VerificationKey2020
from indy_vdr import ledger

from . import DidWebServerClient, INDY, WEB


class CreateDIDWebRequestSchema(OpenAPISchema):
    """Request schema for creating a did:web."""

    url = fields.Str(
        required=False,
        metadata={"description": "The url where the did.json for this DID will reside"},
    )
    name = fields.Str(
        required=False,
        metadata={
            "description": "Named location for this did to be posted to the did web server"
        },
    )
    issue = fields.Bool(
        required=False,
        metadata={"description": "Support issuance with this DID"},
    )
    didcomm = fields.Bool(
        required=False, metadata={"description": "Support DIDComm with this DID"}
    )


class CreateDIDWebResponseSchema(OpenAPISchema):
    """Response schema for creating a did:web."""

    did = fields.Str(
        required=True,
        metadata={
            "description": "The created did:web",
        },
    )


def url_to_did_web(url: str) -> str:
    """Convert a URL into a did:web did."""

    # Make sure that the URL starts with a scheme
    if not url.startswith("http"):
        url = f"https://{url}"

    # Parse it out to we can grab pieces
    parsed_url = urlparse(url)

    # Assemble the domain portion of the DID
    did = "did:web:" + parsed_url.netloc.replace(":", "%3A")

    # Cleanup the path
    path = parsed_url.path.replace(".well-known/did.json", "")
    path = path.replace("/did.json", "")

    # Add the path portion of the did
    if len(path) > 1:
        did += path.replace("/", ":")
    return did


@docs(
    tags=["did"],
    summary="Create DID Web.",
)
@request_schema(CreateDIDWebRequestSchema())
@response_schema(CreateDIDWebResponseSchema())
async def create_did_web(request: web.Request):
    """Route for creating a did:web."""

    context: AdminRequestContext = request["context"]
    client = context.inject(DidWebServerClient)
    body = await request.json()
    url = body.get("url")
    name = body.get("name")
    if not url and not name:
        raise web.HTTPBadRequest(reason="Either url or name is required")

    if url:
        did = url_to_did_web(url)
    else:
        did = url_to_did_web(f"{client.base_url}/{name}")

    issue = body.get("issue", False)
    didcomm = body.get("didcomm", False)

    async with context.session() as session:
        wallet = session.inject(BaseWallet)
        kid = f"{did}#key-0"
        key = await wallet.create_key(ED25519, kid=kid)

        public_key_multibase = multibase.encode(
            multicodec.wrap("ed25519-pub", base58.b58decode(key.verkey)), "base58btc"
        )
        if not url:
            builder = DIDDocumentBuilder(did)
            vm = builder.verification_method.add(
                Ed25519VerificationKey2020,
                "key-0",
                public_key_multibase=public_key_multibase,
            )
            builder.authentication.reference(vm.id)
            if issue:
                builder.assertion_method.reference(vm.id)

            if didcomm:
                # TODO add dicomm service
                pass

            document = builder.build()
            await client.put_did(name, document.serialize())

        did_info = DIDInfo(
            did=did,
            verkey=key.verkey,
            metadata={},
            method=WEB,
            key_type=ED25519,
        )

        await wallet.store_did(did_info)

        return web.json_response({"did": did})


@docs(
    tags=["did"],
    summary="Create DID Indy.",
)
@response_schema(CreateDIDWebResponseSchema())
async def create_did_indy(request: web.Request):
    """Route for creating a did:indy."""

    context: AdminRequestContext = request["context"]
    config = context.settings.for_plugin("acapy_did_indy")
    indy_namespace = config.get("indy_namespace") or getenv("INDY_NAMESPACE")

    async with context.session() as session:
        wallet = session.inject(BaseWallet)
        public_did = await wallet.get_public_did()
        if not public_did:
            raise web.HTTPBadRequest(reason="Public DID must be set")
        did = f"did:indy:{indy_namespace}:{public_did.did}"

        # Exists?
        try:
            previous = await wallet.get_local_did(did)
            return web.json_response({"did": previous.did})
        except WalletNotFoundError:
            pass

        # Enable issuance
        kid = f"{did}#assert"
        key = await wallet.create_key(
            key_type=ED25519, kid=kid
        )
        public_key_multibase = multibase.encode(
            multicodec.wrap("ed25519-pub", base58.b58decode(key.verkey)), "base58btc"
        )
        did_info = DIDInfo(
            did=did,
            verkey=key.verkey,
            metadata={},
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
            "assertionMethod": [vm.id]
        }
        nym_txn = ledger.build_nym_request(
            public_did.did, public_did.did, diddoc_content=json.dumps(doc_content)
        )
        base_ledger = session.inject(BaseLedger)
        await base_ledger.txn_submit(nym_txn, sign=True, sign_did=public_did)
        attrib_txn = ledger.build_attrib_request(
            public_did.did,
            public_did.did,
            xhash=None,
            raw=json.dumps({"diddocContent": doc_content}),
            enc=None,
        )
        await base_ledger.txn_submit(attrib_txn, sign=True, sign_did=public_did)

        return web.json_response({"did": did})


async def register(app: web.Application):
    """Register routes."""
    app.add_routes(
        [
            web.post("/did/web/create", create_did_web),
            web.post("/did/indy/create", create_did_indy),
        ]
    )


def post_process_routes(app: web.Application):
    """Amend swagger API."""

    # Add top-level tags description
    if "tags" not in app._state["swagger_dict"]:
        app._state["swagger_dict"]["tags"] = []

    app._state["swagger_dict"]["tags"].append(
        {
            "name": "did",
            "description": "DID Registration",
        }
    )
