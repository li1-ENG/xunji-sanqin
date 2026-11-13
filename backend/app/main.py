from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from .config import CORS_ORIGINS, UPLOAD_DIR
from .database import SessionLocal, init_db
from .security import ensure_default_admin
from .routers import admin, ai, auth, public

STATIC_DIR = Path(__file__).resolve().parent / 'static'

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        ensure_default_admin(db)
    finally:
        db.close()
    yield

app = FastAPI(
    title='陕西传统村落后端管理',
    description='传统村落数据、内容与反馈管理 API',
    version='1.0.0',
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)
app.include_router(public.router)
app.include_router(ai.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.mount('/static', StaticFiles(directory=str(STATIC_DIR)), name='static')
app.mount('/uploads', StaticFiles(directory=str(UPLOAD_DIR)), name='uploads')

def html_response(filename: str) -> FileResponse:
    return FileResponse(
        STATIC_DIR / filename,
        headers={
            'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
            'Pragma': 'no-cache',
            'Expires': '0',
        },
    )

@app.get('/', include_in_schema=False)
def home_page():
    return html_response('home.html')

@app.get('/admin', include_in_schema=False)
def admin_page():
    return html_response('admin.html')

@app.get('/feedback', include_in_schema=False)
def feedback_page():
    return html_response('feedback.html')

@app.get('/home', include_in_schema=False)
@app.get('/home-v3', include_in_schema=False)
@app.get('/home-v2', include_in_schema=False)
@app.get('/home-demo', include_in_schema=False)
def legacy_home():
    return RedirectResponse('/', status_code=307, headers={'Cache-Control': 'no-store'})

@app.get('/villages', include_in_schema=False)
def villages_page():
    return html_response('villages.html')

@app.get('/villages/{city_slug}/{village_id}', include_in_schema=False)
def city_village_page(city_slug: str, village_id: str):
    return html_response('village.html')
@app.get('/villages/{slug}', include_in_schema=False)
def city_page(slug: str):
    return html_response('city.html')

@app.get('/ai', include_in_schema=False)
def ai_page():
    return html_response('ai.html')

@app.get('/village/{village_id}', include_in_schema=False)
def village_page(village_id: str):
    return html_response('village.html')

@app.get('/village-demo', include_in_schema=False)
def village_demo(id: str | None = None):
    target = f'/village/{id}' if id else '/village/61058110401'
    return RedirectResponse(target, status_code=307, headers={'Cache-Control': 'no-store'})