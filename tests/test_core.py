import asyncio
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from types import SimpleNamespace
from urllib.parse import urlencode
from zoneinfo import ZoneInfo
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from gfs.domain import eligible, resolve_unit, extract_vins, validate_init_data, report, next_weekly
from gfs.db import Database
from gfs.monday import Monday
from gfs.scheduler import execute_job
from gfs.pdf import parse_pdf
from gfs.app import create_app, Broadcast


@pytest.mark.parametrize('title,photo,expected', [('42 INACTIVE', False, False), ('42 inactive', True, True), ('42 active', False, True), ('42 active', True, True)])
def test_filter_matrix(title, photo, expected):
    assert eligible(title, photo) == expected


def test_unit_conflicts_and_sub_prefix():
    units = {'42', '99'}
    assert resolve_unit('Sub 042 (12) Driver', units) == '42'
    assert resolve_unit('42 (99) Driver', units) is None
    assert resolve_unit('777 Driver', units) is None
    assert resolve_unit('42 42 Driver', units) == '42'


def signed_data(token='token', uid=7, stamp=None):
    data = {'auth_date': str(int(stamp or time.time())), 'user': json.dumps({'id': uid})}
    secret = hmac.new(b'WebAppData', token.encode(), hashlib.sha256).digest()
    data['hash'] = hmac.new(secret, '\n'.join(f'{k}={v}' for k,v in sorted(data.items())).encode(), hashlib.sha256).hexdigest()
    return urlencode(data)


def test_webapp_auth_rejects_forgery_and_expiry():
    assert validate_init_data(signed_data(), 'token') == 7
    with pytest.raises(ValueError):
        validate_init_data(signed_data(), 'wrong')
    with pytest.raises(ValueError):
        validate_init_data(signed_data(stamp=time.time()-4000), 'token')
    with pytest.raises(ValueError):
        validate_init_data(signed_data()+'&user=x', 'token')


def test_status_audit_independent_of_coi_and_monday_status_filter():
    groups = [{'present': 1, 'title': '42 Driver', 'photo': 0, 'unit': '42', 'manual_unit': None}]
    trucks = [{'unit': '42', 'vin': '1M8GDM9AXKP042788', 'status': 'SHOP'}]
    result = report({'1HGCM82633A004352'}, trucks, groups)
    assert '1HGCM82633A004352' in result
    assert 'SHOP' in result and '42 Driver' in result


def test_weekly_timezone():
    now = datetime(2026, 11, 4, 10, 0, tzinfo=timezone.utc)
    result = next_weekly(now, 2, 15, 0, ZoneInfo('Asia/Tashkent'))
    assert result == datetime(2026, 11, 11, 10, 0, tzinfo=timezone.utc).timestamp()


def test_pdf_multi_page_and_scan_detection():
    from io import BytesIO
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
    doc = PdfWriter()
    for vin in ['1M8GDM9AXKP042788', '1HGCM82633A004352']:
        page = doc.add_blank_page(300, 300)
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): font})})
        stream = DecodedStreamObject()
        stream.set_data(f'BT /F1 12 Tf 40 40 Td (COI vehicle VIN: {vin}) Tj ET'.encode())
        page[NameObject('/Contents')] = doc._add_object(stream)
    output = BytesIO()
    doc.write(output)
    assert parse_pdf(output.getvalue()) == {'1M8GDM9AXKP042788', '1HGCM82633A004352'}
    doc.add_blank_page(300, 300)
    output = BytesIO()
    doc.write(output)
    with pytest.raises(ValueError, match='skan'):
        parse_pdf(output.getvalue())
    assert not extract_vins('1234567890123456I')


@pytest.mark.parametrize("custom", [False, True])
def test_monday_strict_groups_and_pagination(monkeypatch, custom):
    monkeypatch.delenv('MONDAY_UNIT_SOURCE', raising=False)
    monkeypatch.delenv('MONDAY_GROUP_TITLES', raising=False)
    titles = ['TRUCKS IN USAGE', 'owner operators', 'upcoming', 'inactive']
    if custom:
        monkeypatch.setenv('MONDAY_UNIT_SOURCE', 'item_name')
        monkeypatch.setenv('MONDAY_GROUP_TITLES', 'TRUCKS IN USAGE|Owner Operators|UPCOMING UNITS:')
        titles = ['TRUCKS IN USAGE', 'Owner Operators', 'UPCOMING UNITS:', 'INACTIVE']
    m = Monday('token', '1', '2026-10')
    requested = []
    async def query(q, variables=None):
        if 'columns{id title}' in q:
            return {'boards': [{'name':'TRUCK FILES', 'columns':[{'id':x.lower(),'title':x} for x in ['Unit','VIN','Status']], 'groups':[{'id':str(i),'title':x} for i,x in enumerate(titles)]}]}
        requested.append((variables['groups'][0], variables['cursor']))
        return {'boards':[{'groups':[{'items_page':{'cursor':'next' if variables['cursor'] is None else None, 'items':[{'id':'1','name':'042 - LOCAL','column_values':[{'id':'unit','text':'042'},{'id':'vin','text':'1M8GDM9AXKP042788'},{'id':'status','text':'SHOP'}]}]}}]}]}
    m.query = query
    trucks = asyncio.run(m.trucks())
    assert len(trucks) == 6
    assert all(t['unit']=='42' for t in trucks)
    assert {g for g,c in requested} == {'0','1','2'}
    assert len([c for g,c in requested if c=='next']) == 3


