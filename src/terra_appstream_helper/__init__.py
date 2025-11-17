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
from subprocess import CompletedProcess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

from .xmlutil import merge_xml

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


def scan_installed_files(buildroot: str, xml_root: Optional[ET.Element] = None) -> None:
    """Scan the buildroot for installed files and append relevant AppStream metadata."""
    if xml_root is None:
        raise ValueError("xml_root must be provided to scan_installed_files.")

    rpm_version = os.getenv("RPM_PACKAGE_VERSION", "unknown")

    release_elem = xml_root.find(
        "./releases/release[@version='{0}']".format(rpm_version)
    )
    if release_elem is None:
        release_elem = ET.Element("release")
        release_elem.set("version", rpm_version)
        append_element(xml_root, "releases", release_elem)

    for dirpath, _, filenames in os.walk(buildroot):
        for filename in filenames:
            path = os.path.join(dirpath, filename)
            print(f"Found installed file: {path}")
            if filename.endswith(".so") or ".so." in filename:
                append_provides_element(xml_root, "library", filename)
            elif os.access(path, os.X_OK):
                append_provides_element(xml_root, "binary", filename)
            elif "usr/share/applications" in path and filename.endswith(".desktop"):
                launchable_elem = ET.Element("launchable")
                launchable_elem.set("type", "desktop-id")
                launchable_elem.text = filename
                append_element(xml_root, "provides", launchable_elem)
            elif "usr/lib/systemd/system" in path and filename.endswith(".service"):
                service_elem = ET.Element("launchable")
                service_elem.set("type", "service")
                service_elem.text = filename
                append_element(xml_root, "provides", service_elem)


def load_xml_document(path: Path) -> ET.Element:
    """Load an XML document from disk and return the root element."""
    tree = ET.parse(path)
    return tree.getroot()


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

def stage2_metainfo() -> ET.Element:
    template_element = ET.Element("component")
    
    # Read environment variables
    app_id = os.getenv("APPSTREAM_APPID")
    license = os.getenv("APPSTREAM_LICENSE")
    summary = os.getenv("APPSTREAM_SUMMARY")
    description = os.getenv("APPSTREAM_DESCRIPTION")
    url = os.getenv("APPSTREAM_URL")
    developer_name = os.getenv("APPSTREAM_DEVELOPER_NAME")
    developer_org_name = os.getenv("APPSTREAM_DEVELOPER_ORG_NAME")
    component_type = os.getenv("APPSTREAM_COMPONENT_TYPE")
    pkgname = os.getenv("RPM_PACKAGE_NAME")
    name_pretty = os.getenv("APPSTREAM_NAME_PRETTY")
    # pkgversion = os.getenv("RPM_PACKAGE_VERSION")
    
    # template components
    
    # Implicitly set metadata license to CC0-1.0
    metadata_license_elem = ET.SubElement(template_element, "metadata_license")
    metadata_license_elem.text = "CC0-1.0"
        
    if component_type:
        template_element.set("type", component_type)
        
    if name_pretty:
        name_elem = ET.SubElement(template_element, "name")
        name_elem.text = name_pretty

    if app_id:
        id_elem = ET.SubElement(template_element, "id")
        if pkgname and pkgname.endswith("-nightly"):
            id_elem.text = f"{app_id}-nightly"
        elif pkgname and pkgname.endswith("-git"):
            id_elem.text = f"{app_id}-git"
        else:
            id_elem.text = app_id
    else:
        # error out since we do need an app id
        raise EnvironmentError("APPSTREAM_APPID environment variable is not set.")
    
    if license:
        license_elem = ET.SubElement(template_element, "project_license")
        license_elem.text = license
    
    if url:
        url_elem = ET.SubElement(template_element, "url")
        # type="homepage"
        url_elem.set("type", "homepage")
        url_elem.text = url
    
    if summary:
        summary_elem = ET.SubElement(template_element, "summary")
        summary_elem.text = summary
        

    if description:
        #<p>description</p>
        description_elem = ET.SubElement(template_element, "description")
        p_elem = ET.SubElement(description_elem, "p")
        p_elem.text = description
    elif summary:
        # Fallback: use summary as description
        description_elem = ET.SubElement(template_element, "description")
        p_elem = ET.SubElement(description_elem, "p")
        p_elem.text = summary
        
    if developer_name:
        developer_elem = ET.SubElement(template_element, "developer")
        if developer_org_name:
            developer_elem.set("id", developer_org_name)
        else:
            developer_elem.set("id", app_id if app_id else "com.example")

    
    return template_element

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

    existing_path = find_existing_metainfo(buildroot)  # pyright: ignore[reportArgumentType]
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

    scan_installed_files(buildroot, base_root)  # pyright: ignore[reportArgumentType]

    tree = ET.ElementTree(base_root)
    ET.indent(tree, space="  ", level=0)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tree.write(output_path, encoding="utf-8", xml_declaration=True)
    else:
        ET.dump(base_root)
