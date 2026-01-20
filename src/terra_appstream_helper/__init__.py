# terra-appstream-helper - a helper to generate AppStream metadata for Terra packages
# # How it works
# this helper will scan the RPM_BUILD_ROOT directory for installed files, and help generate AppStream metadata,
# generate AppStream metainfo XML files, and does a three way merge between:
# - the base human-written metainfo file (if any)
# - The generated build-time metainfo file from scanning installed files
# - the existing package-installed metainfo file (if any)
# to produce a final, semantic merge of the three sources of data.
#
# It is intended to be used as part of the Terra packaging build process, to help package maintainers
# generate accurate and complete AppStream metadata for their packages with minimal effort.
#
# This file is licensed under the GNU General Public License v3.0 or later.
# See the LICENSE file in the root of the repository for more details.
import argparse
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

from .logging import get_logger
from .util import get_icon_from_type, stage2_metainfo
from .xmlutil import load_xml_document, merge_xml

parser = argparse.ArgumentParser(
    description="Generate merged AppStream metadata from optional overrides and buildroot data.",
)
parser.add_argument(
    "--override",
    type=Path,
    help="Path to a human-provided metainfo XML override.",
)
parser.add_argument(
    "--output",
    "-o",
    type=Path,
    help="Path to write the final merged metainfo XML. If not provided, output to stdout.",
)
args = parser.parse_args()

# envars that RPM exposes:
# - RPM_PACKAGE_NAME
# - RPM_PACKAGE_VERSION
# - RPM_PACKAGE_RELEASE
# - RPM_BUILD_ROOT
# - RPM_SPECPARTS_DIR

# envars that we set using our custom macros (may not be present):
# - APPSTREAM_APPID - the AppStream application ID for the package
# - APPSTREAM_LICENSE - the SPDX license identifier for the package
# - APPSTREAM_SUMMARY - a short summary of the package
# - APPSTREAM_DESCRIPTION - a longer description of the package
# - APPSTREAM_URL - the project URL for the package
# - APPSTREAM_COMPONENT_TYPE - the AppStream component type (e.g., "desktop-application", "library", etc.)
# - APPSTREAM_DEVELOPER_NAME - the name of the developer or maintainer
# - APPSTREAM_DEVELOPER_ORG_NAME - the name of the developer organization
# - APPSTREAM_NAME_PRETTY - a human-friendly name for the application

buildroot = os.getenv("RPM_BUILD_ROOT")
if buildroot is None:
    raise EnvironmentError("RPM_BUILD_ROOT environment variable is not set.")

logger = get_logger()


def append_element(
    xml_root: ET.Element, element_name: str, subelement: ET.Element
) -> None:
    """Append a subelement to a parent element in the XML tree. Create the parent if it doesn't exist."""
    parent_elem = xml_root.find(element_name)
    if parent_elem is None:
        parent_elem = ET.SubElement(xml_root, element_name)
    parent_elem.append(subelement)


def append_provides_element(
    xml_root: ET.Element, element_type: str, element_value: str
) -> None:
    """Append a new element under <provides> in the XML tree. Create <provides> if it doesn't exist."""
    new_elem = ET.Element(element_type)
    new_elem.text = element_value
    append_element(xml_root, "provides", new_elem)


