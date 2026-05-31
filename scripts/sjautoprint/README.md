# sjAutoPrint 本地打印服务

`sjAutoPrint` 是 sjagent 的本地 Windows 打印代理。它会轮询线上打印队列，生成销售单 PDF，并发送到本机打印机。

## 文件

- `auto_print.py`：Windows 服务入口。
- `config.example.json`：默认配置模板。
- `install_sjautoprint.ps1`：安装或迁移服务。会把旧服务 `ShopXOAutoPrint` 移除，并创建 `sjAutoPrint`。
- `uninstall_sjautoprint.ps1`：卸载 `sjAutoPrint` 服务。

## 安装

用管理员 PowerShell 在项目根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\sjautoprint\install_sjautoprint.ps1
```

默认安装到 `C:\printer`，默认连接 `https://ai.513sjbz.com`，默认打印机是 `Kyocera TASKalfa 1800`。

如果打印机名称不同：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\sjautoprint\install_sjautoprint.ps1 -PrinterName "你的打印机名称"
```

安装脚本只覆盖打印代理代码和配置，不会删除 `C:\printer\pdf_output`、`C:\printer\logs`、`C:\printer\node_modules`、`C:\printer\SumatraPDF` 等运行目录。

## 配置

安装后配置文件在：

```text
C:\printer\config.json
```

常用字段：

- `base_url`：sjagent 服务地址，线上为 `https://ai.513sjbz.com`。
- `printer_name`：本机打印机名称。
- `check_interval`：轮询间隔秒数。
- `print_token`：如果后续打开打印代理令牌校验，在这里填写。

环境变量仍然可以覆盖配置文件，例如 `SJAGENT_PRINT_BASE_URL`、`SJAGENT_PRINTER_NAME`、`SJAGENT_PRINT_CHECK_INTERVAL`。

## 卸载

用管理员 PowerShell 执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\sjautoprint\uninstall_sjautoprint.ps1
```
