from __future__ import annotations

import asyncio
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..config import (
    AI_MAX_OUTPUT_TOKENS,
    AI_REQUEST_TIMEOUT,
    AI_WEB_SEARCH_ENABLED,
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_CHAT_MODEL,
    DEEPSEEK_REASONER_MODEL,
    TAVILY_API_KEY,
    WEB_SEARCH_ALLOWED_DOMAINS,
    WEB_SEARCH_TIMEOUT,
)
from ..models import City, Village, VillageSection

TYPE_LABELS = {
    'history': '历史文化',
    'architecture': '传统建筑',
    'environment': '环境格局',
    'customs': '民俗文化',
    'intangible_heritage': '非物质文化遗产',
    'production': '物产生产',
    'food': '美食物产',
    'travel': '旅游导览',
    'cultural_relic': '文物古迹',
    'scenic': '自然景观',
    'oral_history': '口述历史',
    'legends': '传说故事',
}

CATEGORY_KEYWORDS = {
    'architecture': ('建筑', '民居', '院落', '门楼', '屋顶', '窑洞', '街巷', '祠堂', '古建', '布局', '房屋'),
    'history': ('历史', '迁徙', '建村', '人物', '族谱', '宗族', '年代', '古迹', '文物'),
    'environment': ('环境', '山水', '地形', '地理', '河流', '山脉', '田园', '生态'),
    'customs': ('民俗', '习俗', '节庆', '节日', '礼仪', '非遗', '技艺', '表演', '社火'),
    'intangible_heritage': ('非遗', '非物质文化遗产', '传承', '技艺', '表演', '社火', '皮影', '剪纸'),
    'food': ('美食', '饮食', '小吃', '物产', '特产', '吃什么'),
    'travel': ('旅游', '路线', '交通', '门票', '开放', '游览', '怎么去', '导览', '行程'),
}

REGION_CITIES = {
    '陕北': {'yulin', 'yanan'},
    '关中': {'xian', 'xianyang', 'weinan', 'baoji', 'tongchuan'},
    '陕南': {'hanzhong', 'ankang', 'shangluo'},
}

STOP_PHRASES = (
    '有哪些', '是什么', '有什么', '怎么样', '怎么', '如何', '介绍一下', '介绍', '一下',
    '能不能', '可以', '告诉我', '请问', '推荐', '一条', '这个', '那个', '哪些', '什么',
    '相关', '关于', '陕西', '传统村落', '古村落', '古村', '村落', '资料', '信息', '请',
    '我', '的', '吗', '呢', '和', '与', '及', '以及',
)

DYNAMIC_TERMS = ('最新', '现在', '新闻', '开放', '门票', '交通', '路线', '活动', '通知', '2025', '2026')

class PageTextExtractor(HTMLParser):
    BLOCK_TAGS = {'p', 'h1', 'h2', 'h3', 'h4', 'li', 'article', 'section', 'br'}
    SKIP_TAGS = {'script', 'style', 'noscript', 'svg'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
        elif tag in self.BLOCK_TAGS and not self.skip_depth:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.SKIP_TAGS and self.skip_depth:
            self.skip_depth -= 1
        elif tag in self.BLOCK_TAGS and not self.skip_depth:
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.skip_depth and data.strip():
            self.parts.append(re.sub(r'\s+', ' ', data.strip()))

    def text(self):
        raw = ' '.join(self.parts)
        raw = re.sub(r'\s*\n\s*', '\n', raw)
        raw = re.sub(r'\n{2,}', '\n', raw)
        raw = re.sub(r'[ \t]{2,}', ' ', raw)
        return raw.strip()


@dataclass
class RetrievedSource:
    kind: str
    title: str
    text: str
    url: str
    village: str = ''
    city: str = ''
    section: str = ''
    domain: str = ''
    source_url: str = ''
    accessed_at: str = ''
    score: float = 0.0

    def public(self, index: int) -> dict:
        data = asdict(self)
        data['id'] = index
        data['excerpt'] = self.text[:260]
        data.pop('text', None)
        data.pop('score', None)
        return data


def _normalize(text: str) -> str:
    return re.sub(r'\s+', ' ', (text or '').strip()).lower()


def _query_terms(query: str) -> set[str]:
    text = _normalize(query)
    for phrase in sorted(STOP_PHRASES, key=len, reverse=True):
        text = text.replace(phrase, ' ')
    chunks = re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z0-9]{2,}', text)
    terms: set[str] = set()
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        if len(chunk) <= 10:
            terms.add(chunk)
        if len(chunk) >= 4:
            terms.add(chunk[:2])
            terms.add(chunk[-2:])
        if len(chunk) >= 6:
            terms.add(chunk[:4])
            terms.add(chunk[-4:])
    return {term for term in terms if len(term) >= 2}