def prep_component(buildroot: str, xml_root: Optional[ET.Element] = None) -> None:
    """Scan the buildroot for installed files and append relevant AppStream metadata."""
    if xml_root is None:
        raise ValueError("xml_root must be provided to scan_installed_files.")

    # Only apply default icon when no icon is defined in the merged XML.
    if xml_root.find("icon") is None:
        component_type = xml_root.get("type") or os.getenv("APPSTREAM_COMPONENT_TYPE")
        icon_elem = get_icon_from_type(component_type)
        if icon_elem is not None:
            xml_root.append(icon_elem)

    pkgname = os.getenv("RPM_PACKAGE_NAME", "")
    rpm_version = os.getenv("RPM_PACKAGE_VERSION", "unknown")

    release_elem = xml_root.find(
        "./releases/release[@version='{0}']".format(rpm_version)
    )
    if release_elem is None:
        release_elem = ET.Element("release")
        release_elem.set("version", rpm_version)
        append_element(xml_root, "releases", release_elem)

    # if package is nightly or git, always edit or append -git or -nightly release
    release_suffixes = {
        "-nightly": ("-nightly", " (Nightly)"),
        "-git": ("-git", " (Git Development Build)"),
    }

    for suffix, release_suffix in release_suffixes.items():
        if pkgname.endswith(suffix):
            adjusted = False
            pkgid_elem = xml_root.find("./id")
            if pkgid_elem is not None and pkgid_elem.text is not None:
                base_app_id = pkgid_elem.text
                if not base_app_id.lower().endswith(release_suffix[0].lower()):
                    pkgid_elem.text = f"{base_app_id}{release_suffix[0]}"
                    adjusted = True
            name_elem = xml_root.find("./name")
            if name_elem is not None and name_elem.text is not None:
                base_name = name_elem.text
                normalized_base = base_name.lower()
                raw_suffix = release_suffix[1]
                stripped_suffix = raw_suffix.strip().lower()
                suffix_variants = {raw_suffix.lower()}
                if stripped_suffix:
                    suffix_variants.add(stripped_suffix)
                    if stripped_suffix.startswith("(") and stripped_suffix.endswith(
                        ")"
                    ):
                        inner_suffix = stripped_suffix[1:-1].strip()
                        if inner_suffix:
                            suffix_variants.add(inner_suffix)
                            suffix_variants.add(f" {inner_suffix}")
                if not any(
                    normalized_base.endswith(variant) for variant in suffix_variants
                ):
                    name_elem.text = f"{base_name}{release_suffix[1]}"
                    adjusted = True
            if adjusted:
                logger.info(
                    "Detected package name '%s' ends with '%s'; adjusted AppStream IDs accordingly.",
                    pkgname,
                    suffix,
                )
            else:
                logger.debug(
                    "Package name '%s' ends with '%s'; AppStream IDs already contain suffix, no changes made.",
                    pkgname,
                    suffix,
                )
            # adjust release version

    for dirpath, _, filenames in os.walk(buildroot):
        for filename in filenames:
            path = os.path.join(dirpath, filename)
            logger.debug("Found installed file: %s", path)
            if (filename.endswith(".so") or ".so." in filename) and (
                "usr/lib" in path or "usr/lib64" in path
            ):
                append_provides_element(xml_root, "library", filename)
            if (filename.endswith(".dll") or filename.endswith(".lib")) and (
                "usr/lib" in path or "usr/lib64" in path
            ):
                append_provides_element(xml_root, "library", filename)
            elif os.access(path, os.X_OK) and "usr/bin" in path:
                append_provides_element(xml_root, "binary", filename)
            elif "usr/share/applications" in path and filename.endswith(".desktop"):
                existing_launchable = next(
                    (
                        launchable
                        for launchable in xml_root.findall(
                            "./launchable[@type='desktop-id']"
                        )
                        if launchable.text == filename
                    ),
                    None,
                )
                if existing_launchable is None:
                    launchable_elem = ET.Element("launchable")
                    launchable_elem.set("type", "desktop-id")
                    launchable_elem.text = filename
                    xml_root.append(launchable_elem)
            elif "usr/lib/systemd/system" in path and filename.endswith(".service"):
                existing_service = next(
                    (
                        launchable
                        for launchable in xml_root.findall(
                            "./launchable[@type='service']"
                        )
                        if launchable.text == filename
                    ),
                    None,
                )
                if existing_service is None:
                    service_elem = ET.Element("launchable")
                    service_elem.set("type", "service")
                    service_elem.text = filename
                    xml_root.append(service_elem)


def find_existing_metainfo(buildroot: str) -> Optional[Path]:
    """Return the first metainfo XML file discovered within the buildroot, if any."""
    root_path = Path(buildroot)

    direct_candidate = root_path / "metainfo.xml"
    if direct_candidate.is_file():
        return direct_candidate

    known_dirs = [
        root_path / "usr" / "share" / "metainfo",
        root_path / "usr" / "share" / "appdata",
    ]
    patterns = ("*.metainfo.xml", "*.appdata.xml", "metainfo.xml")

    for directory in known_dirs:
        if not directory.is_dir():
            continue
        for pattern in patterns:
            matches = sorted(directory.glob(pattern))
            if matches:
                return matches[0]

    for pattern in patterns:
        for match in root_path.rglob(pattern):
            return match

    return None


def main(argv: Optional[list[str]] = None) -> None:
    override_path: Optional[Path] = (
        args.override.expanduser() if args.override else None
    )
    output_path: Optional[Path] = args.output.expanduser() if args.output else None
    override_root: Optional[ET.Element] = None
    if override_path is not None:
        if not override_path.is_file():
            raise FileNotFoundError(
                f"The override file {override_path} does not exist."
            )
        override_root = load_xml_document(override_path)

    existing_path = find_existing_metainfo(
        buildroot
    )  # pyright: ignore[reportArgumentType]
    existing_root: Optional[ET.Element] = (
        load_xml_document(existing_path) if existing_path is not None else None
    )

    if override_root is not None:
        base_root = override_root
    elif existing_root is not None:
        base_root = existing_root
    else:
        base_root = ET.Element("component")

    if override_root is not None and existing_root is not None:
        merge_xml(base_root, existing_root)

    stage2_root = stage2_metainfo()
    merge_xml(base_root, stage2_root)

    prep_component(buildroot, base_root)  # pyright: ignore[reportArgumentType]

    tree = ET.ElementTree(base_root)
    ET.indent(tree, space="  ", level=0)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tree.write(output_path, encoding="utf-8", xml_declaration=True)
    else:
        ET.dump(base_root)
