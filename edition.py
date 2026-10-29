"""Which build this is. AgentLash.spec generates a `_edition` module per exe:
AgentLash.exe (standard, no security-awareness code at all) and AgentLash_Security.exe."""
try:
    from _edition import SECURITY_EDITION
except ImportError:
    SECURITY_EDITION = True  # running from source: everything enabled
