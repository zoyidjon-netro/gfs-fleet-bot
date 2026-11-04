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



def test_broadcast_command_and_timezone_scheduling(tmp_path, monkeypatch):
    from aiogram.types import Update, Message, CallbackQuery, User, Chat
    from aiogram.methods import AnswerCallbackQuery, SendMessage
    monkeypatch.setenv('DB_PATH', str(tmp_path / 'bc_test.sqlite'))
    monkeypatch.setenv('ADMIN_IDS', '7')
    monkeypatch.setenv('BOT_TOKEN', '123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11')
    app = create_app()
    dp = app.state.dp
    db = app.state.db

    db.save_group(SimpleNamespace(id=10, title="Unit 10 Driver", photo=True))
    db.save_group(SimpleNamespace(id=20, title="Unit 20 INACTIVE", photo=False))

    bot = AsyncMock()

    # 1. Test Broadcast model with Asia and USA timezones
    b_chicago = Broadcast(text="Hello US", schedule_time="2026-11-05T14:30", timezone="America/Chicago")
    b_tashkent = Broadcast(text="Hello UZ", schedule_time="2026-11-05T14:30", timezone="Asia/Tashkent")
    assert b_chicago.due == 1793910600.0
    assert b_tashkent.due == 1793871000.0
    assert b_chicago.due - b_tashkent.due == 11 * 3600

    # 2. Test /broadcast command from admin
    msg = Message(
        message_id=1,
        date=datetime.now(),
        chat=Chat(id=7, type="private"),
        from_user=User(id=7, is_bot=False, first_name="Admin"),
        text="/broadcast Diqqat barchaga!"
    ).as_(bot)
    asyncio.run(dp.feed_update(bot, Update(update_id=10, message=msg)))
    calls = [c.args[0] for c in bot.call_args_list if c.args and isinstance(c.args[0], SendMessage)]
    assert any("Diqqat barchaga!" in c.text for c in calls)

    pending_jobs = db.rows("SELECT * FROM jobs WHERE state='pending'")
    assert len(pending_jobs) == 1
    job_id = pending_jobs[0]["id"]

    # 3. Test confirming send_now
    q_send = CallbackQuery(
        id="cb_send",
        from_user=User(id=7, is_bot=False, first_name="Admin"),
        chat_instance="c_send",
        data=f"adm:send_now:{job_id}"
    ).as_(bot)
    asyncio.run(dp.feed_update(bot, Update(update_id=11, callback_query=q_send)))
    assert db.rows(f"SELECT state FROM jobs WHERE id={job_id}")[0]["state"] in ("running", "done")

    db.conn.close()


