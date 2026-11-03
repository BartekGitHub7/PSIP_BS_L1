"""Promote audited aggregate inputs to QA, preserving geometry and existing fields.
Default validates and rolls back. Full database backup must precede --write.
"""
import argparse
import subprocess
from pathlib import Path
import psycopg
from psycopg import sql

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--write',action='store_true')
p.add_argument('--database',choices=['psip','iop_rehearsal_20261103'],default='psip')
a=p.parse_args()
root=Path(__file__).resolve().parents[1]
branch=subprocess.check_output(['git','branch','--show-current'],cwd=root,text=True).strip()
if a.write and a.database=='psip' and branch!='env-qa':
    raise ValueError('Production QA data promotion requires env-qa branch')
def connect(env,port,database):
    password=subprocess.check_output(['docker','exec',f'remote-db-{env}-postgis-1','printenv','POSTGRES_PASSWORD'],text=True).strip()
    return psycopg.connect(host='localhost',port=port,dbname=database,user='psip',password=password)
with connect('env-test',5444,'psip') as source,connect('env-qa',5445,a.database) as target:
    source.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
    target.execute("SET lock_timeout='10s'")
    for r in (6,7,8):
        table=f'h3_r{r}'
        relation=sql.Identifier('grid',table)
        target.execute(sql.SQL('LOCK TABLE {} IN SHARE ROW EXCLUSIVE MODE').format(relation))
        identity=sql.SQL('SELECT h3_id::text,encode(ST_AsEWKB(geom),\'hex\') FROM {} ORDER BY h3_id').format(relation)
        assert source.execute(identity).fetchall()==target.execute(identity).fetchall(), 'QA geometry/ID differs: '+table
        columns=source.execute("SELECT column_name,data_type FROM information_schema.columns WHERE table_schema='grid' AND table_name=%s AND left(column_name,3)='ot_' ORDER BY column_name",(table,)).fetchall()
        assert len(columns)==68 and all(t=='double precision' for _,t in columns), columns
        names=[n for n,_ in columns]
        existing={n for n, in target.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='grid' AND table_name=%s",(table,))}
        fields=sql.SQL(',').join(map(sql.Identifier,names))
        rows=source.execute(sql.SQL('SELECT h3_id::text,{} FROM {} ORDER BY h3_id').format(fields,relation)).fetchall()
        # Refuse to overwrite populated aggregate data with different source values.
        shared=[n for n in names if n in existing]
        if shared:
            subset=sql.SQL(',').join(map(sql.Identifier,shared))
            assert source.execute(sql.SQL('SELECT h3_id::text,{} FROM {} ORDER BY h3_id').format(subset,relation)).fetchall()==target.execute(sql.SQL('SELECT h3_id::text,{} FROM {} ORDER BY h3_id').format(subset,relation)).fetchall(), 'QA existing aggregates differ'
        for name in names:
            if name not in existing:
                target.execute(sql.SQL('ALTER TABLE {} ADD COLUMN {} double precision').format(relation,sql.Identifier(name)))
        assignments=sql.SQL(',').join(sql.SQL('{}=%s').format(sql.Identifier(n)) for n in names)
        with target.cursor() as cur:
            cur.executemany(sql.SQL('UPDATE {} SET {} WHERE h3_id::text=%s').format(relation,assignments),[tuple(v[1:])+(v[0],) for v in rows])
        print(table,len(rows),'geometry/IDs identical; 68 aggregate columns promoted')
    migration=(root/'gui/add_passability.sql').read_text(encoding='utf-8')
    # Execute only the migration body within the same atomic transaction.
    body=migration[migration.index('DO $$'):migration.index('COMMIT;')]
    target.execute(body)
    if not a.write:
        target.rollback()
        print('DRY RUN: all QA changes rolled back')
    else:
        print('COMMIT: QA inputs ready for independent IOP calculation')
