from enum import Enum


class Platform(str, Enum):
    """Allowed platforms for an allocation."""

    FB = "fb"
    OB = "ob"
    SNP = "snp"
    GTAG = "gtag"
