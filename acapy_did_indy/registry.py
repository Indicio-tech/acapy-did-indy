"""DID Indy Registry."""

import logging
import re
from typing import Optional, Pattern, Sequence

from acapy_agent.config.injection_context import InjectionContext
from acapy_agent.core.profile import Profile
from acapy_agent.anoncreds.base import BaseAnonCredsRegistrar, BaseAnonCredsResolver
from acapy_agent.anoncreds.models.credential_definition import (
    CredDef,
    CredDefResult,
    GetCredDefResult,
    CredDefState,
    CredDefValue,
    CredDefValuePrimary,
    CredDefValueRevocation,
)
from acapy_agent.anoncreds.models.revocation import (
    GetRevListResult,
    GetRevRegDefResult,
    RevList,
    RevListResult,
    RevRegDef,
    RevRegDefValue,
    RevRegDefResult,
    RevRegDefState,
    RevListState,
)
from acapy_agent.anoncreds.models.schema import (
    AnonCredsSchema,
    GetSchemaResult,
    SchemaResult,
    SchemaState,
)
from acapy_agent.anoncreds.models.schema_info import AnonCredsSchemaInfo
from did_indy.anoncreds import make_indy_schema_id
from did_indy.client.client import IndyDriverClient
from did_indy.ledger import Ledger, LedgerPool, LedgerTransactionError
from acapy_agent.wallet.base import BaseWallet
from acapy_agent.core.error import BaseError
from .author import AuthorSession
from anoncreds import (
    Schema,
)
from uuid import uuid4


LOGGER = logging.getLogger(__name__)

class IndyRegistryError(BaseError):
    """Raised on errors in registrar."""