def _categories(query: str) -> set[str]:
    hits = set()
    for category, words in CATEGORY_KEYWORDS.items():
        if any(word in query for word in words):
            hits.add(category)
    return hits


def _excerpt(text: str, terms: set[str], limit: int = 360) -> str:
    clean = re.sub(r'[ \t]+', ' ', (text or '').strip())
    clean = re.sub(r'\s*\n\s*', '。', clean)
    if not clean:
        return ''
    sentences = [s.strip() for s in re.split(r'(?<=[。！？；])', clean) if s.strip()]
    picked = [s for s in sentences if any(term in s for term in terms)]
    value = ''.join(picked[:3]) if picked else clean
    return value[:limit].rstrip() + ('…' if len(value) > limit else '')


def _is_plain_conversation(query: str) -> bool:
    village_terms = ('村', '传统村落', '古村', '陕西', '陕北', '关中', '陕南', '民居', '窑洞', '祠堂', '非遗', '民俗', '建筑', '历史', '保护', '旅游', '路线', '美食', '物产')
    if any(term in query for term in village_terms):
        return False
    if any(term in query for term in GENERAL_CHAT_TERMS):
        return True
    return len(re.sub(r'\s+', '', query)) <= 20


def conversation_reply(query: str) -> tuple[str, str] | None:
    cleaned = re.sub(r'[\s，。！？!?,.、~～]+', '', (query or '').lower())
    if not cleaned:
        return ('你好，我是小秦同学。你可以问我陕西传统村落的历史、建筑、民俗、非遗、美食物产和旅行路线。', 'greeting')
    greetings = {'你好', '您好', '嗨', '哈喽', 'hello', 'hi', '在吗', '在不在', '早上好', '上午好', '中午好', '下午好', '晚上好', '你好呀', '小秦同学你好', '你好小秦同学'}
    if cleaned in greetings or (len(cleaned) <= 12 and cleaned.startswith('你好')):
        return ('你好，我是小秦同学。你可以问我陕西传统村落的历史、建筑、民俗、非遗、美食物产和旅行路线。', 'greeting')
    if any(word in cleaned for word in ('你是谁', '你叫什么', '介绍一下你', '介绍你自己')):
        return ('我是小秦同学，是“寻迹三秦”的村落导游。我会先检索村落档案，再结合深度思考回答问题，并附上资料来源。', 'identity')
    if any(word in cleaned for word in ('你能做什么', '你会什么', '能帮我什么', '怎么用', '使用方法', '能识别我说的话', '能听懂我')):
        return ('我可以和你正常交流，也可以回答陕西传统村落的历史、建筑、环境、民俗、非遗、物产和旅行路线。涉及村落事实时，我会先查资料并标注来源；资料不足时会直接说明，不编造。', 'capabilities')
    if any(word in cleaned for word in ('谢谢', '感谢', '辛苦了', '多谢')):
        return ('不客气。如果你想继续了解某座村落，直接告诉我村名和感兴趣的方向就可以。', 'thanks')
    if any(word in cleaned for word in ('再见', '拜拜', '晚安')):
        return ('再见，欢迎随时回来继续逛村落。', 'farewell')
    return None


