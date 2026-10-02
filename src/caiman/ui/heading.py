"""Uppercase fullwidth card headings, contained in one terminal row.

Uppercase is presentation only. Unsupported or overlong identities fall back to
ordinary text in the caller, retaining their original spelling.
"""

# Printable ASCII has a fullwidth form at a fixed offset; space has its own.
FULLWIDTH_OFFSET = 0xFEE0
IDEOGRAPHIC_SPACE = '　'


def fullwidth_title(value: str, width: int) -> list[str]:
    # Reject unsupported source characters before case conversion: e.g. ß must
    # not silently become SS, and opaque identifiers keep their exact fallback.
    if not value or any(not ' ' <= c <= '~' for c in value) or len(value) * 2 > width:
        return []
    return [''.join(IDEOGRAPHIC_SPACE if c == ' ' else chr(ord(c) + FULLWIDTH_OFFSET)
                    for c in value.upper())]