class IndyRegistry(BaseAnonCredsResolver, BaseAnonCredsRegistrar):
    """DIDIndyRegistry."""

    def __init__(self, client: IndyDriverClient):
        """Initialize an instance.

        Args:
            None

        """
        self._supported_identifiers_regex = re.compile(r"^did:indy:.+$")
        self.client = client

    @property
    def supported_identifiers_regex(self) -> Pattern:
        """Supported Identifiers regex."""
        return self._supported_identifiers_regex

    async def setup(self, context: InjectionContext) -> None:
        """Setup."""
        LOGGER.info("Successfully registered DIDIndyRegistry")

    async def get_schema(self, profile: Profile, schema_id: str) -> GetSchemaResult:
        """Get a schema from the registry."""
        LOGGER.debug("ANONCREDS: get_schema %s", schema_id)
        
        async with profile.session() as session:
            ledger_pool = session.inject(LedgerPool)
        async with Ledger(ledger_pool) as ledger:
            try:
                schema_deref = await ledger.get_schema(schema_id)
            except LedgerTransactionError as error:
                LOGGER.exception("Failed to retrieve schema")
                raise IndyRegistryError(f"Cannot retrieve schema: {error}") from error

        schema = schema_deref.contentStream
        return GetSchemaResult(
            schema=AnonCredsSchema(
                issuer_id=schema_id.split("/", maxsplit=1)[0],
                attr_names=schema.attr_names,
                name=schema.name,
                version=schema.version,
            ),
            schema_id=schema_id,
            resolution_metadata=schema_deref.dereferencingMetadata,
            schema_metadata=schema_deref.contentMetadata.model_dump(),
        )

    async def register_schema(
        self,
        profile: Profile,
        schema: AnonCredsSchema,
        options: Optional[dict] = None,
    ) -> SchemaResult:
        """Register a schema on the registry."""
        LOGGER.debug("ANONCREDS: register_schema %s - %s", schema.issuer_id, schema.name)

        async with profile.session() as session:
            wallet = session.inject(BaseWallet)
            if schema.issuer_id:
                public_did = await wallet.get_local_did(schema.issuer_id)
            else:
                public_did = await wallet.get_public_did()

            if not public_did:
                raise IndyRegistryError("No nym provided and public DID not set")
            author_session = session.inject(AuthorSession)

        LOGGER.debug("Using DID to register schema: %s", schema.issuer_id)
        async with author_session.with_verkey(public_did.verkey) as author:

            LOGGER.debug("Registering schema: %s", schema)
            schema_response = await author.register_schema(schema.to_native(), author_session.taa)

        LOGGER.debug("Schema registered and saving to wallet: %s", schema_response)
        

        return SchemaResult(
            job_id=uuid4().hex,
            schema_state=SchemaState(
                state=SchemaState.STATE_FINISHED,
                schema_id=schema_response.schema_id,
                schema=AnonCredsSchema.from_native(
                    Schema.create(
                        name=schema_response.registration_metadata.txn.data.data.name,
                        version=schema_response.registration_metadata.txn.data.data.version,
                        attr_names=schema_response.registration_metadata.txn.data.data.attr_names,
                        issuer_id=schema_response.schema_id,
                    )),
            ),
            registration_metadata=schema_response.registration_metadata.model_dump(),
            schema_metadata=schema_response.schema_metadata.model_dump(),
        )

    async def get_credential_definition(
        self, profile: Profile, credential_definition_id: str
    ) -> GetCredDefResult:
        """Get a credential definition from the registry."""
        LOGGER.debug("ANONCREDS: get_credential_definition %s", credential_definition_id)
        async with profile.session() as session:
            ledger_pool = session.inject(LedgerPool)
        async with Ledger(ledger_pool) as ledger:
            try:
                cred_def_deref = await ledger.get_cred_def(credential_definition_id)
            except LedgerTransactionError as error:
                LOGGER.exception("Failed to retrieve credential definition")
                raise IndyRegistryError(f"Cannot retrieve credential definition: {error}") from error

            pool_name = ledger.pool.name

        issuer_id = credential_definition_id.split("/", maxsplit=1)[0]
        return GetCredDefResult(
            credential_definition_id=credential_definition_id,
            credential_definition=CredDef(
                issuer_id=issuer_id,
                schema_id=make_indy_schema_id(
                    issuer_id=issuer_id,
                    name=pool_name,
                    version="v0",  # TODO: is this right?
                ),
                type=cred_def_deref.contentMetadata.nodeResponse.result.signature_type,
                tag=cred_def_deref.contentMetadata.nodeResponse.result.tag,
                value=CredDefValue(
                    primary=CredDefValuePrimary.deserialize(cred_def_deref.contentStream.primary),
                    revocation=CredDefValueRevocation.deserialize(cred_def_deref.contentStream.revocation, none2none=True),
                ),
            ),
            resolution_metadata=cred_def_deref.dereferencingMetadata,
            credential_definition_metadata=cred_def_deref.contentMetadata.model_dump(),
        )

    async def register_credential_definition(
        self,
        profile: Profile,
        schema: GetSchemaResult,
        credential_definition: CredDef,
        options: Optional[dict] = None,
    ) -> CredDefResult:
        """Register a credential definition on the registry."""
        LOGGER.debug(
            "ANONCREDS: register_credential_definition %s",
            credential_definition,
        )

        async with profile.session() as session:
            wallet = session.inject(BaseWallet)
            if credential_definition.issuer_id:
                public_did = await wallet.get_local_did(credential_definition.issuer_id)
            else:
                public_did = await wallet.get_public_did()

            if not public_did:
                raise IndyRegistryError("No nym provided and public DID not set")
            author_session = session.inject(AuthorSession)

        LOGGER.debug("Using DID to register credential definition: %s", credential_definition.issuer_id)
        async with author_session.with_verkey(public_did.verkey) as author:

            LOGGER.debug("Registering credential definition: %s", credential_definition)
            cred_def_response = await author.register_cred_def(credential_definition.to_native(), author_session.taa)
            LOGGER.debug("Credential definition registered: %s", cred_def_response)

        return CredDefResult(
            # job_id=uuid4().hex,
            None,  # Job ID is not used in this implementation
            credential_definition_state=CredDefState(
                state=CredDefState.STATE_FINISHED,
                credential_definition_id=cred_def_response.cred_def_id,
                credential_definition=credential_definition,
            ),
            registration_metadata=cred_def_response.registration_metadata.model_dump(),
            credential_definition_metadata=cred_def_response.cred_def_metadata.model_dump(),
        )

    async def get_revocation_registry_definition(
        self, profile: Profile, revocation_registry_id: str
    ) -> GetRevRegDefResult:
        """Get a revocation registry definition from the registry."""
        LOGGER.debug(
            "ANONCREDS: get_revocation_registry_definition %s", revocation_registry_id
        )
        async with profile.session() as session:
            ledger_pool = session.inject(LedgerPool)
        async with Ledger(ledger_pool) as ledger:
            try:
                rev_reg_def_deref = await ledger.get_rev_reg_def(revocation_registry_id)
            except LedgerTransactionError as error:
                LOGGER.exception("Failed to retrieve revocation registry definition")
                raise IndyRegistryError(f"Cannot retrieve revocation registry definition: {error}") from error

        return GetRevRegDefResult(
            revocation_registry_id=revocation_registry_id,
            revocation_registry=RevRegDef(
                issuer_id=revocation_registry_id.split("/", maxsplit=1)[0], # TODO
                type="CL_ACCUM",
                cred_def_id=rev_reg_def_deref.contentStream.cred_def_id,
                tag=rev_reg_def_deref.contentStream.tag,
                value=RevRegDefValue(
                    public_keys=rev_reg_def_deref.contentStream.value.public_keys,
                    max_cred_num=rev_reg_def_deref.contentStream.value.max_cred_num,
                    tails_location=rev_reg_def_deref.contentStream.value.tails_location,
                    tails_hash=rev_reg_def_deref.contentStream.value.tails_hash,
                ),
            ),
            resolution_metadata=rev_reg_def_deref.dereferencingMetadata,
            revocation_registry_metadata=rev_reg_def_deref.contentMetadata.model_dump(),
        )

    async def register_revocation_registry_definition(
        self,
        profile: Profile,
        revocation_registry_definition: RevRegDef,
        options: Optional[dict] = None,
    ) -> RevRegDefResult:
        """Register a revocation registry definition on the registry."""
        LOGGER.debug(
            "ANONCREDS: register_revocation_registry_definition %s",
            revocation_registry_definition,
        )

        async with profile.session() as session:
            wallet = session.inject(BaseWallet)
            if revocation_registry_definition.issuer_id:
                public_did = await wallet.get_local_did(revocation_registry_definition.issuer_id)
            else:
                public_did = await wallet.get_public_did()

            if not public_did:
                raise IndyRegistryError("No nym provided and public DID not set")

            author_session = session.inject(AuthorSession)

        LOGGER.debug("Using DID to register revocation registry definition: %s", revocation_registry_definition.issuer_id)
        async with author_session.with_verkey(public_did.verkey) as author:

            LOGGER.debug("Registering revocation registry definition: %s", revocation_registry_definition)
            rev_reg_response = await author.register_rev_reg_def(revocation_registry_definition.to_native(), author_session.taa)
            LOGGER.debug("Revocation registry definition registered: %s", rev_reg_response)

        return RevRegDefResult(
            job_id=uuid4().hex,
            revocation_registry_definition_state=RevRegDefState(
                state=RevRegDefState.STATE_FINISHED,
                revocation_registry_definition_id=rev_reg_response.indy_rev_reg_def_id,
                revocation_registry_definition=revocation_registry_definition,
            ),
            registration_metadata=rev_reg_response.registration_metadata.model_dump(),
            revocation_registry_definition_metadata=rev_reg_response.rev_reg_def_metadata.model_dump(),
        )

    async def get_revocation_list(
        self,
        profile: Profile,
        revocation_registry_id: str,
        timestamp_from: Optional[int] = 0,
        timestamp_to: Optional[int] = None,
    ) -> GetRevListResult:
        """Get a revocation list from the registry."""
        LOGGER.info("ANONCREDS: get_revocation_list %s", revocation_registry_id)
        raise NotImplementedError()

    async def register_revocation_list(
        self,
        profile: Profile,
        rev_reg_def: RevRegDef,
        rev_list: RevList,
        options: Optional[dict] = None,
    ) -> RevListResult:
        """Register a revocation list on the registry."""
        LOGGER.debug(
            "ANONCREDS: register_revocation_list %s", rev_reg_def
        )

        async with profile.session() as session:
            wallet = session.inject(BaseWallet)
            if rev_reg_def.issuer_id:
                public_did = await wallet.get_local_did(rev_reg_def.issuer_id)
            else:
                public_did = await wallet.get_public_did()

            if not public_did:
                raise IndyRegistryError("No nym provided and public DID not set")

            author_session = session.inject(AuthorSession)

        LOGGER.debug("Using DID to register revocation status list: %s", rev_reg_def.issuer_id)
        async with author_session.with_verkey(public_did.verkey) as author:

            LOGGER.debug("Registering revocation status list: %s", rev_reg_def)
            rev_status_list_response = await author.register_rev_status_list(rev_list.to_native(), author_session.taa)
            LOGGER.debug("Revocation status list registered: %s", rev_status_list_response)


        return RevListResult(
            job_id=uuid4().hex,
            revocation_list_state=RevListState(
                state=RevRegDefState.STATE_FINISHED,
                revocation_list=rev_list,
            ),
            registration_metadata=rev_status_list_response.registration_metadata.model_dump(),
            revocation_list_metadata=rev_status_list_response.rev_status_list_metadata.model_dump(),
        )

    async def update_revocation_list(
        self,
        profile: Profile,
        rev_reg_def: RevRegDef,
        prev_list: RevList,
        curr_list: RevList,
        revoked: Sequence[int],
        options: Optional[dict] = None,
    ) -> RevListResult:
        """Update a revocation list on the registry."""
        LOGGER.debug(
            "ANONCREDS: update_revocation_list %s", rev_reg_def
        )

        async with profile.session() as session:
            wallet = session.inject(BaseWallet)
            if rev_reg_def.issuer_id:
                public_did = await wallet.get_local_did(rev_reg_def.issuer_id)
            else:
                public_did = await wallet.get_public_did()

            if not public_did:
                raise IndyRegistryError("No nym provided and public DID not set")

            author_session = session.inject(AuthorSession)

        LOGGER.debug("Using DID to update revocation status list: %s", rev_reg_def.issuer_id)
        async with author_session.with_verkey(public_did.verkey) as author:

            LOGGER.debug("Updating revocation status list: %s", rev_reg_def)
            rev_status_list_response = await author.update_rev_status_list(
                prev_list=prev_list.to_native(),
                curr_list=curr_list.to_native(),
                revoked=list(revoked),
                taa=author_session.taa,
            )
            LOGGER.debug("Revocation status list updated: %s", rev_status_list_response)


        return RevListResult(
            job_id=uuid4().hex,
            revocation_list_state=RevListState(
                state=RevRegDefState.STATE_FINISHED,
                revocation_list=curr_list,
            ),
            registration_metadata=rev_status_list_response.registration_metadata.model_dump(),
            revocation_list_metadata=rev_status_list_response.rev_status_list_metadata.model_dump(),
        )

    async def get_schema_info_by_id(
        self, profile: Profile, schema_id: str
    ) -> AnonCredsSchemaInfo:
        """Get a schema info from the registry."""
        LOGGER.debug("ANONCREDS: get_schema_info_by_id %s", schema_id)
        schema_results = await self.get_schema(profile, schema_id)
        if not schema_results.schema:
            raise IndyRegistryError(f"Schema with ID {schema_id} not found")
        schema = schema_results.schema
        schema_info = AnonCredsSchemaInfo(
            issuer_id=schema.issuer_id,
            name=schema.name,
            version=schema.version,
        )
        LOGGER.debug("Schema info retrieved: %s", schema_info)
        return schema_info