def retrieve_archive(db: Session, query: str, village_ref: str | None = None, context: str = '') -> list[RetrievedSource]:
    villages = db.scalars(
        select(Village)
        .where(Village.status == 'published')
        .options(
            selectinload(Village.city),
            selectinload(Village.sections),
        )
        .order_by(Village.sort_order, Village.id)
    ).all()
    if not villages:
        return []

    query_norm = _normalize(query)
    entity_norm = _normalize(query + ' ' + context)
    terms = _query_terms(query)
    categories = _categories(query_norm)
    regions = {region for region in REGION_CITIES if region in entity_norm}

    named_villages = []
    for village in villages:
        name = village.name or ''
        short_name = re.sub(r'村$', '', name)
        if village_ref and village_ref in {str(village.id), village.source_id, village.slug}:
            named_villages.append(village)
        elif name and (name in entity_norm or (len(short_name) >= 2 and short_name in entity_norm)):
            named_villages.append(village)
    named_ids = {village.id for village in named_villages}

    city_terms = {city.slug for city in {v.city for v in villages if v.city}}
    named_cities = {slug for slug in city_terms if slug in entity_norm}

    candidates: list[RetrievedSource] = []
    for village in villages:
        if named_ids and village.id not in named_ids:
            continue
        village_named = village.id in named_ids
        city_named = village.city.slug in named_cities
        region_named = bool(regions & REGION_CITIES.keys() & {r for r in regions if village.city.slug in REGION_CITIES.get(r, set())})
        base_score = 48 if village_named else 0
        if city_named:
            base_score += 16
        if region_named:
            base_score += 8

        if village.summary:
            summary_score = base_score + (8 if village_named else 0)
            if summary_score > 0 or any(term in village.summary for term in terms):
                candidates.append(RetrievedSource(
                    kind='archive',
                    title=f'{village.name} · 村落概况',
                    text=_excerpt(village.summary, terms, 420),
                    url=f'/villages/{village.city.slug}/{village.source_id}',
                    village=village.name,
                    city=village.city.name,
                    section='村落概况',
                    source_url=village.source_url,
                    score=summary_score + sum(2 for term in terms if term in village.summary),
                ))

        for section in village.sections:
            content = section.content_text or ''
            title = section.title or TYPE_LABELS.get(section.type, section.type)
            score = base_score
            if section.type in categories:
                score += 14
            if any(term in title for term in terms):
                score += 12
            if any(term in section.type for term in terms):
                score += 6
            for term in terms:
                count = content.count(term)
                if count:
                    score += min(5, 1 + count // 2)
            if score < 10:
                continue
            excerpt = _excerpt(content, terms)
            if not excerpt:
                continue
            candidates.append(RetrievedSource(
                kind='archive',
                title=f'{village.name} · {title}',
                text=excerpt,
                url=f'/villages/{village.city.slug}/{village.source_id}',
                village=village.name,
                city=village.city.name,
                section=title,
                source_url=section.source_url,
                score=score,
            ))

    candidates.sort(key=lambda item: (-item.score, item.village, item.title))
    per_village_limit = 5 if named_ids else 2
    selected: list[RetrievedSource] = []
    seen = set()
    per_village: dict[str, int] = {}
    for item in candidates:
        key = (item.village, item.section, item.text[:80])
        if key in seen:
            continue
        if per_village.get(item.village, 0) >= per_village_limit:
            continue
        seen.add(key)
        selected.append(item)
        per_village[item.village] = per_village.get(item.village, 0) + 1
        if len(selected) >= 6:
            break
    return selected


def _public_sources(sources: list[RetrievedSource]) -> list[dict]:
    return [source.public(index) for index, source in enumerate(sources, 1)]


def _extractive_answer(query: str, sources: list[RetrievedSource]) -> str:
    if not sources:
        return '当前村落档案中没有找到足够可靠的资料。请补充具体村落名称、想了解的历史建筑或民俗项目，我再为你检索。'
    lines = ['根据现有村落档案，可以确认以下信息：']
    for index, source in enumerate(sources[:3], 1):
        lines.append(f'{index}. 这里是一段取自《{source.village or source.title}》的「{source.section or source.title}」资料：{source.text}')
    lines.append('以上内容均来自站点已整理资料或已标注的公开来源；档案未覆盖的部分不作推测。')
    return '\n\n'.join(lines)


def _should_search_web(query: str, sources: list[RetrievedSource]) -> bool:
    if not AI_WEB_SEARCH_ENABLED:
        return False
    if any(term in query for term in DYNAMIC_TERMS):
        return True
    if not sources:
        return True
    return len(sources) < 2 or sources[0].score < 24


def _allowed_domain(host: str) -> bool:
    host = (host or '').lower().strip('.')
    return any(host == domain or host.endswith('.' + domain) for domain in WEB_SEARCH_ALLOWED_DOMAINS)


async def _bing_rss(client: httpx.AsyncClient, query: str) -> list[RetrievedSource]:
    try:
        response = await client.get(
            'https://www.bing.com/search',
            params={'q': query, 'format': 'rss'},
            headers={'User-Agent': 'Mozilla/5.0 (compatible; XunJiSanQin/1.0)'},
        )
        response.raise_for_status()
        root = ET.fromstring(response.text)
    except Exception:
        return []

    items: list[RetrievedSource] = []
    for node in root.findall('.//item'):
        title = (node.findtext('title') or '').strip()
        link = (node.findtext('link') or '').strip()
        description = re.sub(r'<[^>]+>', ' ', node.findtext('description') or '')
        description = re.sub(r'\s+', ' ', description).strip()
        parsed = urlparse(link)
        if parsed.scheme not in {'http', 'https'} or not _allowed_domain(parsed.hostname or ''):
            continue
        items.append(RetrievedSource(
            kind='web',
            title=title or parsed.hostname or '公开资料',
            text=description[:500],
            url=link,
            domain=parsed.hostname or '',
            accessed_at=datetime.now(timezone.utc).date().isoformat(),
            score=1.0,
        ))
    return items


async def _fetch_page(client: httpx.AsyncClient, source: RetrievedSource) -> RetrievedSource:
    try:
        response = await client.get(
            source.url,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; XunJiSanQin/1.0)'},
        )
        response.raise_for_status()
        content_type = response.headers.get('content-type', '')
        if 'html' not in content_type.lower():
            return source
        parser = PageTextExtractor()
        parser.feed(response.text[:1_500_000])
        text = parser.text()
        if len(text) >= 80:
            source.text = _excerpt(text, set(), 1800)
        return source
    except Exception:
        return source