def test_admin_crud_api_and_bot_actions(tmp_path, monkeypatch):
    from aiogram.types import Update, Message, CallbackQuery, User, Chat
    from aiogram.methods import AnswerCallbackQuery, SendMessage, EditMessageText

    TOKEN = '123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11'
    monkeypatch.setenv('DB_PATH', str(tmp_path / 'admin_crud.sqlite'))
    monkeypatch.setenv('ADMIN_IDS', '7')
    monkeypatch.setenv('BOT_TOKEN', TOKEN)

    app = create_app()
    client = TestClient(app)
    headers = {'Authorization': 'tma ' + signed_data(token=TOKEN, uid=7)}
    dp = app.state.dp
    db = app.state.db
    bot = AsyncMock()

    # 1. API: Read initial admins
    admins = client.get('/api/admins', headers=headers).json()
    assert len(admins) == 1
    assert admins[0]['id'] == 7
    assert admins[0]['role'] == 'superadmin'

    # 2. API: Create admin with name and role
    res = client.post('/api/admins', headers=headers, json={'user_id': 88, 'name': 'Alisher', 'role': 'admin'})
    assert res.status_code == 200
    assert res.json()['id'] == 88
    assert res.json()['role'] == 'admin'

    admins = client.get('/api/admins', headers=headers).json()
    assert len(admins) == 2
    admin_88 = next(a for a in admins if a['id'] == 88)
    assert admin_88['name'] == 'Alisher'
    assert admin_88['role'] == 'admin'

    # 3. API: Update admin
    res = client.put('/api/admins/88', headers=headers, json={'name': 'Alisher Yangilandi', 'role': 'superadmin'})
    assert res.status_code == 200
    admin_88_updated = next(a for a in client.get('/api/admins', headers=headers).json() if a['id'] == 88)
    assert admin_88_updated['name'] == 'Alisher Yangilandi'
    assert admin_88_updated['role'] == 'superadmin'

    # 4. API: 404 for updating non-existent admin
    assert client.put('/api/admins/9999', headers=headers, json={'name': 'Yoq'}).status_code == 404

    # 5. API: Delete admin
    assert client.delete('/api/admins/88', headers=headers).status_code == 200
    assert len(client.get('/api/admins', headers=headers).json()) == 1

    # 6. API: 400 when attempting to delete the last admin
    del_last = client.delete('/api/admins/7', headers=headers)
    assert del_last.status_code == 400
    assert "Oxirgi" in del_last.json()['detail']

    # 7. Bot: /add_admin command
    msg_add = Message(
        message_id=101,
        date=datetime.now(),
        chat=Chat(id=7, type="private"),
        from_user=User(id=7, is_bot=False, first_name="Admin"),
        text="/add_admin 99 Sardor admin"
    ).as_(bot)
    asyncio.run(dp.feed_update(bot, Update(update_id=101, message=msg_add)))
    assert db.is_admin(99)
    admin_99 = db.rows("SELECT * FROM admins WHERE id=99")[0]
    assert admin_99["name"] == "Sardor"
    assert admin_99["role"] == "admin"

    # 8. Bot: /edit_admin command
    msg_edit = Message(
        message_id=102,
        date=datetime.now(),
        chat=Chat(id=7, type="private"),
        from_user=User(id=7, is_bot=False, first_name="Admin"),
        text="/edit_admin 99 Sardorbek"
    ).as_(bot)
    asyncio.run(dp.feed_update(bot, Update(update_id=102, message=msg_edit)))
    assert db.rows("SELECT name FROM admins WHERE id=99")[0]["name"] == "Sardorbek"

    # 9. Bot: inline callback confirmation and deletion
    q_confirm = CallbackQuery(
        id="cb_conf",
        from_user=User(id=7, is_bot=False, first_name="Admin"),
        chat_instance="c_conf",
        data="adm:del_admin_confirm:99"
    ).as_(bot)
    asyncio.run(dp.feed_update(bot, Update(update_id=103, callback_query=q_confirm)))

    q_do = CallbackQuery(
        id="cb_do",
        from_user=User(id=7, is_bot=False, first_name="Admin"),
        chat_instance="c_do",
        data="adm:del_admin_do:99"
    ).as_(bot)
    asyncio.run(dp.feed_update(bot, Update(update_id=104, callback_query=q_do)))
    assert not db.is_admin(99)

    # 10. Bot: /del_admin command safety check on last admin
    msg_del_last = Message(
        message_id=105,
        date=datetime.now(),
        chat=Chat(id=7, type="private"),
        from_user=User(id=7, is_bot=False, first_name="Admin"),
        text="/del_admin 7"
    ).as_(bot)
    bot.reset_mock()
    asyncio.run(dp.feed_update(bot, Update(update_id=105, message=msg_del_last)))
    send_calls = [c.args[0] for c in bot.call_args_list if c.args and isinstance(c.args[0], SendMessage)]
    assert any("Oxirgi administratorni o'chirib bo'lmaydi" in c.text for c in send_calls)
    assert db.is_admin(7)

    # 11. API: Add admin by username (@username and plain username) & string ID
    db.execute("INSERT INTO users(id, username) VALUES(?, ?)", (555, "dilshod"))
    res_uname = client.post('/api/admins', headers=headers, json={'identifier': '@dilshod', 'role': 'superadmin', 'name': 'Dilshod'})
    assert res_uname.status_code == 200
    assert res_uname.json()['id'] == 555
    assert db.is_admin(555)

    # Plain string ID
    res_str_id = client.post('/api/admins', headers=headers, json={'identifier': '777', 'role': 'admin'})
    assert res_str_id.status_code == 200
    assert res_str_id.json()['id'] == 777
    assert db.is_admin(777)

    # Unknown username returns 404
    assert client.post('/api/admins', headers=headers, json={'identifier': '@nonexistent_user'}).status_code == 404

    # 12. Bot: adm:add_admin_prompt callback and reply to prompt
    msg_box = Message(message_id=50, date=datetime.now(), chat=Chat(id=7, type="private"))
    q_prompt = CallbackQuery(
        id="cb_prompt",
        from_user=User(id=7, is_bot=False, first_name="Admin"),
        chat_instance="c_prompt",
        message=msg_box,
        data="adm:add_admin_prompt"
    ).as_(bot)
    bot.reset_mock()
    asyncio.run(dp.feed_update(bot, Update(update_id=106, callback_query=q_prompt)))
    assert any("Yangi administrator qo'shish" in c.args[0].text for c in bot.call_args_list if c.args and isinstance(c.args[0], SendMessage))

    # User replies to prompt with username
    db.execute("INSERT INTO users(id, username) VALUES(?, ?)", (666, "bekzod"))
    prompt_msg = Message(
        message_id=200,
        date=datetime.now(),
        chat=Chat(id=7, type="private"),
        text="✍️ Yangi administrator qo'shish:"
    )
    reply_msg = Message(
        message_id=201,
        date=datetime.now(),
        chat=Chat(id=7, type="private"),
        from_user=User(id=7, is_bot=False, first_name="Admin"),
        text="@bekzod Bekzod admin",
        reply_to_message=prompt_msg
    ).as_(bot)
    bot.reset_mock()
    asyncio.run(dp.feed_update(bot, Update(update_id=107, message=reply_msg)))
    assert db.is_admin(666)
    assert any("Administrator muvaffaqiyatli qo'shildi" in c.args[0].text for c in bot.call_args_list if c.args and isinstance(c.args[0], SendMessage))

    # 13. Verify that admin buttons display usernames
    q_admins = CallbackQuery(
        id="cb_adm_list",
        from_user=User(id=7, is_bot=False, first_name="Admin"),
        chat_instance="c_adm",
        message=msg_box,
        data="adm:admins"
    ).as_(bot)
    bot.reset_mock()
    asyncio.run(dp.feed_update(bot, Update(update_id=108, callback_query=q_admins)))
    edit_calls = [c.args[0] for c in bot.call_args_list if c.args and isinstance(c.args[0], EditMessageText)]
    assert any("🗑 @bekzod" in btn.text for call in edit_calls for row in call.reply_markup.inline_keyboard for btn in row)

    db.conn.close()


