from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
ADMIN = ROOT / "admin" / "src"


class AdminPrintFeedbackContractTest(unittest.TestCase):
    def test_web_can_query_sales_print_task_status(self):
        http_source = (ROOT / "src" / "channels" / "http_api" / "__init__.py").read_text(encoding="utf-8")
        api_source = (ADMIN / "api.ts").read_text(encoding="utf-8")
        types_source = (ADMIN / "types.ts").read_text(encoding="utf-8")

        self.assertIn('/api/sales/print-tasks/<int:task_id>', http_source)
        self.assertIn('sales_print_task_status_api', http_source)
        self.assertIn('get_sales_service().print_task_row(task_id)', http_source)
        self.assertIn('/api/sales/print-tasks/${id}', api_source)
        self.assertIn('salesPrintTaskStatus', api_source)
        self.assertIn('customer_name?: string', types_source)
        self.assertIn('created_at?: string', types_source)

    def test_react_admin_uses_unified_print_feedback(self):
        app_source = (ADMIN / "App.tsx").read_text(encoding="utf-8")
        customer_source = (
            ADMIN / "components" / "business" / "customers" / "customer-detail-dialog.tsx"
        ).read_text(encoding="utf-8")
        feedback_path = ADMIN / "components" / "business" / "print-feedback.tsx"
        self.assertTrue(feedback_path.exists(), "print feedback must be shared across print entry points")
        feedback_source = feedback_path.read_text(encoding="utf-8")

        self.assertIn("useSalesPrintFeedback", feedback_source)
        self.assertIn("PrintFeedbackToast", feedback_source)
        self.assertIn("打印任务已提交", feedback_source)
        self.assertIn("已发送到打印机", feedback_source)
        self.assertIn("本地打印程序暂未接收", feedback_source)
        self.assertIn("salesPrintTaskStatus", feedback_source)
        self.assertIn("setTimeout", feedback_source)

        self.assertIn("useSalesPrintFeedback", app_source)
        self.assertIn("<PrintFeedbackToast", app_source)
        self.assertIn("printFeedback.printSales", app_source)
        self.assertIn("useSalesPrintFeedback", customer_source)
        self.assertIn("<PrintFeedbackToast", customer_source)


if __name__ == "__main__":
    unittest.main()