async def _tavily_search(client: httpx.AsyncClient, query: str, limit: int) -> list[RetrievedSource]:
    if not TAVILY_API_KEY:
        return []
    try:
        response = await client.post(
            'https://api.tavily.com/search',
            json={
                'api_key': TAVILY_API_KEY,
                'query': query,
                'search_depth': 'advanced',
                'include_domains': list(WEB_SEARCH_ALLOWED_DOMAINS),
                'max_results': limit,
                'include_raw_content': False,
            },
        )
        response.raise_for_status()
        results = response.json().get('results') or []
    except Exception:
        return []
    items: list[RetrievedSource] = []
    for result in results:
        url = str(result.get('url') or '')
        parsed = urlparse(url)
        if parsed.scheme not in {'http', 'https'} or not _allowed_domain(parsed.hostname or ''):
            continue
        text = re.sub(r'\s+', ' ', str(result.get('content') or '')).strip()
        if not text:
            continue
        items.append(RetrievedSource(
            kind='web',
            title=str(result.get('title') or parsed.hostname or '公开资料'),
            text=text[:1800],
            url=url,
            domain=parsed.hostname or '',
            accessed_at=datetime.now(timezone.utc).date().isoformat(),
            score=2.0,
        ))
    return items


async def search_official_web(query: str, limit: int = 4) -> list[RetrievedSource]:
    if not AI_WEB_SEARCH_ENABLED:
        return []
    search_queries = [
        f'{query} 陕西 传统村落 site:gov.cn',
        f'{query} site:dmctv.cn',
        f'{query} site:whhlyt.shaanxi.gov.cn',
        f'{query} site:ncha.gov.cn',
    ]
    try:
        async with httpx.AsyncClient(timeout=WEB_SEARCH_TIMEOUT, follow_redirects=True) as client:
            merged = await _tavily_search(client, query, limit)
            if merged:
                return merged[:limit]
            batches = await asyncio.gather(*[_bing_rss(client, item) for item in search_queries])
            merged = []
            seen = set()
            for batch in batches:
                for item in batch:
                    if item.url in seen:
                        continue
                    seen.add(item.url)
                    merged.append(item)
            merged = merged[:limit]
            if merged:
                fetched = await asyncio.gather(*[_fetch_page(client, item) for item in merged])
                merged = [item for item in fetched if item.text and len(item.text) >= 20]
            return merged[:limit]
    except Exception:
        return []



