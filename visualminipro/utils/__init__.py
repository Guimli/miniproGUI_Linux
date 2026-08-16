"""Support utilities: paths, settings, algorithm/firmware handling."""

from .algorithm_xml import (
    algorithm_xml_path_if_needed,
    needs_algorithm_installation,
    resolve_algorithm_xml_path,
    resolve_algorithm_xml_path_for,
)
from .infoic import legacy_infoic_available, resolve_infoic_path
from .mamedb import (
    MameDatabaseError,
    MameMatch,
    compute_sha1,
    database_summary,
    find_by_sha1,
    find_database,
)
from .paths import config_dir, data_dir, logicic_path
from .settings import apply_libusb_debug_logging, settings
from .xgpro_extractor import XgproSoftwareExtractor, XgproSoftwareExtractorError
from .xgpro_firmware import (
    FirmwareInfo,
    SoftwareBundleVerificationStatus,
    XgproFirmwareUtils,
    XgproFirmwareUtilsError,
)

__all__ = [
    "FirmwareInfo",
    "MameDatabaseError",
    "MameMatch",
    "SoftwareBundleVerificationStatus",
    "XgproFirmwareUtils",
    "XgproFirmwareUtilsError",
    "XgproSoftwareExtractor",
    "XgproSoftwareExtractorError",
    "algorithm_xml_path_if_needed",
    "apply_libusb_debug_logging",
    "compute_sha1",
    "config_dir",
    "data_dir",
    "database_summary",
    "find_by_sha1",
    "find_database",
    "legacy_infoic_available",
    "logicic_path",
    "needs_algorithm_installation",
    "resolve_algorithm_xml_path",
    "resolve_algorithm_xml_path_for",
    "resolve_infoic_path",
    "settings",
]
