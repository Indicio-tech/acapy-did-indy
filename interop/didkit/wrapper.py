"""DIDKit wrapper."""

from ctypes import CDLL, CFUNCTYPE, addressof, c_char_p, c_int32, c_void_p, cast, create_string_buffer, string_at
import json
import os.path
from sys import platform
from typing import Any, Callable

from .contexts import CONTEXTS

didpath = os.path.dirname(os.path.abspath(__file__))

if platform == "linux" or platform == "linux2":
    didpath = os.path.join(didpath, "libdidkit.so")
    didkit = libc = CDLL(didpath)
elif platform == "darwin":
    didpath = os.path.join(didpath, "libdidkit.dylib")
    didkit = libc = CDLL(didpath)
else:
    didpath = os.path.join(didpath, "didkit.dll")
    didkit = libc = CDLL(didpath, winmode=1)

# String getVersion()
didkit.didkit_get_version.restype = c_char_p
didkit.didkit_get_version.argtypes = ()

# String didkit_error_message()
didkit.didkit_error_message.restype = c_char_p
didkit.didkit_error_message.argtypes = ()

# int didkit_error_code()
didkit.didkit_error_code.restype = c_int32
didkit.didkit_error_code.argtypes = ()

ResolveDidCallback = CFUNCTYPE(c_char_p, c_char_p, c_void_p)

# String verifyCredential(String credential, String options)
didkit.didkit_vc_verify_credential.restype = c_void_p
didkit.didkit_vc_verify_credential.argtypes = (
    c_char_p,  # credential
    c_char_p,  # proof options
    ResolveDidCallback,  # resolver callback
    c_void_p,  # callback ptr
    c_char_p,  # context map
)

# void didkit_free_string(String str)
didkit.didkit_free_string.restype = None
didkit.didkit_free_string.argtypes = (c_void_p,)


class DIDKitException(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message

    @staticmethod
    def lastError():
        code = didkit.didkit_error_code()
        message = didkit.didkit_error_message()
        message_str = "Unable to get error message" if not message else message.decode()
        return DIDKitException(code, message_str)


def get_version():
    return didkit.didkit_get_version().decode()

_allocated_buffers = []

def verify_credential(
    credential: dict,
    options: dict,
    resolver: Callable[[str], dict],
    contexts: dict[str, Any],
) -> dict:
    @ResolveDidCallback
    def c_resolve_did(did: c_char_p, ptr: c_void_p) -> int:
        did_str = string_at(did).decode()
        result = resolver(did_str)
        encoded = json.dumps(result).encode()
        buf = create_string_buffer(encoded)
        _allocated_buffers.append(buf)
        return addressof(buf)

    contexts = {context: json.dumps(value) for context, value in contexts.items()}
    contexts_str = json.dumps(contexts)
    result = didkit.didkit_vc_verify_credential(
        json.dumps(credential).encode(),
        json.dumps(options).encode(),
        c_resolve_did,
        None,
        contexts_str.encode(),
    )
    if not result:
        raise DIDKitException.lastError()
    result_ptr = cast(result, c_char_p)
    assert result_ptr.value
    result_str = result_ptr.value.decode()
    didkit.didkit_free_string(cast(result, c_void_p))
    return json.loads(result_str)


if __name__ == "__main__":
    print(get_version())

    credential = {
        "@context": [
            "https://www.w3.org/2018/credentials/v1",
            "https://purl.imsglobal.org/spec/ob/v3p0/context-3.0.3.json",
            "https://www.w3.org/ns/credentials/status/v1",
            "https://w3id.org/security/suites/ed25519-2020/v1",
        ],
        "id": "urn:uuid:efefd4ff-8ff3-4705-b5c4-e9e4cc068b08",
        "type": ["VerifiableCredential", "OpenBadgeCredential"],
        "issuer": {
            "type": ["Profile"],
            "id": "did:indy:indicio:test:Y4zmgeL7gnnKY5MtdhPvTz",
            "name": "My Subwallet Label",
        },
        "issuanceDate": "2025-03-25T17:27:39Z",
        "credentialSubject": {
            "id": "did:key:z6Mkppn6TSkar9uEn9AG66q8JRJLK2KuMVnu2EcMeFScBQZx",
            "type": ["AchievementSubject"],
            "achievement": {
                "name": "Cred Attempt SDK 5",
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
                "id": "urn:uuid:76f9cf2f-424c-4b76-ad00-deff7ea9af08",
            },
        },
        "credentialStatus": {
            "id": "https://mepeltierindicio.share.zrok.io/json-ld-revocation/tenants/d2045eb4-c3c2-411a-b1c1-2406d3f0cb64/w3c/status/0#114976",
            "type": "BitstringStatusListEntry",
            "statusPurpose": "revocation",
            "statusListIndex": 114976,
            "statusListCredential": "https://mepeltierindicio.share.zrok.io/json-ld-revocation/tenants/d2045eb4-c3c2-411a-b1c1-2406d3f0cb64/w3c/status/0",
        },
        "proof": {
            "type": "Ed25519Signature2020",
            "proofPurpose": "assertionMethod",
            "verificationMethod": "did:indy:indicio:test:Y4zmgeL7gnnKY5MtdhPvTz#assert",
            "created": "2025-03-25T17:27:41+00:00",
            "proofValue": "z32XbAwaBPek45BzLvVu1xhcBcubKUBUwC5pQMW1Fx3JN5MXba7qyeE4vKKeCqaVqwPJyFMBeQRvr6ydfv7chYCnN",
        },
        "name": "Cred Attempt SDK 5",
    }

    def resolver(did: str) -> dict:
        return {
            "@context": [
                "https://www.w3.org/ns/did/v1",
                "https://w3id.org/security/suites/ed25519-2018/v1",
                "https://w3id.org/security/suites/ed25519-2020/v1",
            ],
            "id": "did:indy:indicio:test:Y4zmgeL7gnnKY5MtdhPvTz",
            "verificationMethod": [
                {
                    "type": "Ed25519VerificationKey2018",
                    "id": "did:indy:indicio:test:Y4zmgeL7gnnKY5MtdhPvTz#verkey",
                    "controller": "did:indy:indicio:test:Y4zmgeL7gnnKY5MtdhPvTz",
                    "publicKeyBase58": "Hw9eYXLY9oHhQGynA7meg8fLWzuBjDtmiJh4NGAdscvd",
                },
                {
                    "controller": "did:indy:indicio:test:Y4zmgeL7gnnKY5MtdhPvTz",
                    "id": "did:indy:indicio:test:Y4zmgeL7gnnKY5MtdhPvTz#assert",
                    "publicKeyMultibase": "z6MkoFBQkXuBwcKygrCgAzsZ7Dua1UEtGuUiRazvWxd64EHK",
                    "type": "Ed25519VerificationKey2020",
                },
            ],
            "authentication": ["did:indy:indicio:test:Y4zmgeL7gnnKY5MtdhPvTz#verkey"],
            "assertionMethod": ["did:indy:indicio:test:Y4zmgeL7gnnKY5MtdhPvTz#assert"],
            "service": [
                {
                    "id": "#didcomm-0",
                    "priority": 0,
                    "recipientKeys": ["#key-0"],
                    "routingKeys": [],
                    "serviceEndpoint": "https://mepeltierindicio.share.zrok.io/agent",
                    "type": "did-communication",
                }
            ],
        }

    print(verify_credential(credential, {}, resolver, CONTEXTS))
