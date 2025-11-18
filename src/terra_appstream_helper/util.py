# Helper module for AppStream XML manipulation

import os
import xml.etree.ElementTree as ET
from typing import Optional


def get_icon_from_type(component_type: str) -> Optional[ET.Element]:
    
    icon_type_map = {
        "runtime": "application-x-executable",
        "console-application": "terminal",
        "addon": "package",
        "icon-theme": "preferences-desktop-theme",
        "codec": "multimedia-codec",
        "driver": "computer",
        "repository": "folder",
    }

    if component_type in icon_type_map:
        icon_elem = ET.Element("icon")
        icon_elem.set("type", "stock")
        icon_elem.text = icon_type_map[component_type]
        return icon_elem
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
    else:
        name_elem = ET.SubElement(template_element, "name")
        name_elem.text = pkgname
        
    icon_elem = get_icon_from_type(component_type if component_type else "console-application")
    if icon_elem is not None:
        template_element.append(icon_elem)

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
        
        if url.endswith(".git") or "github.com" in url or "gitlab.com" in url:
            vcs_elem = ET.SubElement(template_element, "url")
            vcs_elem.set("type", "vcs-browser")
            vcs_elem.text = url
            

    if summary:
        summary_elem = ET.SubElement(template_element, "summary")
        summary_elem.text = summary

    if description:
        # <p>description</p>
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
