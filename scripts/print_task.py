"""
打印任务脚本
通过 ERP API 创建打印任务
"""
import sys
import json
import argparse

# 模拟 ERP API 调用
def main():
    parser = argparse.ArgumentParser(description="打印任务")
    parser.add_argument("sales_id", help="销售单ID")
    args = parser.parse_args()

    # 实际项目中调用 ERP API: SalesPrintTask
    # 这里模拟返回
    result = {
        "code": 0,
        "msg": "打印任务创建成功",
        "data": args.sales_id,
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