VILLAGE_QUERY_TERMS = ('村', '传统村落', '古村', '陕西', '陕北', '关中', '陕南', '民居', '窑洞', '祠堂', '非遗', '民俗', '建筑', '历史', '保护', '旅游', '路线', '美食', '物产')
GENERAL_CHAT_TERMS = ('今天', '心情', '累', '开心', '难过', '压力', '聊天', '聊聊', '交流', '说话', '听懂', '笑话', '故事', '喜欢', '觉得', '建议', '加油', '朋友', '生活', '学习', '考试', '比赛', '陪我')


def _looks_like_village_query(query: str) -> bool:
    if any(term in query for term in VILLAGE_QUERY_TERMS):
        return True
    return not any(term in query for term in GENERAL_CHAT_TERMS)


def _conversation_fallback() -> str:
    return '???????????????????????????????????????????????????????'


async def _deepseek_conversation(query: str, history: list[dict]) -> tuple[str | None, str | None, str | None]:
    if not DEEPSEEK_API_KEY:
        return None, None, '??? DEEPSEEK_API_KEY'
    system = (
        '????????????????????????????????????????????????'
        '??????????????????????????????'
        '????????????????????????????????????????????????'
        '???????????????????????????????????????'
    )
    messages = [{'role': 'system', 'content': system}]
    for item in history[-6:]:
        role = item.get('role')
        content = str(item.get('content') or '').strip()
        if role in {'user', 'assistant'} and content:
            messages.append({'role': role, 'content': content[:1200]})
    messages.append({'role': 'user', 'content': query})
    try:
        async with httpx.AsyncClient(timeout=AI_REQUEST_TIMEOUT) as client:
            response = await client.post(
                f'{DEEPSEEK_BASE_URL}/chat/completions',
                headers={'Authorization': f'Bearer {DEEPSEEK_API_KEY}', 'Content-Type': 'application/json'},
                json={
                    'model': DEEPSEEK_CHAT_MODEL,
                    'messages': messages,
                    'stream': False,
                    'max_tokens': min(AI_MAX_OUTPUT_TOKENS, 500),
                    'temperature': 0.55,
                },
            )
            response.raise_for_status()
            data = response.json()
            content = ((data.get('choices') or [{}])[0].get('message') or {}).get('content')
            if content and content.strip():
                return content.strip(), DEEPSEEK_CHAT_MODEL, None
    except Exception as exc:
        return None, None, str(exc)
    return None, None, 'DeepSeek ???????'

def _build_context(sources: list[RetrievedSource]) -> str:
    blocks = []
    for index, source in enumerate(sources, 1):
        origin = f'本地村落档案，详情页 {source.url}'
        if source.kind == 'web':
            origin = f'公开网页 {source.url}，域名 {source.domain}，访问日期 {source.accessed_at}'
        blocks.append(
            f'[{index}] 来源：{origin}\n'
            f'标题：{source.title}\n村落：{source.village or "未注明"}\n模块：{source.section or source.title}\n'
            f'资料正文：{source.text[:2200]}'
        )
    return '\n\n'.join(blocks)


