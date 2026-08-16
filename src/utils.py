"""Shared utility functions."""

import re


def slugify(text: str, max_len: int = 60) -> str:
    """Convert arbitrary text to a safe filesystem slug.

    Lowercases, collapses runs of non-alphanumeric characters to a single
    underscore, strips leading/trailing underscores, and truncates to *max_len*
    characters.

    Examples::

        slugify("Jennifer Aniston")            -> "jennifer_aniston"
        slugify("Arjuna fighting warriors!")   -> "arjuna_fighting_warriors"
    """
    lowered = text.lower()
    slugged = re.sub(r"[^a-z0-9]+", "_", lowered)
    slugged = slugged.strip("_")
    return slugged[:max_len]
