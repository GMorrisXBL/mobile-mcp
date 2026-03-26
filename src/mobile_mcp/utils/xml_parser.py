"""XML parsing utilities for Android UI hierarchy."""

import re
import xml.etree.ElementTree as ET
from typing import Optional

from mobile_mcp.robots.base import Rect, ScreenElement


def parse_bounds(bounds_str: str) -> Optional[Rect]:
    """Parse Android bounds string like '[0,0][1080,1920]'.

    Args:
        bounds_str: Bounds string from UIAutomator.

    Returns:
        Rect object, or None if parsing fails.
    """
    # Match pattern [x1,y1][x2,y2]
    match = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds_str)
    if not match:
        return None

    x1, y1, x2, y2 = map(int, match.groups())
    return Rect(x=x1, y=y1, width=x2 - x1, height=y2 - y1)


def parse_android_ui_hierarchy(xml_content: str) -> list[ScreenElement]:
    """Parse Android UIAutomator XML dump.

    Args:
        xml_content: XML string from 'uiautomator dump'.

    Returns:
        List of ScreenElement objects.
    """
    elements: list[ScreenElement] = []

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return elements

    def process_node(node: ET.Element) -> None:
        """Recursively process XML nodes."""
        # Get bounds
        bounds_str = node.get("bounds", "")
        rect = parse_bounds(bounds_str)

        if rect and (rect.width > 0 or rect.height > 0):
            # Extract element properties
            element_class = node.get("class", "")
            element_type = element_class.split(".")[-1] if element_class else "Unknown"

            text = node.get("text") or None
            content_desc = node.get("content-desc") or None
            resource_id = node.get("resource-id") or None
            focused = node.get("focused") == "true"

            # Only include non-empty elements
            if text or content_desc or resource_id:
                elements.append(
                    ScreenElement(
                        type=element_type,
                        rect=rect,
                        text=text,
                        label=content_desc,
                        name=None,
                        value=None,
                        identifier=resource_id,
                        focused=focused,
                    )
                )

        # Process children
        for child in node:
            process_node(child)

    process_node(root)
    return elements


def clean_xml_content(xml_content: str) -> str:
    """Clean XML content by removing invalid characters.

    Args:
        xml_content: Raw XML string.

    Returns:
        Cleaned XML string.
    """
    # Remove null bytes and other control characters
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", xml_content)
    return cleaned
