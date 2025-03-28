"""Test DIDKit verification of a credential value."""

import json
from acapy_controller.controller import Controller
from acapy_controller.models import ResolutionResult
import pytest
import pytest_asyncio
from didkit import wrapper
from didkit.contexts import CONTEXTS

@pytest_asyncio.fixture
async def indy_did_doc(controller: Controller, indy_did: str):
    """Return the did doc for the indy did."""
    result = await controller.get(
        f"/resolver/resolve/{indy_did}",
        response=ResolutionResult
    )
    return result.did_document


@pytest_asyncio.fixture
async def contexts():
    """Retrieve JSON-LD Contexts."""
    return CONTEXTS

    # If we need to download any additional ones for future testing
    # contexts = (
    #     "https://www.w3.org/2018/credentials/v1",
    #     "https://purl.imsglobal.org/spec/ob/v3p0/context-3.0.3.json",
    # )
    # context_map = {}
    # async with ClientSession() as session:
    #     for context in contexts:
    #         async with session.get(context) as resp:
    #             context_map[context] = await resp.json()
    # return context_map


@pytest_asyncio.fixture
async def credential(controller: Controller, indy_did: str):
    """Produce a credential for testing."""
    vm = indy_did + "#assert"
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
                "id": indy_did,
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
    return result["verifiableCredential"]


@pytest.mark.asyncio
async def test_didkit_verify(credential: dict, indy_did_doc: dict, contexts: dict):
    """Test didkit verification of a credential."""
    def resolver(did: str) -> dict:
        return indy_did_doc

    result = wrapper.verify_credential(credential, {}, resolver, contexts)
    assert not result["warnings"]
    assert not result["errors"]
