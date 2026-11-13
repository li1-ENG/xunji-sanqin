import os
import sys
import tempfile
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / 'data' / 'smoke_test.db'
if DB_PATH.exists():
    DB_PATH.unlink()
os.environ['DATABASE_URL'] = f"sqlite:///{DB_PATH.as_posix()}"
os.environ['DEEPSEEK_API_KEY'] = ''
os.environ['AI_WEB_SEARCH_ENABLED'] = '0'
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from PIL import Image
from backend.app.main import app
from backend.app.database import engine


with TestClient(app) as client:
    assert client.get('/api/health').status_code == 200
    login = client.post('/api/admin/auth/login', json={'account': '传统村落后台管理', 'password': 'SX666'})
    assert login.status_code == 200, login.text
    headers = {'Authorization': 'Bearer ' + login.json()['access_token']}
    imported = client.post('/api/admin/import/processed', headers=headers)
    assert imported.status_code == 200, imported.text
    stats = client.get('/api/stats').json()
    assert stats['village_count'] == 37, stats
    assert stats['city_count'] == 6, stats
    city = client.get('/api/cities/weinan/villages').json()
    assert city['villages'] and 'summary' not in city['villages'][0]
    village = client.get('/api/villages/61058110401').json()
    assert village['name'] and village['sections']
    ai = client.post('/api/ai/chat', json={'message': '党家村有哪些代表性建筑？', 'deep_thinking': False})
    assert ai.status_code == 200, ai.text
    ai_payload = ai.json()
    assert ai_payload['answer'] and ai_payload['sources'], ai_payload
    assert ai_payload['mode'] == 'local_archive', ai_payload
    greeting = client.post('/api/ai/chat', json={'message': '你好', 'deep_thinking': True})
    assert greeting.status_code == 200, greeting.text
    greeting_payload = greeting.json()
    assert greeting_payload['mode'] == 'conversation', greeting_payload
    assert greeting_payload['answer'] and not greeting_payload['sources'], greeting_payload
    small_talk = client.post('/api/ai/chat', json={'message': '我今天有点累，陪我聊聊吧', 'deep_thinking': True})
    assert small_talk.status_code == 200, small_talk.text
    small_talk_payload = small_talk.json()
    assert small_talk_payload['mode'] == 'conversation', small_talk_payload
    assert small_talk_payload['answer'] and not small_talk_payload['sources'], small_talk_payload
    image_buffer = BytesIO()
    Image.new('RGB', (96, 64), (210, 205, 195)).save(image_buffer, format='PNG')
    uploaded = client.post(
        f"/api/admin/villages/{village['id']}/media/upload",
        headers=headers,
        files={'file': ('test.png', image_buffer.getvalue(), 'image/png')},
        data={'title': '测试图片'},
    )
    assert uploaded.status_code == 201, uploaded.text
    uploaded_payload = uploaded.json()
    assert uploaded_payload['url'].startswith('/uploads/'), uploaded_payload
    deleted_media = client.delete(f"/api/admin/media/{uploaded_payload['id']}", headers=headers)
    assert deleted_media.status_code == 200, deleted_media.text
    invalid_feedback = client.post('/api/feedback', json={'message': 'invalid email test', 'email': 'not-an-email'})
    assert invalid_feedback.status_code == 422, invalid_feedback.text
    feedback = client.post('/api/feedback', json={'message': 'smoke test', 'village_name': 'test', 'city': 'xian'})
    assert feedback.status_code == 201, feedback.text
    admin_feedback = client.get('/api/admin/feedback', headers=headers)
    assert admin_feedback.status_code == 200 and admin_feedback.json()['total'] >= 1
    assert client.get('/admin').status_code == 200
    print('smoke test passed', stats)

engine.dispose()
if DB_PATH.exists():
    DB_PATH.unlink()
