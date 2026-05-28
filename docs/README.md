# sjagent 文档目录

当前文档只保留正在维护的部署说明、API 合同、页面项目书、数据库迁移记录和检测报告。旧后台迁移期计划、临时执行清单和已经完成的 UI 底座计划已从仓库移除。

## 当前入口

- 运营后台：`/admin`
- 健康检查：`/health`
- 小程序接口：`/api/mini/*`
- 后台登录 API：继续使用 `/api/web-auth/*`，这是现有 React 后台的会话接口名，不代表旧后台页面仍保留。

## 推荐阅读顺序

1. `../README.md`
2. `react_admin_api_contract.md`
3. `react_admin_page_design_blueprint.md`
4. 页面项目书：`react_admin_*_page_development_handbook.md`
5. `native_runtime_cutover.md`
6. `sjagent_system_audit_report_2026-05-28.md`
