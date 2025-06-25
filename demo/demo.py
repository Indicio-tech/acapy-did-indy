"""Demo DID Web Issuance."""

import asyncio
import json
from os import getenv

from acapy_controller import Controller
from acapy_controller.logging import logging_to_stdout, section
from acapy_controller.protocols import indy_anoncred_onboard, didexchange, indy_anoncred_credential_artifacts, anoncreds_issue_credential_v2, DIDResult

AGENT = getenv("AGENT", "http://localhost:3001")
HOLDER = getenv("HOLDER", "http://localhost:3003")
logging_to_stdout()


async def main():
    async with Controller(AGENT) as controller, Controller(HOLDER) as holder:
        # did = await indy_anoncred_onboard(controller)
        # did = (await controller.post(
        #     "/wallet/did/create",
        #     json={"method": "sov", "options": {"key_type": "ed25519"}},
        #     response=DIDResult,
        # )).result
        # print(f"Did: {did}")
        did_indy_result = await controller.post(
            "/did/indy/new-did",
            json={
                "ldp_vc": True,
                "didcomm": True,
                # "nym": did.did,
            }
        )
        did_indy = did_indy_result["did"]
        vm = did_indy + "#assert"

        with section("Establish Connection"):
            agent_conn, holder_conn = await didexchange(controller, holder)

        with section("Register Schema"):
            print("Registering Schema and Credential Definition")
            print(f"Using DID: {did_indy}")
            print(f"Using Verifiable Method: {vm}")
            print("Did result:", json.dumps(did_indy_result, indent=2))
            schema, cred_def = await indy_anoncred_credential_artifacts(
                controller,
                ["firstname", "lastname"],
                support_revocation=False,
                issuer_id=did_indy,
            )
            print(json.dumps(schema.serialize(), indent=2))
            print(json.dumps(cred_def.serialize(), indent=2))

        with section("Issue Credential to Holder"):
            issuer_cred_ex, holder_cred_ex = await anoncreds_issue_credential_v2(
                controller,
                holder,
                agent_conn.connection_id,
                holder_conn.connection_id,
                cred_def.credential_definition_id,
                {"firstname": "Holder", "lastname": "test"}
            )
            print(json.dumps(holder_cred_ex.serialize(), indent=2))
        print("Successfully issued credential to holder!")
        print("You can now use the issued credential in the holder agent.")
        print("Holder Credential Exchange ID:", holder_cred_ex.cred_ex_record.cred_ex_id)
        print("Issuer Credential Exchange ID:", issuer_cred_ex.cred_ex_record.cred_ex_id)
        print("Credential Definition ID:", cred_def.credential_definition_id)
        print("Schema ID:", schema.schema_id)
        print("DID Indy:", did_indy)
        # print("Holder Credential Attributes:")
        # print(json.dumps(holder_cred_ex.cred_ex_record.credential_attributes, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
