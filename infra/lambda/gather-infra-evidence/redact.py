"""Point 4: redact secrets before any log text reaches an LLM or a Knowledge Base.

Copy this file into BOTH Lambda zips. Order of patterns matters: specific
formats (AWS keys, JWTs, presigned URL params) run before the generic
key=value catch-all.
"""
import re

REDACTIONS = [
    # AWS access key IDs
    (re.compile(r"(A3T[A-Z0-9]|AKIA|ASIA|ABIA|ACCA)[0-9A-Z]{16}"),
     "[REDACTED_AWS_KEY_ID]"),
    # AWS secret access keys assigned in env dumps (40-char base64-ish)
    (re.compile(r"(?i)(aws_secret_access_key|secret_access_key)\s*[=:]\s*\S+"),
     r"\1=[REDACTED]"),
    # Presigned URL / SigV4 query params
    (re.compile(r"(?i)(x-amz-(?:signature|credential|security-token))=[^&\s\"']+"),
     r"\1=[REDACTED]"),
    # JWTs (three base64url segments)
    (re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}"),
     "[REDACTED_JWT]"),
    # Bearer tokens
    (re.compile(r"(?i)bearer\s+[a-z0-9._~+/=-]{8,}"),
     "Bearer [REDACTED]"),
    # Connection strings: postgres://user:pass@host/db etc.
    (re.compile(r"(?i)\b(postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqps?)://[^\s\"']+"),
     r"\1://[REDACTED_CONNECTION_STRING]"),
    # Generic KEY=value / KEY: value for sensitive-looking names
    (re.compile(
        r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|"
        r"private[_-]?key|auth(?:orization)?|database_url|db_pass\w*)\b"
        r"\s*[=:]\s*[^\s\"']+"),
     r"\1=[REDACTED]"),
    # PEM blocks
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
     "[REDACTED_PRIVATE_KEY]"),
]


def redact(text: str) -> str:
    if not text:
        return text
    for pattern, replacement in REDACTIONS:
        text = pattern.sub(replacement, text)
    return text