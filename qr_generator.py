"""
QR Code Generator

Generates QR code images for embedding in PowerPoint presentations.
"""

import logging
from io import BytesIO
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Glove brand color for QR codes
GLOVE_QR_COLOR = "#37BEAE"
LOGO_PATH = Path(__file__).parent / "decoratives" / "glove_logo.png"


def generate_qr_code(
    url: str,
    box_size: int = 10,
    border: int = 4,
    fill_color: str = GLOVE_QR_COLOR,
    back_color: str = "white"
) -> Optional[BytesIO]:
    """Generate styled QR code image as BytesIO for embedding in PPT.

    Args:
        url: URL to encode in QR code
        box_size: Size of each box in pixels (default 10)
        border: Border size in boxes (default 4)
        fill_color: QR code color (default Glove brand color)
        back_color: Background color (default white)

    Returns:
        BytesIO buffer containing PNG image, or None if generation fails
    """
    try:
        import qrcode
        from qrcode.constants import ERROR_CORRECT_H
        from qrcode.image.styledpil import StyledPilImage
        from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
        from qrcode.image.styles.colormasks import SolidFillColorMask
        from PIL import Image

        qr = qrcode.QRCode(
            version=None,  # Auto-determine version
            error_correction=ERROR_CORRECT_H,  # 30% - needed for logo
            box_size=box_size,
            border=border,
        )
        qr.add_data(url)
        qr.make(fit=True)

        # Convert hex color to RGB tuple
        if fill_color.startswith('#'):
            fill_rgb = tuple(int(fill_color[i:i+2], 16) for i in (1, 3, 5))
        else:
            fill_rgb = (55, 190, 174)  # Fallback to Glove teal

        # Generate styled QR with rounded modules
        img = qr.make_image(
            image_factory=StyledPilImage,
            module_drawer=RoundedModuleDrawer(),
            color_mask=SolidFillColorMask(
                back_color=(255, 255, 255),
                front_color=fill_rgb
            )
        )

        # Add logo in center if available
        if LOGO_PATH.exists():
            try:
                from PIL import ImageDraw

                logo = Image.open(LOGO_PATH)

                # Calculate logo size (max 25% of QR code)
                qr_width, qr_height = img.size
                max_logo_size = int(qr_width * 0.25)

                # Resize logo maintaining aspect ratio
                logo.thumbnail((max_logo_size, max_logo_size), Image.Resampling.LANCZOS)
                logo_width, logo_height = logo.size

                # Center logo on QR code
                logo_x = (qr_width - logo_width) // 2
                logo_y = (qr_height - logo_height) // 2

                # Create rounded white background for logo (with padding)
                padding = 10
                corner_radius = 20
                bg_width = logo_width + padding * 2
                bg_height = logo_height + padding * 2

                # Create rounded rectangle mask
                rounded_bg = Image.new('RGBA', (bg_width, bg_height), (0, 0, 0, 0))
                mask = Image.new('L', (bg_width, bg_height), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.rounded_rectangle(
                    [(0, 0), (bg_width - 1, bg_height - 1)],
                    radius=corner_radius,
                    fill=255
                )

                # Apply white fill with rounded mask
                white_fill = Image.new('RGBA', (bg_width, bg_height), (255, 255, 255, 255))
                rounded_bg.paste(white_fill, mask=mask)

                # Convert QR to RGBA if needed
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')

                # Paste rounded white background
                img.paste(rounded_bg, (logo_x - padding, logo_y - padding), rounded_bg)

                # Paste logo
                if logo.mode == 'RGBA':
                    img.paste(logo, (logo_x, logo_y), logo)
                else:
                    img.paste(logo, (logo_x, logo_y))

            except Exception as e:
                logger.warning(f"Failed to add logo to QR code: {e}")

        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)

        logger.debug(f"Generated styled QR code for URL: {url[:50]}...")
        return buffer

    except ImportError as e:
        logger.error(f"qrcode styled components not available: {e}. Run: pip install qrcode[pil]")
        return None
    except Exception as e:
        logger.error(f"Failed to generate QR code: {e}")
        return None


def generate_qr_with_logo(
    url: str,
    logo_path: Optional[str] = None,
    box_size: int = 10,
    border: int = 2
) -> Optional[BytesIO]:
    """Generate QR code with optional center logo.

    Args:
        url: URL to encode
        logo_path: Path to logo image (optional)
        box_size: Size of each box in pixels
        border: Border size in boxes

    Returns:
        BytesIO buffer containing PNG image
    """
    try:
        import qrcode
        from qrcode.constants import ERROR_CORRECT_H
        from PIL import Image

        # Use higher error correction if adding logo
        error_correction = ERROR_CORRECT_H if logo_path else qrcode.constants.ERROR_CORRECT_M

        qr = qrcode.QRCode(
            version=1,
            error_correction=error_correction,
            box_size=box_size,
            border=border,
        )
        qr.add_data(url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white").convert('RGB')

        if logo_path:
            try:
                logo = Image.open(logo_path)

                # Calculate logo size (max 30% of QR code)
                qr_width, qr_height = img.size
                max_logo_size = int(qr_width * 0.3)

                # Resize logo maintaining aspect ratio
                logo.thumbnail((max_logo_size, max_logo_size), Image.Resampling.LANCZOS)
                logo_width, logo_height = logo.size

                # Center logo on QR code
                logo_x = (qr_width - logo_width) // 2
                logo_y = (qr_height - logo_height) // 2

                # Create white background for logo
                white_bg = Image.new('RGB', (logo_width + 10, logo_height + 10), 'white')
                img.paste(white_bg, (logo_x - 5, logo_y - 5))

                # Paste logo
                if logo.mode == 'RGBA':
                    img.paste(logo, (logo_x, logo_y), logo)
                else:
                    img.paste(logo, (logo_x, logo_y))

            except Exception as e:
                logger.warning(f"Failed to add logo to QR code: {e}")

        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)

        return buffer

    except ImportError:
        logger.error("Required libraries not installed. Run: pip install qrcode[pil] Pillow")
        return None
    except Exception as e:
        logger.error(f"Failed to generate QR code with logo: {e}")
        return None


if __name__ == "__main__":
    # Test QR code generation
    test_url = "https://example.com/test-breakdown?id=12345"

    print("Testing QR code generation...")

    qr_buffer = generate_qr_code(test_url)
    if qr_buffer:
        print(f"Generated QR code: {len(qr_buffer.getvalue())} bytes")

        # Save test file
        with open("test_qr.png", "wb") as f:
            f.write(qr_buffer.getvalue())
        print("Saved to test_qr.png")
    else:
        print("Failed to generate QR code")