def test_send_rechecks_live_filter_and_restart_deduplicates(tmp_path):
    db = Database(str(tmp_path/'db.sqlite'))
    for i in [1,2]:
        db.save_group(SimpleNamespace(id=i,title='Old title',photo=True))
    db.execute("INSERT INTO jobs(owner,payload,due,state) VALUES(7,?,1,'running')", (json.dumps({'kind':'text','text':'hello'}),))
    bot = SimpleNamespace(get_chat=AsyncMock(side_effect=lambda i: SimpleNamespace(id=i,title='INACTIVE' if i==1 else '42 Driver',photo=None)),send_message=AsyncMock())
    job = db.rows('SELECT * FROM jobs')[0]
    asyncio.run(execute_job(bot,db,job))
    assert bot.send_message.await_count == 1
    assert bot.send_message.call_args.args[0] == 2
    asyncio.run(execute_job(bot,db,job))
    assert bot.send_message.await_count == 1
    assert {r['state'] for r in db.rows('SELECT * FROM deliveries')} == {'sent','skipped'}


def test_api_access_and_job_persistence(tmp_path,monkeypatch):
    monkeypatch.setenv('DB_PATH',str(tmp_path/'db.sqlite'))
    monkeypatch.setenv('ADMIN_IDS','7')
    monkeypatch.setenv('BOT_TOKEN','token')
    client=TestClient(create_app())  # No lifespan: no network bot polling.
    assert client.get('/api/state').status_code == 403
    assert client.get('/api/state',headers={'Authorization':'tma '+signed_data(uid=9)}).status_code == 403
    headers={'Authorization':'tma '+signed_data()}
    assert client.post('/api/jobs',headers=headers,json={'text':'Hello'}).status_code == 200
    job=client.get('/api/state',headers=headers).json()['jobs'][0]
    assert job['state']=='pending'
    assert client.put(f'/api/jobs/{job["id"]}',headers=headers,json={'text':'Updated'}).status_code==200
    assert client.delete(f'/api/jobs/{job["id"]}',headers=headers).status_code==200
    assert client.get('/api/state',headers=headers).json()['jobs'][0]['state']=='cancelled'
    assert client.post('/api/jobs',headers=headers,json={'kind':'copy','source_chat':9,'source_message':1}).status_code==400
    assert client.get('/').status_code==200


def test_invalid_button_and_media_validation():
    with pytest.raises(ValueError):
        Broadcast(text='Hi', buttons=[[{'text':'go','callback_data':'x'*65}]])
    with pytest.raises(ValueError):
        Broadcast(kind='photo')


def test_manual_binding_survives_remapping_and_status_audit(tmp_path):
    db = Database(str(tmp_path/'db.sqlite'))
    db.save_group(SimpleNamespace(id=1, title='42 (99) Driver', photo=True))
    trucks = [{'unit': '42', 'vin': '1M8GDM9AXKP042788', 'status': 'SHOP'},
              {'unit': '99', 'vin': '1HGCM82633A004352', 'status': 'ACTIVE'}]
    db.remap(trucks)
    assert db.groups()[0]['unit'] is None
    db.execute('UPDATE groups SET manual_unit=? WHERE id=?', ('42', 1))
    db.remap(trucks)
    assert db.groups()[0]['manual_unit'] == '42'
    assert 'SHOP' in report(set(), trucks, db.groups())
    db.conn.close()


def test_failed_chat_does_not_block_other_deliveries(tmp_path):
    db = Database(str(tmp_path/'db.sqlite'))
    for i in (1, 2):
        db.save_group(SimpleNamespace(id=i, title=str(i), photo=True))
    db.execute("INSERT INTO jobs(owner,payload,due,state) VALUES(7,?,1,'running')", (json.dumps({'kind':'text','text':'hello'}),))
    async def get_chat(i):
        if i == 1:
            raise ConnectionError('offline')
        return SimpleNamespace(id=i, title=str(i), photo=True)
    bot = SimpleNamespace(get_chat=AsyncMock(side_effect=get_chat), send_message=AsyncMock())
    asyncio.run(execute_job(bot, db, db.rows('SELECT * FROM jobs')[0]))
    assert {r['chat']: r['state'] for r in db.rows('SELECT * FROM deliveries')} == {1:'failed', 2:'sent'}
    db.conn.close()


def test_invalid_weekly_timezone_is_validation_error():
    with pytest.raises(ValueError):
        Broadcast(text='test', weekly={'weekday': 0, 'hour': 12, 'minute': 0, 'timezone': 'invalid/timezone'})


