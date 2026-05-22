# 数据库清单与快速部署

更新时间：2026-05-20

这里记录北极星项目里每个数据库的用途、环境变量和建表脚本位置。密码不写进源代码，只从 `.env` 或部署环境变量读取。

## 1. 数据库清单

| 数据库 | 角色 | 用途 | 环境变量 |
|---|---|---|---|
| 旧 ShopXO/ERP 库 | 旧系统来源库 | 只读迁移来源；商品、客户、库存、销售历史从这里抽 | `DB_HOST`、`DB_PORT`、`DB_NAME`、`DB_USER`、`DB_PASSWORD` |
| `sjagent_core` | 北极星自有业务库 | 商品、客户、用户、订单流、销售、仓库库存、库存流水 | `SJAGENT_CORE_DB_HOST`、`SJAGENT_CORE_DB_PORT`、`SJAGENT_CORE_DB_NAME`、`SJAGENT_CORE_DB_USER`、`SJAGENT_CORE_DB_PASSWORD` |

机器可读清单：`database/databases.yaml`。

## 2. 建表脚本

建表 SQL 放在 `database/schema/`：

| 文件 | 内容 |
|---|---|
| `001_product_catalog.sql` | 商品中心、单位、分类、图片、迁移映射 |
| `002_business_core.sql` | 客户/供应商、用户身份、订单流、销售、仓库、库存、出入库、盘点、调拨、库存流水 |
| `003_system_settings.sql` | 系统设置：商品编号规则、编号调整记录、商品/库存/收款/图片/权限规则 |

通用部署脚本：

```powershell
python scripts\deploy_database_schema.py --database sjagent_core
```

如果新库只允许服务器本机访问，本地可以先开 SSH 隧道，再指定本地端口：

```powershell
$env:SJAGENT_CORE_DB_HOST='127.0.0.1'
$env:SJAGENT_CORE_DB_PORT='13306'
$env:SJAGENT_CORE_DB_NAME='sjagent_core'
$env:SJAGENT_CORE_DB_USER='sjagent_core'
$env:SJAGENT_CORE_DB_PASSWORD='<从安全位置填入>'
python scripts\deploy_database_schema.py --database sjagent_core
```

部署脚本会创建 `schema_deploy_log`，记录每次跑过哪些 SQL 文件和校验值。脚本可以重复执行，所有业务表都是 `CREATE TABLE IF NOT EXISTS`。

## 3. 数据迁移脚本

| 脚本 | 作用 |
|---|---|
| `scripts/migrate_product_catalog.py` | 从旧 ShopXO/ERP 导入商品中心 |
| `scripts/migrate_business_core.py` | 从旧 ShopXO/ERP 导入仓库、客户/供应商、用户身份、库存余额和初始库存流水 |

推荐顺序：

1. 运行 `deploy_database_schema.py` 建空表。
2. 运行 `migrate_product_catalog.py` 导商品。
3. 运行 `migrate_business_core.py` 导仓库、客户、用户、库存。
4. 抽样校验商品、客户、库存、销售历史价格。
