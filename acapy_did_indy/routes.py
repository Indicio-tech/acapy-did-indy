"""Routes for creating did:web."""

from aiohttp import web
from aiohttp_apispec import docs, request_schema, response_schema
from aries_cloudagent.admin.request_context import AdminRequestContext
from aries_cloudagent.messaging.models.openapi import OpenAPISchema
from aries_cloudagent.protocols.coordinate_mediation.v1_0.route_manager import (
    RouteManager,
)
from aries_cloudagent.storage.base import StorageNotFoundError
from marshmallow import fields

from .registrar import IndyRegistrar


class CreateDIDIndyRequestSchema(OpenAPISchema):
    """Request schema for creating a did:web."""

    nym = fields.Str(
        required=False,
        metadata={
            "description": "The nym this did will be based on; defaults to nym of public DID"
        },
    )
    ldp_vc = fields.Bool(
        required=False,
        metadata={
            "description": "Support LDP-VC issuance with this DID; defaults to False"
        },
    )
    didcomm = fields.Bool(
        required=False,
        metadata={"description": "Support DIDComm with this DID; defaults to True"},
    )
    mediation_id = fields.Str(
        required=False,
        metadata={"description": "Mediation record ID to be used in DIDComm service"},
    )


class CreateDIDResponseSchema(OpenAPISchema):
    """Response schema for creating a did:web."""

    did = fields.Str(
        required=True,
        metadata={
            "description": "The created did:web",
        },
    )


@docs(
    tags=["did"],
    summary="Create DID Indy.",
)
@request_schema(CreateDIDIndyRequestSchema())
@response_schema(CreateDIDResponseSchema())
async def create_did_indy(request: web.Request):
    """Route for creating a did:indy."""

    context: AdminRequestContext = request["context"]
    registrar = context.inject(IndyRegistrar)

    body = await request.json()
    nym = body.get("nym")
    ldp_vc = body.get("ldp_vc", False)
    didcomm = body.get("didcomm", True)
    mediation_id = body.get("mediation_id")

    if mediation_id and not didcomm:
        raise web.HTTPBadRequest(reason="mediation_id set but didcomm is not set")

    route_manager = context.inject(RouteManager)
    try:
        mediation_record = await route_manager.mediation_record_if_id(
            profile=context.profile,
            mediation_id=mediation_id,
            or_default=didcomm,
        )
    except StorageNotFoundError:
        raise web.HTTPNotFound(reason=f"No mediation record with id {mediation_id}")

    try:
        did_info = await registrar.from_public_nym(
            context.profile,
            nym,
            didcomm=didcomm,
            ldp_vc=ldp_vc,
            mediation_records=[mediation_record] if mediation_record else None,
        )
    except Exception:
        raise web.HTTPInternalServerError(reason="Could not create did:indy from public nym")

    return web.json_response({"did": did_info.did})


async def register(app: web.Application):
    """Register routes."""
    app.add_routes(
        [
            web.post("/did/indy/from-nym", create_did_indy),
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
