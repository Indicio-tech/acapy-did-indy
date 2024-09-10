"""Demo DID Web Issuance."""

import asyncio
import json
from os import getenv

from acapy_controller import Controller
from acapy_controller.protocols import indy_anoncred_onboard

AGENT = getenv("AGENT", "http://localhost:3001")


async def main():
    async with Controller(AGENT) as controller:
        did = await indy_anoncred_onboard(controller)
        did_indy_result = await controller.post("/did/indy/create")
        did_indy = did_indy_result["did"]
        vm = did_indy + "#assert"
        credential = {
            "credential": {
                "@context": [
                    "https://www.w3.org/2018/credentials/v1",
                    "https://purl.imsglobal.org/spec/ob/v3p0/context-3.0.3.json",
                    "https://w3id.org/security/suites/ed25519-2020/v1",
                ],
                "name": "JFF x vc-edu PlugFest 3 Interoperability",
                "id": "urn:uuid:8f0df0cc-b5ab-48fa-8bc8-1bac515008cb",
                "type": ["VerifiableCredential", "OpenBadgeCredential"],
                "issuer": {
                    "type": ["Profile"],
                    "id": did_indy,
                    "name": "JFF x vc-edu PlugFest 3 Interoperability",
                },
                "issuanceDate": "2024-08-21T18:20:23Z",
                "credentialSubject": {
                    "id": "did:key:z6MktsCtkJCST2NUZfa3SQSm4DL89YmFEdJmt37Vvkw8aH19",
                    "type": ["AchievementSubject"],
                    "achievement": {
                        "name": "JFF x vc-edu PlugFest 3 Interoperability",
                        "description": "This wallet supports the use of W3C Verifiable Credentials and has demonstrated interoperability during the presentation request workflow during JFF x VC-EDU PlugFest 3.",
                        "criteria": {
                            "type": "Criteria",
                            "narrative": "Wallet solution providers earned this badge by demonstrating interoperability during the presentation request workflow. This included successfully receiving a presentation request, allowing the holder to select at least two types of verifiable credentials to create a verifiable presentation, returning the presentation to the requester, and passing verification of the presentation and the included credentials.",
                        },
                        "image": {
                            "id": "https://w3c-ccg.github.io/vc-ed/plugfest-3-2023/images/JFF-VC-EDU-PLUGFEST3-badge-image.png",
                            "type": "Image",
                        },
                        "type": ["Achievement"],
                        "id": "urn:uuid:53b3803c-8774-4697-a614-455588181966",
                    },
                },
            },
            "options": {
                "challenge": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "created": "2021-12-31T23:59:59Z",
                "domain": "example.com",
                "proofPurpose": "assertionMethod",
                "proofType": "Ed25519Signature2020",
                "verificationMethod": vm,
            },
        }
        result = await controller.post("/vc/credentials/issue", json=credential)
        print(json.dumps(result["verifiableCredential"], indent=2))


if __name__ == "__main__":
    asyncio.run(main())
