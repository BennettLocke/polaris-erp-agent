"""MySQL 直连客户端 - 库存查询用"""
import re
import pymysql
from pymysql.cursors import DictCursor
from contextlib import contextmanager
from typing import Optional
from src.core.config import get_config
from src.engine.exceptions import DBError
from src.utils import get_logger

logger = get_logger("sjagent.db_client")


class DatabaseClient:
    """
    MySQL 数据库客户端（长连接）
    用于库存直查，不走 API，节省 Token
    """

    _instance: Optional["DatabaseClient"] = None
    _connection: Optional[pymysql.Connection] = None

    def __new__(cls) -> "DatabaseClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self.config = get_config()
        self.db_config = self.config.db_config

    def _get_connection(self) -> pymysql.Connection:
        """获取或创建连接"""
        if self._connection is None or not self._connection.open:
            try:
                self._connection = pymysql.connect(
                    host=self.db_config["host"],
                    port=self.db_config["port"],
                    user=self.db_config["user"],
                    password=self.db_config["password"],
                    database=self.db_config["name"],
                    charset=self.db_config["charset"],
                    cursorclass=DictCursor,
                    autocommit=True,
                )
                logger.info("数据库连接已建立")
            except pymysql.Error as e:
                self._connection = None
                logger.error(f"数据库连接失败: {e}")
                raise DBError(f"数据库连接失败: {e}")
        else:
            # 检查连接是否存活
            try:
                self._connection.ping(reconnect=True)
            except pymysql.Error:
                logger.warning("数据库连接已失效，重新连接")
                self._connection = None
                return self._get_connection()
        return self._connection

    @contextmanager
    def cursor(self):
        """上下文管理器，自动释放 cursor"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
        finally:
            cursor.close()

    def query(self, sql: str, params: tuple = None) -> list[dict]:
        """执行查询并返回结果"""
        logger.info(f"SQL 查询: {sql[:200]}")
        try:
            with self.cursor() as cursor:
                cursor.execute(sql, params)
                results = cursor.fetchall()
                logger.info(f"查询返回 {len(results)} 条记录")
                return results
        except pymysql.OperationalError as e:
            # 连接断开，清空连接以便重连
            logger.warning(f"数据库连接断开，准备重连: {e}")
            self._connection = None
            raise DBError(f"SQL 查询失败（连接断开）: {e}")
        except pymysql.Error as e:
            logger.error(f"SQL 查询异常: {e}")
            raise DBError(f"SQL 查询失败: {e}")

    def execute(self, sql: str, params: tuple = None) -> int:
        """执行增删改，返回影响行数"""
        try:
            with self.cursor() as cursor:
                affected = cursor.execute(sql, params)
                logger.info(f"SQL 执行成功，影响 {affected} 行")
                return affected
        except pymysql.OperationalError as e:
            # 连接断开，清空连接以便重连
            logger.warning(f"数据库连接断开，准备重连: {e}")
            self._connection = None
            raise DBError(f"SQL 执行失败（连接断开）: {e}")
        except pymysql.Error as e:
            logger.error(f"SQL 执行异常: {e}")
            raise DBError(f"SQL 执行失败: {e}")

    def close(self):
        """关闭连接"""
        if self._connection and self._connection.open:
            self._connection.close()
            logger.info("数据库连接已关闭")

    # ---- 库存查询 SQL ----

    def get_product_inventory(self, product_id: int) -> list[dict]:
        """
        查询某产品各仓库库存
        按 order-flow 规范输出：产品名称 | 【颜色】 | 【仓库】 | 库存数量
        """
        sql = """
        SELECT
            p.title AS 产品名称,
            p.spec AS `【颜色】`,
            w.name AS `【仓库】`,
            wi.inventory AS 库存数量
        FROM sxo_plugins_erp_warehouse_product_inventory wi
        JOIN sxo_plugins_erp_product p ON p.id = wi.product_id
        JOIN sxo_plugins_erp_warehouse w ON w.id = wi.warehouse_id
        WHERE wi.product_id = %s
        ORDER BY w.id
        """
        return self.query(sql, (product_id,))

    def get_warehouse_inventory(self, warehouse_id: int) -> list[dict]:
        """查询某仓库全部有库存产品"""
        sql = """
        SELECT
            p.title AS 产品名称,
            p.spec AS `【颜色】`,
            w.name AS `【仓库】`,
            wi.inventory AS 库存数量
        FROM sxo_plugins_erp_warehouse_product_inventory wi
        JOIN sxo_plugins_erp_product p ON p.id = wi.product_id
        JOIN sxo_plugins_erp_warehouse w ON w.id = wi.warehouse_id
        WHERE w.id = %s AND wi.inventory > 0
        ORDER BY p.title, p.spec
        """
        return self.query(sql, (warehouse_id,))

    def search_inventory(
        self,
        keyword: str,
        color: str = "",
        only_in_stock: bool = False,
        limit: int = 100,
    ) -> list[dict]:
        """
        一次性按商品名/颜色查询库存，避免先查商品再逐个查库存的 N+1 查询。
        输出格式：产品名称 | 【颜色】 | 【仓库】 | 库存数量
        """
        terms = self._keyword_terms(keyword)
        normalized_title = (
            "REPLACE(REPLACE(REPLACE(REPLACE(p.title, '【', ''), '】', ''), ' ', ''), '　', '')"
        )
        where = []
        params: list = []
        for term in terms:
            one_term_where = []
            for variant in self._keyword_variants(term):
                one_term_where.append(
                    "("
                    "p.title LIKE %s "
                    "OR REPLACE(REPLACE(p.title, '【', ''), '】', '') LIKE %s "
                    f"OR {normalized_title} LIKE %s "
                    "OR p.spec LIKE %s"
                    ")"
                )
                params.extend([f"%{variant}%", f"%{variant}%", f"%{variant}%", f"%{variant}%"])
            where.append("(" + " OR ".join(one_term_where) + ")")

        if color:
            where.append("p.spec LIKE %s")
            params.append(f"%{color}%")
        if only_in_stock:
            where.append("wi.inventory > 0")

        params.append(limit)
        sql = f"""
        SELECT
            p.id AS product_id,
            p.title AS 产品名称,
            p.spec AS `【颜色】`,
            p.simple_desc,
            w.name AS `【仓库】`,
            wi.inventory AS 库存数量
        FROM sxo_plugins_erp_product p
        JOIN sxo_plugins_erp_warehouse_product_inventory wi ON wi.product_id = p.id
        JOIN sxo_plugins_erp_warehouse w ON w.id = wi.warehouse_id
        WHERE {' AND '.join(where)}
        ORDER BY p.title, p.spec, w.id
        LIMIT %s
        """
        return self.query(sql, tuple(params))

    def get_product_info(self, product_id: int) -> dict | None:
        """查询产品信息（含每件套数）"""
        sql = """
        SELECT id, title, spec, simple_desc, price
        FROM sxo_plugins_erp_product
        WHERE id = %s
        """
        results = self.query(sql, (product_id,))
        return results[0] if results else None

    def search_products(self, keyword: str) -> list[dict]:
        """模糊搜索产品"""
        terms = self._keyword_terms(keyword)
        normalized_title = (
            "REPLACE(REPLACE(REPLACE(REPLACE(title, '【', ''), '】', ''), ' ', ''), '　', '')"
        )
        where_parts = []
        params: list[str] = []
        for term in terms:
            one_term_where = []
            for variant in self._keyword_variants(term):
                one_term_where.append(
                    f"(title LIKE %s OR REPLACE(REPLACE(title, '【', ''), '】', '') LIKE %s OR {normalized_title} LIKE %s OR spec LIKE %s)"
                )
                params.extend([f"%{variant}%", f"%{variant}%", f"%{variant}%", f"%{variant}%"])
            where_parts.append("(" + " OR ".join(one_term_where) + ")")
        sql = """
        SELECT id, title, spec, simple_desc, price
        FROM sxo_plugins_erp_product
        WHERE """ + " AND ".join(where_parts) + """
        ORDER BY title, spec
        """
        return self.query(sql, tuple(params))

    def _compact_keyword(self, keyword: str) -> str:
        return (
            str(keyword or "")
            .replace("【", "")
            .replace("】", "")
            .replace(" ", "")
            .replace("　", "")
        )

    def _keyword_variants(self, keyword: str) -> list[str]:
        """Return numeric aliases so 2大盒/二大盒/两大盒 can find the same product."""
        compact = self._compact_keyword(keyword)
        variants: list[str] = []

        def add(value: str):
            value = self._compact_keyword(value)
            if value not in variants:
                variants.append(value)

        add(keyword)
        add(compact)
        if re.search(r"(?:3\s*两|2\s*两|三两|二两)", compact):
            add(re.sub(r"(?:3\s*两|2\s*两|(?<!二)三两|二两)", "二三两", compact))
        digit_to_words = {
            "1": ("一",),
            "2": ("二", "两"),
            "3": ("三",),
            "6": ("六",),
        }
        word_to_digit = {
            "一": "1",
            "二": "2",
            "两": "2",
            "三": "3",
            "六": "6",
        }
        queue = [compact]
        for value in queue:
            for digit, words in digit_to_words.items():
                if digit in value:
                    for word in words:
                        changed = value.replace(digit, word)
                        if changed not in queue:
                            queue.append(changed)
            for word, digit in word_to_digit.items():
                if word in value:
                    changed = value.replace(word, digit)
                    if changed not in queue:
                        queue.append(changed)
        for value in queue:
            add(value)
        return variants or [""]

    def _keyword_terms(self, keyword: str) -> list[str]:
        """把“喜悦 三小盒”一类组合词拆成必须同时命中的词。"""
        keyword = (keyword or "").strip()
        terms = [t for t in keyword.split() if t]
        return terms or [keyword]


def get_db_client() -> DatabaseClient:
    """获取数据库客户端单例"""
    return DatabaseClient()
