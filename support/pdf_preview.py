"""
pdf_preview.py — render PDF bytes as a sequence of st.image pages.

Uses pdf2image (poppler) so it works in every browser without relying on
browser-native PDF embedding (which is blocked by modern browsers via data URIs).
"""
import io
import streamlit as st


def show_pdf_pages(pdf_bytes: bytes, dpi: int = 150) -> None:
    """Convert PDF bytes to images and display each page with st.image."""
    try:
        from pdf2image import convert_from_bytes
    except ImportError:
        st.error("pdf2image is not installed. Run: pip install pdf2image")
        return

    try:
        pages = convert_from_bytes(pdf_bytes, dpi=dpi)
    except Exception as exc:
        st.error(f"Failed to render PDF: {exc}")
        return

    for i, page in enumerate(pages):
        buf = io.BytesIO()
        page.save(buf, format="PNG")
        st.image(buf.getvalue(), use_container_width=True,
                 caption=f"Page {i + 1} of {len(pages)}" if len(pages) > 1 else None)
