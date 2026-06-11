"""Concrete filesystem-formatting safety policy."""

FORMAT_FILESYSTEM_PATTERNS: tuple[tuple[str, ...], ...] = (
    ("mkfs",),
    ("mkfs.",),
    ("newfs",),
    ("format",),
    ("diskutil", "eraseDisk"),
    ("diskpart",),
)
