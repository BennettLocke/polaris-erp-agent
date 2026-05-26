from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AdminVisualTokensContractTest(unittest.TestCase):
    def test_react_admin_uses_local_component_visual_tokens(self):
        css_source = (ROOT / "admin" / "src" / "styles.css").read_text(encoding="utf-8")

        for required in [
            '--sj-font-sans: "PingFang SC", "PingFang TC", "Microsoft YaHei UI", "Microsoft YaHei", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;',
            "--sj-foreground: #18181b;",
            "--sj-muted: #71717a;",
            "--sj-border: #e4e4e7;",
            "--sj-input-border: #d4d4d8;",
            "--sj-button-height-xs: 24px;",
            "--sj-button-height-sm: 28px;",
            "--sj-button-height-md: 32px;",
            "--sj-button-height-lg: 36px;",
            "--sj-input-height: 36px;",
            "--sj-card-radius: 14px;",
            "--sj-card-shadow: 0 0 0 1px rgba(24, 24, 27, 0.1);",
        ]:
            self.assertIn(required, css_source)

        self.assertRegex(
            css_source,
            r"\.primary-action\s*\{[^}]*background:\s*var\(--sj-button-primary\)",
        )
        self.assertRegex(css_source, r"\.sj-combobox input\s*\{[^}]*height:\s*var\(--sj-input-height\)")
        self.assertRegex(css_source, r"\.sj-combobox input\s*\{[^}]*border-radius:\s*var\(--sj-input-radius\)")

        allowed_hex = {
            "#000000",
            "#09090b",
            "#18181b",
            "#27272a",
            "#3f3f46",
            "#52525b",
            "#71717a",
            "#a1a1aa",
            "#166534",
            "#991b1b",
            "#d4d4d8",
            "#bbf7d0",
            "#dcfce7",
            "#e4e4e7",
            "#fecaca",
            "#fee2e2",
            "#f4f4f5",
            "#fafafa",
            "#ffffff",
        }
        actual_hex = {match.lower() for match in re.findall(r"#[0-9a-fA-F]{6,8}", css_source)}
        self.assertLessEqual(actual_hex, allowed_hex)

        for legacy_color in [
            "#1d9478",
            "#0f766e",
            "#13735f",
            "#edf8f5",
            "#eefaf6",
            "#ecfdf5",
            "#a9d9cd",
            "#b8ddd3",
            "#b42318",
            "#d64545",
            "#fff1f0",
            "#fff8e5",
        ]:
            self.assertNotIn(legacy_color, css_source)


if __name__ == "__main__":
    unittest.main()
