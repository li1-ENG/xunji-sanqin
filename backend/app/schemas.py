from typing import Literal
import re

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

class LoginRequest(BaseModel):
    account: str = Field(validation_alias=AliasChoices('account', 'email'), min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=256)

class CityInput(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    slug: str = Field(min_length=1, max_length=40)
    code: str = Field(min_length=1, max_length=10)
    sort_order: int = 0

class VillageInput(BaseModel):
    source_id: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=1, max_length=80)
    city_id: int
    location: str = ''
    summary: str = ''
    cover_image: str = ''
    description_html: str = ''
    description_text: str = ''
    attributes_json: dict = Field(default_factory=dict)
    status: str = 'draft'
    sort_order: int = 0
    source_url: str = ''
    source_site: str = ''

class VillageStatusInput(BaseModel):
    status: str

class SectionInput(BaseModel):
    type: str = Field(min_length=1, max_length=40)
    title: str = ''
    content_html: str = ''
    content_text: str = ''
    images_json: list = Field(default_factory=list)
    sort_order: int = 0
    source_file: str = ''
    source_url: str = ''

class FigureInput(BaseModel):
    name: str = ''
    content_html: str = ''
    content_text: str = ''
    sort_order: int = 0
    source_url: str = ''

class HistoricElementInput(BaseModel):
    name: str = ''
    code: str = ''
    images_json: list = Field(default_factory=list)
    sort_order: int = 0
    source_url: str = ''

class MediaInput(BaseModel):
    url: str = Field(min_length=1)
    media_type: str = 'image'
    title: str = ''
    source_file: str = ''
    source_url: str = ''
    sort_order: int = 0

class ReorderInput(BaseModel):
    ids: list[int]

class FeedbackCreate(BaseModel):
    name: str = Field(default='', max_length=80)
    email: str = Field(default='', max_length=255)
    category: Literal['village_supplement', 'correction', 'suggestion'] = 'village_supplement'
    village_name: str = Field(default='', max_length=120)
    city: str = Field(default='', max_length=40)
    message: str = Field(min_length=2, max_length=5000)
    website: str = Field(default='', max_length=200)

    @field_validator('name', 'village_name', 'city', 'message', mode='before')
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator('email')
    @classmethod
    def validate_contact_email(cls, value: str) -> str:
        value = (value or '').strip()
        if not value:
            return ''
        if len(value) > 255 or not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', value):
            raise ValueError('联系邮箱格式不正确')
        return value

class FeedbackUpdate(BaseModel):
    status: str

class AdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    display_name: str



class AIChatHistoryItem(BaseModel):
    role: Literal['user', 'assistant']
    content: str = Field(min_length=1, max_length=4000)


class AIChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    history: list[AIChatHistoryItem] = Field(default_factory=list, max_length=8)
    deep_thinking: bool = True
    village_ref: str | None = Field(default=None, max_length=80)
