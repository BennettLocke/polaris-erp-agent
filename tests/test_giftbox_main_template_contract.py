import unittest
import base64
import io
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "scripts" / "giftbox_main_template"


class GiftboxMainTemplateContractTest(unittest.TestCase):
    def test_template_exposes_modular_swatches_and_svg_factory(self):
        source = (TEMPLATE_DIR / "template.js").read_text(encoding="utf-8")

        self.assertIn("const DEFAULT_SWATCHES", source)
        self.assertIn("function normalizeSwatches", source)
        self.assertIn("function createGiftboxMainSvg", source)
        self.assertIn("swatches", source)
        self.assertIn("specBadgeConfig", source)
        self.assertIn("spec-badge", source)
        self.assertIn("productShadow", source)
        self.assertIn('filter="url(#productShadow)"', source)
        self.assertIn("safeTopY: 365", source)
        self.assertIn("const IMAGE_FRAME = productFrame(DEFAULT_OPTIONS.productFrameConfig)", source)
        self.assertIn("module.exports", source)
        self.assertIn('preserveAspectRatio="xMidYMax meet"', source)
        self.assertNotIn('preserveAspectRatio="xMidYMid slice"', source)

    def test_preview_uses_shared_template_and_file_upload(self):
        source = (TEMPLATE_DIR / "preview.html").read_text(encoding="utf-8")

        self.assertIn("template.js", source)
        self.assertIn('id="product-image-input"', source)
        self.assertIn('id="swatch-list"', source)
        self.assertIn("createGiftboxMainSvg", source)
        self.assertIn("trimImageWhitespace", source)
        self.assertIn("download-svg-button", source)

    def test_generate_cli_uses_shared_template_and_color_option(self):
        source = (TEMPLATE_DIR / "generate.js").read_text(encoding="utf-8")

        self.assertIn("createGiftboxMainSvg", source)
        self.assertIn("--colors", source)
        self.assertIn("--no-trim", source)
        self.assertIn("render_svg_resvg.js", source)
        self.assertIn("trimImageWhitespace", source)
        self.assertIn("trim_whitespace.py", source)
        self.assertIn("imageToDataUri", source)
        self.assertIn("pythonCommandCandidates", source)
        self.assertIn('candidates.push("python", "python3")', source)
        self.assertIn("result.error.message", source)

    def test_generate_cli_trims_white_space_before_embedding_svg(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.png"
            output = Path(temp_dir) / "output.svg"
            image = Image.new("RGBA", (100, 100), (255, 255, 255, 255))
            for y in range(42, 78):
                for x in range(32, 68):
                    image.putpixel((x, y), (20, 20, 20, 255))
            image.save(source)

            subprocess.run(
                [
                    "node",
                    str(TEMPLATE_DIR / "generate.js"),
                    "--image",
                    str(source),
                    "--output",
                    str(output),
                ],
                cwd=str(ROOT),
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            svg = output.read_text(encoding="utf-8")
            match = re.search(r'href="data:image/png;base64,([^"]+)"', svg)
            self.assertIsNotNone(match)
            embedded = Image.open(io.BytesIO(base64.b64decode(match.group(1))))
            self.assertLess(embedded.width, 100)
            self.assertLess(embedded.height, 100)
            self.assertEqual(embedded.mode, "RGBA")
            self.assertLess(embedded.getpixel((0, 0))[3], 16)


if __name__ == "__main__":
    unittest.main()
