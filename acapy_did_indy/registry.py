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
)
from acapy_agent.anoncreds.models.revocation import (
    GetRevListResult,
    GetRevRegDefResult,
    RevList,
    RevListResult,
    RevRegDef,
    RevRegDefResult,
)
from acapy_agent.anoncreds.models.schema import (
    AnonCredsSchema,
    GetSchemaResult,
    SchemaResult,
)
from acapy_agent.anoncreds.models.schema_info import AnonCredsSchemaInfo
from did_indy.client.client import IndyDriverAdminClient, IndyDriverClient
from did_indy.ledger import LedgerPool, fetch_genesis_transactions

LOGGER = logging.getLogger(__name__)


class IndyRegistry(BaseAnonCredsResolver, BaseAnonCredsRegistrar):
    """DIDIndyRegistry."""

    def __init__(self, client: IndyDriverClient, pool: LedgerPool):
        """Initialize an instance.

        Args:
            None

        """
        self._supported_identifiers_regex = re.compile(r"^did:indy:.*$")

    @property
    def supported_identifiers_regex(self) -> Pattern:
        """Supported Identifiers regex."""
        return self._supported_identifiers_regex
        # TODO: fix regex (too general)

    async def setup(self, context: InjectionContext) -> None:
        """Setup."""
        LOGGER.info("Successfully registered DIDIndyRegistry")

    async def get_schema(self, profile: Profile, schema_id: str) -> GetSchemaResult:
        """Get a schema from the registry."""
        LOGGER.info("ANONCREDS: get_schema %s", schema_id)
        raise NotImplementedError()

    async def register_schema(
        self,
        profile: Profile,
        schema: AnonCredsSchema,
        options: Optional[dict] = None,
    ) -> SchemaResult:
        """Register a schema on the registry."""
        LOGGER.info("ANONCREDS: register_schema %s - %s", schema.issuer_id, schema.name)

        LOGGER.warning("Current DID: %s", schema.issuer_id)
        raise NotImplementedError()

    async def get_credential_definition(
        self, profile: Profile, credential_definition_id: str
    ) -> GetCredDefResult:
        """Get a credential definition from the registry."""
        LOGGER.info("ANONCREDS: get_credential_definition %s", credential_definition_id)
        raise NotImplementedError()

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
            credential_definition.credential_definition_id,
        )
        raise NotImplementedError()

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
            revocation_registry_definition.revocation_registry_id,
        )
        raise NotImplementedError()

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
            "ANONCREDS: register_revocation_list %s", rev_reg_def.revocation_registry_id
        )
        raise NotImplementedError()

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
            "ANONCREDS: update_revocation_list %s", rev_reg_def.revocation_registry_id
        )
        raise NotImplementedError()

    async def get_schema_info_by_id(
        self, profile: Profile, schema_id: str
    ) -> AnonCredsSchemaInfo:
        """Get a schema info from the registry."""
        LOGGER.info("ANONCREDS: get_schema_info_by_id %s", schema_id)
        return await super().get_schema_info_by_id(schema_id)