async def _deepseek_answer(query: str, history: list[dict], sources: list[RetrievedSource], deep_thinking: bool) -> tuple[str | None, str | None, str | None]:
    if not DEEPSEEK_API_KEY:
        return None, None, '未配置 DEEPSEEK_API_KEY'
    system = (
        '你是“小秦同学”，陕西传统村落数字档案的讲解员。只能依据用户消息中提供的资料回答，'
        '不得补充资料之外的历史、人物、数字或现实政策。回答使用中文，先直接回答问题，再给出依据。'
        '引用资料时只能使用 [1]、[2] 这样的编号，不能编造网址或来源。'
        '如果资料不足以回答，明确说“现有资料不足”，并指出还缺少什么信息。'
        '对存在争议的内容要说明“资料存在不同说法”，不能把推测写成事实。'
    )
    history_lines = []
    for item in history[-6:]:
        role = '用户' if item.get('role') == 'user' else '小秦同学'
        history_lines.append(f'{role}：{str(item.get("content") or "")[:800]}')
    user_content = (
        f'当前问题：{query}\n\n'
        f'最近对话：\n' + ('\n'.join(history_lines) if history_lines else '无') + '\n\n'
        f'可引用资料：\n{_build_context(sources)}\n\n'
        '请只根据上述资料回答，并标注 [编号]。'
    )
    messages = [{'role': 'system', 'content': system}, {'role': 'user', 'content': user_content}]
    models = [DEEPSEEK_REASONER_MODEL if deep_thinking else DEEPSEEK_CHAT_MODEL]
    if deep_thinking and DEEPSEEK_CHAT_MODEL not in models:
        models.append(DEEPSEEK_CHAT_MODEL)

    last_error = None
    async with httpx.AsyncClient(timeout=AI_REQUEST_TIMEOUT) as client:
        for model in models:
            payload = {
                'model': model,
                'messages': messages,
                'stream': False,
                'max_tokens': AI_MAX_OUTPUT_TOKENS,
            }
            if model != DEEPSEEK_REASONER_MODEL:
                payload['temperature'] = 0.2
            try:
                response = await client.post(
                    f'{DEEPSEEK_BASE_URL}/chat/completions',
                    headers={'Authorization': f'Bearer {DEEPSEEK_API_KEY}', 'Content-Type': 'application/json'},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                content = ((data.get('choices') or [{}])[0].get('message') or {}).get('content')
                if content and content.strip():
                    return content.strip(), model, None
            except Exception as exc:
                last_error = str(exc)
                continue
    return None, None, last_error or 'DeepSeek 未返回有效内容'


async def answer_village_question(db: Session, message: str, history: list[dict] | None = None, village_ref: str | None = None, deep_thinking: bool = True) -> dict:
    history = history or []
    conversation = conversation_reply(message)
    if conversation:
        answer, intent = conversation
        return {
            'answer': answer,
            'sources': [],
            'mode': 'conversation',
            'model': None,
            'web_search_used': False,
            'deep_thinking_used': False,
            'warning': None,
            'intent': intent,
        }
    if _is_plain_conversation(message):
        answer, model, error = await _deepseek_conversation(message, history)
        return {
            'answer': answer or _conversation_fallback(),
            'sources': [],
            'mode': 'conversation',
            'model': model,
            'web_search_used': False,
            'deep_thinking_used': False,
            'warning': None,
            'intent': 'small_talk',
        }
    context = ' '.join(str(item.get('content') or '') for item in history[-4:])
    local_sources = retrieve_archive(db, message, village_ref, context)
    if not local_sources and not _looks_like_village_query(message):
        answer, model, error = await _deepseek_conversation(message, history)
        return {
            'answer': answer or _conversation_fallback(),
            'sources': [],
            'mode': 'conversation',
            'model': model,
            'web_search_used': False,
            'deep_thinking_used': False,
            'warning': None,
            'intent': 'small_talk',
        }
    web_sources: list[RetrievedSource] = []
    warning = None
    if _should_search_web(message, local_sources):
        web_sources = await search_official_web(message)
        if not web_sources:
            warning = '未检索到可引用的政府、官方媒体或传统村落官方资料，因此仅依据本地档案回答。'

    sources = local_sources + web_sources
    sources = sources[:8]
    if not sources:
        return {
            'answer': '现有资料不足，暂时无法给出有可靠来源的答案。请尝试补充具体村落名称、历史时期、建筑类型或民俗项目。',
            'sources': [],
            'mode': 'no_reliable_source',
            'web_search_used': bool(web_sources),
            'deep_thinking_used': False,
            'warning': warning or '没有找到可引用的本地档案或正规公开网页。',
        }

    answer, model, error = await _deepseek_answer(message, history, sources, deep_thinking)
    if answer:
        mode = 'deepseek_reasoner' if model == DEEPSEEK_REASONER_MODEL else 'deepseek_chat'
        if web_sources:
            mode += '+web'
        return {
            'answer': answer,
            'sources': _public_sources(sources),
            'mode': mode,
            'model': model,
            'web_search_used': bool(web_sources),
            'deep_thinking_used': model == DEEPSEEK_REASONER_MODEL,
            'warning': warning,
        }

    fallback = _extractive_answer(message, sources)
    if error:
        warning = (warning + ' ' if warning else '') + '大模型服务暂时不可用，已切换为本地档案摘录。'
    return {
        'answer': fallback,
        'sources': _public_sources(sources),
        'mode': 'local_archive+web' if web_sources else 'local_archive',
        'model': None,
        'web_search_used': bool(web_sources),
        'deep_thinking_used': False,
        'warning': warning,
    }
