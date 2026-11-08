from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

from sme.models import Base


def test_every_runtime_table_is_innodb_and_utf8mb4():
    for table in Base.metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(dialect=mysql.dialect())).lower()
        assert 'engine=innodb' in ddl, table.name
        assert 'charset=utf8mb4' in ddl, table.name
