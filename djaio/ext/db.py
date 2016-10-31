# -*- coding: utf-8 -*-
import aiopg
from psycopg2.extras import DictCursor
from typing import List, Dict


class DB:

    def __init__(self, config: Dict):
        self.config = config
        self.dbs = {}

    async def init(self, loop=None):
        for _key, _creds in self.config.items():
            self.dbs[_key] = {}
            for _role, _dsn in _creds.items():
                self.dbs[_key][_role] = await aiopg.create_pool(
                    _dsn, minsize=1, maxsize=10, timeout=5, loop=loop
                )

    async def shutdown(self, app):
        # close connections

        for k, db in self.dbs.items():
            for role, item in db.items():
                if item is not None:
                    item.close()

        for k, db in self.dbs.items():
            for role, item in db.items():
                if item is not None:
                    await item.wait_closed()

    async def execute(self, db_name: str, query: str, values: List, _type: str):
        """
        Execute SQL query in connection pool
        :param db_name:
        :param query:
        :param values:
        :param _type:
        :return:
        """

        if _type not in ('select', 'insert', 'update', 'delete'):
            raise RuntimeError(
                'Wrong request type {}'.format(_type)
            )
        if not self.dbs[db_name]['master']:
            raise RuntimeError(
                'db {} master is not initialized'.format(db_name)
            )

        pool = self.dbs[db_name]['master']
        if _type == 'select' and 'slave' in self.dbs[db_name]:
            pool = self.dbs[db_name]['slave']

        async with pool.acquire() as conn:
            async with conn.cursor(cursor_factory=DictCursor) as cursor:
                await cursor.execute(query, values)

                if _type == 'select':
                    data = await cursor.fetchall()
                else:
                    cursor.connection.commit()
                    data = cursor.rowcount
        return data


def setup(app):
    db = DB(app.settings.DATABASE)
    app.loop.run_until_complete(db.init())
    app.db = db
    app.on_cleanup.append(db.shutdown)
