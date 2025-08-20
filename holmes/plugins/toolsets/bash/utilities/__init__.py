"""
Common CLI utilities support for the bash toolset.

This module provides safe implementations of common Unix utilities like jq, awk, sed,
cut, sort, uniq, head, tail, wc, tr, and base64 for use in troubleshooting scenarios.

All utilities are implemented with security in mind:
- Read-only operations only
- No file modification capabilities
- No command execution within utilities
- Proper input validation and size limits
- Shell injection prevention using shlex.quote
"""