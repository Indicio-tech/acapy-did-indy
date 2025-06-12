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
from did_indy.client.client import IndyDriverClient
from did_indy.ledger import Ledger, LedgerPool, LedgerTransactionError
from did_indy.author.author import Author, AuthorDependencies
from aries_askar import Key
from acapy_agent.wallet.base import BaseWallet
from acapy_agent.core.error import BaseError
from did_indy.models.taa import TaaAcceptance
from anoncreds import (
    CredentialDefinition,
    RevocationRegistryDefinition,
    RevocationStatusList,
    Schema,
)
from uuid import uuid4

from base58 import b58decode as b58_to_bytes


LOGGER = logging.getLogger(__name__)

# TODO: FIX
NAMESPACE = "indicio:test"

class IndyRegistryError(BaseError):
    """Raised on errors in registrar."""


class AuthorDependenciesBasic(AuthorDependencies):
    def __init__(self, key: Key, pool: LedgerPool):
        self.key = key
        self.pool = pool

    async def get_key(self, did: str) -> Key:
        return self.key

    async def get_pool(self, namespace: str) -> LedgerPool:
        return self.pool


class IndyRegistry(BaseAnonCredsResolver, BaseAnonCredsRegistrar):
    """DIDIndyRegistry."""

    def __init__(self, client: IndyDriverClient, pool: LedgerPool, taa: Optional[TaaAcceptance] = None):
        """Initialize an instance.

        Args:
            None

        """
        self._supported_identifiers_regex = re.compile(r"^did:indy(:[0-9a-zA-Z]+)+:.+$")
        self.client = client
        self.pool = pool
        self.taa = taa

    @property
    def supported_identifiers_regex(self) -> Pattern:
        """Supported Identifiers regex."""
        return self._supported_identifiers_regex

    async def setup(self, context: InjectionContext) -> None:
        """Setup."""
        LOGGER.info("Successfully registered DIDIndyRegistry")

    async def get_schema(self, profile: Profile, schema_id: str) -> GetSchemaResult:
        """Get a schema from the registry."""
        LOGGER.info("ANONCREDS: get_schema %s", schema_id)
        
        async with Ledger(self.pool) as ledger:
            try:
                schema_deref = await ledger.get_schema(schema_id)
            except LedgerTransactionError as error:
                LOGGER.exception("Failed to retrieve schema")
                raise IndyRegistryError(f"Cannot retrieve schema: {error}") from error

        schema = schema_deref.contentStream
        return GetSchemaResult(
            schema=AnonCredsSchema(
                issuer_id=schema_id.split(":")[0],
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
        LOGGER.info("ANONCREDS: register_schema %s - %s", schema.issuer_id, schema.name)

        LOGGER.warning("Current DID: %s", schema.issuer_id)
        async with profile.session() as session:
            wallet = session.inject(BaseWallet)
            if schema.issuer_id:
                public_did = await wallet.get_local_did(schema.issuer_id)
            else:
                public_did = await wallet.get_public_did()

            if not public_did:
                raise IndyRegistryError("No nym provided and public DID not set")
            # did = f"did:indy:{self.NAMESPACE}:{public_did.did}"

            # # Exists?
            # try:
            #     previous = await wallet.get_local_did(did)
            #     return previous
            # except WalletNotFoundError:
            #     pass
        # Export the actual Askar Key object from the wallet using the verkey
        # key = await wallet.get_signing_key(public_did.verkey)
        # Convert the verkey string to an Askar Key object
        key = Key.from_secret_bytes(public_did.key_type._type, b58_to_bytes(public_did.verkey))
        author = Author(self.client, AuthorDependenciesBasic(key, self.pool))
        # result = await author.create_nym(NAMESPACE, verkey=public_did.verkey, taa=self.taa)
        LOGGER.info("Creating NYM with verkey: %s", public_did.verkey)
        LOGGER.info("Using Nym: %s", schema.issuer_id)

        nym_response = await author.client.create_nym(
            NAMESPACE,
            verkey=public_did.verkey,
            nym=schema.issuer_id[len(NAMESPACE)+10:],
            taa=self.taa
        )

        schema_response = await author.register_schema(schema.to_native(), self.taa)

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
                        issuer_id=schema_response.schema_id.split(":")[0],
                    )),
            ),
            registration_metadata=schema_response.registration_metadata.model_dump(),
            schema_metadata=schema_response.schema_metadata.model_dump(),
        )

    async def get_credential_definition(
        self, profile: Profile, credential_definition_id: str
    ) -> GetCredDefResult:
        """Get a credential definition from the registry."""
        LOGGER.info("ANONCREDS: get_credential_definition %s", credential_definition_id)
        async with Ledger(self.pool) as ledger:
            try:
                cred_def_deref = await ledger.get_cred_def(credential_definition_id)
            except LedgerTransactionError as error:
                LOGGER.exception("Failed to retrieve credential definition")
                raise IndyRegistryError(f"Cannot retrieve credential definition: {error}") from error

        return GetCredDefResult(
            credential_definition_id=credential_definition_id,
            credential_definition=CredDef(
                issuer_id="", # TODO
                schema_id="", # TODO
                type=cred_def_deref.contentMetadata.nodeResponse.result.signature_type,
                tag=cred_def_deref.contentMetadata.nodeResponse.result.tag,
                value=CredDefValue(
                    primary=CredDefValuePrimary.deserialize(cred_def_deref.contentStream.primary),
                    revocation=None, # TODO
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
        LOGGER.info(
            "ANONCREDS: register_credential_definition %s",
            credential_definition,
        )
        LOGGER.warning("Current DID: %s", credential_definition.issuer_id)

        async with profile.session() as session:
            wallet = session.inject(BaseWallet)
            if credential_definition.issuer_id:
                public_did = await wallet.get_local_did(credential_definition.issuer_id)
            else:
                public_did = await wallet.get_public_did()

            if not public_did:
                raise IndyRegistryError("No nym provided and public DID not set")

        # Convert the verkey string to an Askar Key object
        key = Key.from_secret_bytes(public_did.key_type._type, b58_to_bytes(public_did.verkey))
        author = Author(self.client, AuthorDependenciesBasic(key, self.pool))
        
        LOGGER.info("Creating NYM with verkey: %s", public_did.verkey)
        LOGGER.info("Using Nym: %s", credential_definition.issuer_id)

        nym_response = await author.client.create_nym(
            NAMESPACE,
            verkey=public_did.verkey,
            nym=credential_definition.issuer_id[len(NAMESPACE)+10:],
            taa=self.taa,
        )

        cred_def_response = await author.register_cred_def(credential_definition.to_native(), self.taa)

        return CredDefResult(
            job_id=uuid4().hex,
            credential_definition_state=CredDefState(
                state=CredDefState.STATE_FINISHED,
                credential_definition_id=cred_def_response.indy_cred_def_id,
                credential_definition=credential_definition,
            ),
            registration_metadata=cred_def_response.registration_metadata.model_dump(),
            credential_definition_metadata=cred_def_response.cred_def_metadata.model_dump(),
        )

    async def get_revocation_registry_definition(
        self, profile: Profile, revocation_registry_id: str
    ) -> GetRevRegDefResult:
        """Get a revocation registry definition from the registry."""
        LOGGER.info(
            "ANONCREDS: get_revocation_registry_definition %s", revocation_registry_id
        )
        raise NotImplementedError()

    async def register_revocation_registry_definition(
        self,
        profile: Profile,
        revocation_registry_definition: RevRegDef,
        options: Optional[dict] = None,
    ) -> RevRegDefResult:
        """Register a revocation registry definition on the registry."""
        LOGGER.info(
            "ANONCREDS: register_revocation_registry_definition %s",
            revocation_registry_definition,
        )
        LOGGER.warning("Current DID: %s", revocation_registry_definition.issuer_id)

        async with profile.session() as session:
            wallet = session.inject(BaseWallet)
            if revocation_registry_definition.issuer_id:
                public_did = await wallet.get_local_did(revocation_registry_definition.issuer_id)
            else:
                public_did = await wallet.get_public_did()

            if not public_did:
                raise IndyRegistryError("No nym provided and public DID not set")

        # Convert the verkey string to an Askar Key object
        key = Key.from_secret_bytes(public_did.key_type._type, b58_to_bytes(public_did.verkey))
        author = Author(self.client, AuthorDependenciesBasic(key, self.pool))
        
        LOGGER.info("Creating NYM with verkey: %s", public_did.verkey)
        LOGGER.info("Using Nym: %s", revocation_registry_definition.issuer_id)

        nym_response = await author.client.create_nym(
            NAMESPACE,
            verkey=public_did.verkey,
            nym=revocation_registry_definition.issuer_id[len(NAMESPACE)+10:],
            taa=self.taa,
        )

        rev_reg_response = await author.register_rev_reg_def(revocation_registry_definition.to_native(), self.taa)

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
        LOGGER.info(
            "ANONCREDS: register_revocation_list %s", rev_reg_def
        )
        LOGGER.warning("Current DID: %s", rev_reg_def.issuer_id)

        async with profile.session() as session:
            wallet = session.inject(BaseWallet)
            if rev_reg_def.issuer_id:
                public_did = await wallet.get_local_did(rev_reg_def.issuer_id)
            else:
                public_did = await wallet.get_public_did()

            if not public_did:
                raise IndyRegistryError("No nym provided and public DID not set")

        # Convert the verkey string to an Askar Key object
        key = Key.from_secret_bytes(public_did.key_type._type, b58_to_bytes(public_did.verkey))
        author = Author(self.client, AuthorDependenciesBasic(key, self.pool))
        
        LOGGER.info("Creating NYM with verkey: %s", public_did.verkey)
        LOGGER.info("Using Nym: %s", rev_reg_def.issuer_id)

        nym_response = await author.client.create_nym(
            NAMESPACE,
            verkey=public_did.verkey,
            nym=rev_reg_def.issuer_id[len(NAMESPACE)+10:],
            taa=self.taa,
        )

        rev_status_list_response = await author.register_rev_status_list(rev_list.to_native(), self.taa)

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
        LOGGER.info(
            "ANONCREDS: update_revocation_list %s", rev_reg_def
        )
        LOGGER.warning("Current DID: %s", rev_reg_def.issuer_id)

        async with profile.session() as session:
            wallet = session.inject(BaseWallet)
            if rev_reg_def.issuer_id:
                public_did = await wallet.get_local_did(rev_reg_def.issuer_id)
            else:
                public_did = await wallet.get_public_did()

            if not public_did:
                raise IndyRegistryError("No nym provided and public DID not set")

        # Convert the verkey string to an Askar Key object
        key = Key.from_secret_bytes(public_did.key_type._type, b58_to_bytes(public_did.verkey))
        author = Author(self.client, AuthorDependenciesBasic(key, self.pool))
        
        LOGGER.info("Creating NYM with verkey: %s", public_did.verkey)
        LOGGER.info("Using Nym: %s", rev_reg_def.issuer_id)

        nym_response = await author.client.create_nym(
            NAMESPACE,
            verkey=public_did.verkey,
            nym=rev_reg_def.issuer_id[len(NAMESPACE)+10:],
            taa=self.taa,
        )

        rev_status_list_response = await author.update_rev_status_list(
            prev_list=prev_list.to_native(),
            curr_list=curr_list.to_native(),
            revoked=list(revoked),
            taa=self.taa,
        )

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
        LOGGER.info("ANONCREDS: get_schema_info_by_id %s", schema_id)
        return await super().get_schema_info_by_id(profile, schema_id)
