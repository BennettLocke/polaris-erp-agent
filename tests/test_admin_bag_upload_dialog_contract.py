from pathlib import Path
import re
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKBENCH = ROOT / "admin/src/components/business/workbench"


class AdminBagUploadDialogContractTest(unittest.TestCase):
    def source(self, name):
        path = WORKBENCH / name
        self.assertTrue(path.exists(), f"Missing bag upload implementation: {name}")
        return path.read_text(encoding="utf-8")

    def test_shortcut_opens_dialog_without_chat_or_pending_changes(self):
        source = self.source("workbench-page.tsx")
        command = source.split("function insertCommand(", 1)[1].split("function handleKeyDown(", 1)[0]
        self.assertIn('command === "上传泡袋"', command)
        self.assertIn('command === "泡袋上传"', command)
        self.assertIn("setBagUploadOpen(true)", command)
        self.assertNotIn("sendMessage", command)
        self.assertNotIn("setSessionSnapshot", command)
        self.assertNotIn("setFiles", command)
        self.assertIn("<BagUploadDialog", source)

    def test_completion_uses_local_message_cache_without_refreshing_pending(self):
        source = self.source("workbench-page.tsx")
        self.assertIn("function completeBagUpload(", source)
        complete = source.split("function completeBagUpload(", 1)[1].split("function insertCommand(", 1)[0]
        self.assertIn('appendMessage("assistant"', complete)
        self.assertIn('"bag-upload"', complete)
        self.assertIn("pushBusinessHistory", complete)
        for forbidden in ["sendMessage", "agentChat", "agentHistory", "setSessionSnapshot", "updateSessionPending", "createNewSession", "setFiles", "setInput"]:
            self.assertNotIn(forbidden, complete)
        self.assertIn("saveJson(messageStorageKey(sessionId)", source)
        self.assertIn('current.filter((message) => message.source === "bag-upload")', source)

    def test_upload_is_isolated_from_chat_and_uses_product_cache(self):
        source = self.source("bag-upload-dialog.tsx")
        for forbidden in ["agentChat", "sendMessage", "agentHistory", "updateSessionPending", "setSessionSnapshot", "localStorage", "setInterval"]:
            self.assertNotIn(forbidden, source)
        self.assertIn("api.agentUploadLimits()", source)
        self.assertIn("queryKeys.products.root", source)
        self.assertIn("api.uploadBags(", source)
        self.assertIn("claimBagUpload(submitLock", source)
        self.assertIn("phase: phaseRef.current", source)
        self.assertIn('phaseRef.current = "complete"', source)
        self.assertIn("onEscapeKeyDown", source)
        self.assertIn("onInteractOutside", source)
        self.assertIn("showCloseButton={!isUploading}", source)
        self.assertIn("if (submitLock.current) return;", source)
        self.assertIn('setPhase(uncertain ? "uncertain" : "idle")', source)
        self.assertIn("先核对商品库", source)
        self.assertIn("Loader2", source)
        self.assertNotIn("<Progress", source)

    def test_dialog_uses_scoped_standard_controls_and_result_tables(self):
        source = self.source("bag-upload-dialog.tsx")
        for component in ["Dialog", "DialogTitle", "Tabs", "TabsList", "TabsTrigger", "Checkbox", "FieldGroup", "Field", "Input", "Button", "Alert", "Table", "TableHead", "TableCell"]:
            self.assertIn(f"<{component}", source)
        self.assertNotIn("<Card", source)
        self.assertNotIn("multiple", source)
        self.assertIn("result.success.map", source)
        self.assertIn("result.failures.map", source)
        css = self.source("bag-upload-dialog.css")
        self.assertIn('.bag-upload-dialog [data-slot="checkbox"]', css)
        for rule in ["width: 18px", "height: 18px", "min-width: 18px", "min-height: 18px", "max-width: 18px", "max-height: 18px", "padding: 0"]:
            self.assertIn(rule, css)
        self.assertNotIn(":root", css)
        listed = css.split('.bag-upload-dialog .bag-upload-listed {', 1)[1].split('}', 1)[0]
        self.assertIn("display: flex", listed)

    def test_segmented_control_reuses_declared_tabs_and_copy_is_concise(self):
        source = self.source("bag-upload-dialog.tsx")
        self.assertIn('from "@/components/ui/tabs"', source)
        self.assertIn('activationMode="automatic"', source)
        self.assertNotIn("@radix-ui/react-roving-focus", source)
        self.assertNotIn("function ToggleGroup", source)
        self.assertNotIn('role="radio"', source)
        self.assertIn("上传完成后上架", source)
        self.assertIn("选择压缩包", source)
        self.assertNotIn("result.summary", source)
        for value in ["result.total", "result.success.length", "result.failures.length"]:
            self.assertIn(value, source)

    def test_scoped_css_uses_existing_project_tokens(self):
        css = self.source("bag-upload-dialog.css")
        global_css = (ROOT / "admin/src/styles.css").read_text(encoding="utf-8")
        referenced = set(re.findall(r"var\((--[\w-]+)", css))
        declared = set(re.findall(r"(--[\w-]+)\s*:", global_css))
        self.assertFalse(referenced - declared, f"Undefined tokens: {referenced - declared}")

    def test_api_types_match_batch_contract(self):
        types = (ROOT / "admin/src/types.ts").read_text(encoding="utf-8")
        for name in ["BagType", "BagUploadOptions", "BagUploadResult", "BagUploadSuccess", "BagUploadFailure"]:
            self.assertIn(f"export type {name}", types)
        result = types.split("export type BagUploadResult =", 1)[1].split("};", 1)[0]
        for field in ["bag_type: string", "price: number", "is_listed: boolean", "total: number", "success: BagUploadSuccess[]", "failures: BagUploadFailure[]", "summary: string"]:
            self.assertIn(field, result)

    def test_failure_filename_is_optional_and_preferred_over_cleaned_title(self):
        types = (ROOT / "admin/src/types.ts").read_text(encoding="utf-8")
        failure = types.split("export type BagUploadFailure =", 1)[1].split("};", 1)[0]
        self.assertIn("filename?: string", failure)
        source = self.source("bag-upload-dialog.tsx")
        failures_table = source.split("result.failures.map", 1)[1].split("</TableBody>", 1)[0]
        self.assertIn("<TableCell>{item.filename || item.title}</TableCell>", failures_table)

    def test_pure_validation_submission_guard_and_multipart_contract(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node is required for frontend helper contract tests")
        test = WORKBENCH / "bag-upload-dialog.test.cjs"
        self.assertTrue(test.exists())
        completed = subprocess.run([node, "--test", test.relative_to(ROOT / "admin").as_posix()], cwd=ROOT / "admin", capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main()