def test_multi_language_support(tmp_path, monkeypatch):
    from gfs.i18n import t
    from aiogram.types import Update, Message, CallbackQuery, User, Chat
    from aiogram.methods import SendMessage, EditMessageText, AnswerCallbackQuery

    # 1. Test i18n dictionary translations
    assert t("btn_sync", "uz") == "🔄 Sinxronlash"
    assert t("btn_sync", "ru") == "🔄 Синхронизация"
    assert t("btn_sync", "en") == "🔄 Synchronize"
    assert t("btn_sync", "fr") == "🔄 Sinxronlash"  # fallback

    TOKEN = '123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11'
    monkeypatch.setenv('DB_PATH', str(tmp_path / 'lang_test.sqlite'))
    monkeypatch.setenv('ADMIN_IDS', '7')
    monkeypatch.setenv('BOT_TOKEN', TOKEN)

    app = create_app()
    client = TestClient(app)
    headers = {'Authorization': 'tma ' + signed_data(token=TOKEN, uid=7)}
    dp = app.state.dp
    db = app.state.db
    bot = AsyncMock()

    # 2. Test DB language helpers
    assert db.get_lang(7) == "uz"
    db.set_lang(7, "ru")
    assert db.get_lang(7) == "ru"
    db.set_lang(7, "en")
    assert db.get_lang(7) == "en"
    db.set_lang(7, "unknown")
    assert db.get_lang(7) == "uz"

    # 3. Test API /api/user/lang and /api/state
    res = client.get('/api/user/lang', headers=headers)
    assert res.status_code == 200
    assert res.json()['lang'] == 'uz'

    res_post = client.post('/api/user/lang', headers=headers, json={'lang': 'ru'})
    assert res_post.status_code == 200
    assert res_post.json()['lang'] == 'ru'
    assert db.get_lang(7) == 'ru'

    state = client.get('/api/state', headers=headers).json()
    assert state['lang'] == 'ru'

    # 4. Test Bot /lang command
    msg_lang = Message(
        message_id=301,
        date=datetime.now(),
        chat=Chat(id=7, type="private"),
        from_user=User(id=7, is_bot=False, first_name="Admin"),
        text="/lang"
    ).as_(bot)
    bot.reset_mock()
    asyncio.run(dp.feed_update(bot, Update(update_id=201, message=msg_lang)))
    send_calls = [c.args[0] for c in bot.call_args_list if c.args and isinstance(c.args[0], SendMessage)]
    assert len(send_calls) >= 1
    buttons = [btn.callback_data for row in send_calls[0].reply_markup.inline_keyboard for btn in row]
    assert "adm:lang:uz" in buttons
    assert "adm:lang:ru" in buttons
    assert "adm:lang:en" in buttons

    # 5. Test switching to English via callback query
    msg_box = Message(message_id=302, date=datetime.now(), chat=Chat(id=7, type="private"))
    q_en = CallbackQuery(
        id="cb_lang_en",
        from_user=User(id=7, is_bot=False, first_name="Admin"),
        chat_instance="c_lang",
        message=msg_box,
        data="adm:lang:en"
    ).as_(bot)
    bot.reset_mock()
    asyncio.run(dp.feed_update(bot, Update(update_id=202, callback_query=q_en)))
    assert db.get_lang(7) == "en"
    edit_calls = [c.args[0] for c in bot.call_args_list if c.args and isinstance(c.args[0], EditMessageText)]
    assert any("Use the buttons below to control the bot" in c.text for c in edit_calls)

    # 6. Test switching to Russian via callback query
    q_ru = CallbackQuery(
        id="cb_lang_ru",
        from_user=User(id=7, is_bot=False, first_name="Admin"),
        chat_instance="c_lang",
        message=msg_box,
        data="adm:lang:ru"
    ).as_(bot)
    bot.reset_mock()
    asyncio.run(dp.feed_update(bot, Update(update_id=203, callback_query=q_ru)))
    assert db.get_lang(7) == "ru"
    edit_calls = [c.args[0] for c in bot.call_args_list if c.args and isinstance(c.args[0], EditMessageText)]
    assert any("Используйте меню ниже" in c.text for c in edit_calls)

    # 7. Test switching back to Uzbek via callback query
    q_uz = CallbackQuery(
        id="cb_lang_uz",
        from_user=User(id=7, is_bot=False, first_name="Admin"),
        chat_instance="c_lang",
        message=msg_box,
        data="adm:lang:uz"
    ).as_(bot)
    bot.reset_mock()
    asyncio.run(dp.feed_update(bot, Update(update_id=204, callback_query=q_uz)))
    assert db.get_lang(7) == "uz"
    edit_calls = [c.args[0] for c in bot.call_args_list if c.args and isinstance(c.args[0], EditMessageText)]
    assert any("Botni boshqarish uchun" in c.text for c in edit_calls)

    db.conn.close()