def test_selected_recipients_and_admin_catalog(tmp_path, monkeypatch):
    monkeypatch.setenv('DB_PATH', str(tmp_path/'api.sqlite'))
    monkeypatch.setenv('ADMIN_IDS', '7')
    monkeypatch.setenv('BOT_TOKEN', 'token')
    client = TestClient(create_app())
    headers = {'Authorization': 'tma '+signed_data()}
    assert client.get('/api/audits', headers=headers).json() == []
    assert client.get('/api/admins').status_code == 403
    assert client.post('/api/admins', headers=headers, json={'user_id': 8}).status_code == 200
    assert {a['id'] for a in client.get('/api/admins', headers=headers).json()} == {7,8}
    assert client.post('/api/jobs', headers=headers, json={'text':'test','recipients':[-999]}).status_code == 400
    assert client.post('/api/jobs', headers=headers, json={'text':'test','recipients':[]}).status_code == 422


def test_scheduler_respects_recipient_selection(tmp_path):
    db = Database(str(tmp_path/'selected.sqlite'))
    for i in [1,2]:
        db.save_group(SimpleNamespace(id=i,title=str(i),photo=True))
    db.execute("INSERT INTO jobs(owner,payload,due,state) VALUES(7,?,1,'running')", (json.dumps({'kind':'text','text':'test','recipients':[2]}),))
    bot = SimpleNamespace(get_chat=AsyncMock(return_value=SimpleNamespace(id=2,title='2',photo=True)), send_message=AsyncMock())
    asyncio.run(execute_job(bot, db, db.rows('SELECT * FROM jobs')[0]))
    assert bot.send_message.await_count == 1
    assert bot.send_message.call_args.args[0] == 2
    db.conn.close()


def test_structured_audit_preserves_eligibility_and_missing_vins():
    from gfs.domain import audit_details
    groups = [dict(id=1, present=1, title="42 Driver", photo=0, unit="42", manual_unit=None),
              dict(id=2, present=1, title="42 INACTIVE", photo=0, unit="42", manual_unit=None)]
    trucks = [dict(unit="42", vin="1M8GDM9AXKP042788", status="SHOP")]
    facts = audit_details({"1HGCM82633A004352"}, trucks, groups)
    assert facts["vin_count"] == 1
    assert facts["missing_vins"] == ["1HGCM82633A004352"]
    assert facts["warnings"] == [dict(chat_id=1, title="42 Driver", unit="42", status="SHOP")]


def test_existing_database_audit_migration_preserves_reports(tmp_path):
    import sqlite3
    path = str(tmp_path / "legacy.sqlite")
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE audits(id INTEGER PRIMARY KEY, owner INTEGER, created REAL, filename TEXT, state TEXT, result TEXT, error TEXT)")
        conn.execute("INSERT INTO audits VALUES(1,7,0,'old.pdf','done','Original report',NULL)")
    db = Database(path)
    row = db.rows("SELECT * FROM audits")[0]
    assert row["result"] == "Original report" and row["details"] is None
    db.conn.close()



def test_admin_inline_callbacks(tmp_path, monkeypatch):
    from aiogram.types import Update, CallbackQuery, User
    from aiogram.methods import AnswerCallbackQuery
    monkeypatch.setenv('DB_PATH', str(tmp_path / 'cb.sqlite'))
    monkeypatch.setenv('ADMIN_IDS', '7')
    monkeypatch.setenv('BOT_TOKEN', '123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11')
    app = create_app()
    dp = app.state.dp
    db = app.state.db

    db.execute("INSERT INTO jobs(id,owner,payload,due,state) VALUES(101,7,'{}',1,'pending')")
    bot = AsyncMock()

    # 1. Non-admin clicking admin button
    q1 = CallbackQuery(id='cb_1', from_user=User(id=999, is_bot=False, first_name='Other'), chat_instance='c1', data='adm:main').as_(bot)
    asyncio.run(dp.feed_update(bot, Update(update_id=1, callback_query=q1)))
    calls1 = [c.args[0] for c in bot.call_args_list if c.args and isinstance(c.args[0], AnswerCallbackQuery)]
    assert any(c.text == "Sizda ruxsat yo'q!" for c in calls1)

    # 2. Admin clicking adm:cancel:101
    q2 = CallbackQuery(id='cb_2', from_user=User(id=7, is_bot=False, first_name='Admin'), chat_instance='c2', data='adm:cancel:101').as_(bot)
    asyncio.run(dp.feed_update(bot, Update(update_id=2, callback_query=q2)))
    assert db.rows("SELECT state FROM jobs WHERE id=101")[0]["state"] == "cancelled"

    # 3. Driver clicking regular button
    q3 = CallbackQuery(id='cb_3', from_user=User(id=888, is_bot=False, first_name='Driver'), chat_instance='c3', data='driver_choice').as_(bot)
    asyncio.run(dp.feed_update(bot, Update(update_id=3, callback_query=q3)))
    calls3 = [c.args[0] for c in bot.call_args_list if c.args and isinstance(c.args[0], AnswerCallbackQuery)]
    assert any(c.text == "Qabul qilindi" for c in calls3)

    db.conn.close()
