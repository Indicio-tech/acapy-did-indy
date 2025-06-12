"""Demo DID Web Issuance."""

import asyncio
import json
from os import getenv

from acapy_controller import Controller
from acapy_controller.logging import logging_to_stdout, section
from acapy_controller.protocols import indy_anoncred_onboard, didexchange, indy_anoncred_credential_artifacts, indy_issue_credential_v2

AGENT = getenv("AGENT", "http://localhost:3001")
HOLDER = getenv("HOLDER", "http://localhost:3003")


async def main():
    async with Controller(AGENT) as controller, Controller(HOLDER) as holder:
        did = await indy_anoncred_onboard(controller)
        print(f"Did: {did}")
        did_indy_result = await controller.post(
            "/did/indy/from-nym",
            json={
                "ldp_vc": True,
                "didcomm": True,
                "nym": did.did,
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
            holder_cred_ex, _ = await indy_issue_credential_v2(
                controller,
                holder,
                agent_conn.connection_id,
                holder_conn.connection_id,
                cred_def.credential_definition_id,
                {"firstname": "Holder", "lastname": "test"}
            )
            print(json.dumps(holder_cred_ex.serialize(), indent=2))

if __name__ == "__main__":
    asyncio.run(main())
