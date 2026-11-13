from datetime import datetime, timezone
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

class City(Base, TimestampMixin):
    __tablename__ = 'cities'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    code: Mapped[str] = mapped_column(String(10), unique=True, index=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    villages: Mapped[list['Village']] = relationship(back_populates='city')

class Village(Base, TimestampMixin):
    __tablename__ = 'villages'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    city_id: Mapped[int] = mapped_column(ForeignKey('cities.id'), index=True, nullable=False)
    location: Mapped[str] = mapped_column(String(255), default='', nullable=False)
    summary: Mapped[str] = mapped_column(Text, default='', nullable=False)
    cover_image: Mapped[str] = mapped_column(Text, default='', nullable=False)
    description_html: Mapped[str] = mapped_column(Text, default='', nullable=False)
    description_text: Mapped[str] = mapped_column(Text, default='', nullable=False)
    attributes_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default='draft', index=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, default='', nullable=False)
    source_site: Mapped[str] = mapped_column(Text, default='', nullable=False)
    city: Mapped[City] = relationship(back_populates='villages')
    sections: Mapped[list['VillageSection']] = relationship(back_populates='village', cascade='all, delete-orphan', order_by='VillageSection.sort_order')
    figures: Mapped[list['VillageFigure']] = relationship(back_populates='village', cascade='all, delete-orphan', order_by='VillageFigure.sort_order')
    historic_elements: Mapped[list['HistoricElement']] = relationship(back_populates='village', cascade='all, delete-orphan', order_by='HistoricElement.sort_order')
    media: Mapped[list['MediaItem']] = relationship(back_populates='village', cascade='all, delete-orphan', order_by='MediaItem.sort_order')

class VillageSection(Base, TimestampMixin):
    __tablename__ = 'village_sections'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    village_id: Mapped[int] = mapped_column(ForeignKey('villages.id', ondelete='CASCADE'), index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(120), default='', nullable=False)
    content_html: Mapped[str] = mapped_column(Text, default='', nullable=False)
    content_text: Mapped[str] = mapped_column(Text, default='', nullable=False)
    images_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source_file: Mapped[str] = mapped_column(String(80), default='', nullable=False)
    source_url: Mapped[str] = mapped_column(Text, default='', nullable=False)
    village: Mapped[Village] = relationship(back_populates='sections')

class VillageFigure(Base, TimestampMixin):
    __tablename__ = 'village_figures'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    village_id: Mapped[int] = mapped_column(ForeignKey('villages.id', ondelete='CASCADE'), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), default='', nullable=False)
    content_html: Mapped[str] = mapped_column(Text, default='', nullable=False)
    content_text: Mapped[str] = mapped_column(Text, default='', nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, default='', nullable=False)
    village: Mapped[Village] = relationship(back_populates='figures')

class HistoricElement(Base, TimestampMixin):
    __tablename__ = 'historic_elements'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    village_id: Mapped[int] = mapped_column(ForeignKey('villages.id', ondelete='CASCADE'), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), default='', nullable=False)
    code: Mapped[str] = mapped_column(String(40), default='', nullable=False)
    images_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, default='', nullable=False)
    village: Mapped[Village] = relationship(back_populates='historic_elements')

class MediaItem(Base, TimestampMixin):
    __tablename__ = 'media_items'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    village_id: Mapped[int] = mapped_column(ForeignKey('villages.id', ondelete='CASCADE'), index=True, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    media_type: Mapped[str] = mapped_column(String(20), default='image', index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), default='', nullable=False)
    source_file: Mapped[str] = mapped_column(String(80), default='', nullable=False)
    source_url: Mapped[str] = mapped_column(Text, default='', nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    village: Mapped[Village] = relationship(back_populates='media')

class Feedback(Base, TimestampMixin):
    __tablename__ = 'feedback'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), default='', nullable=False)
    email: Mapped[str] = mapped_column(String(255), default='', nullable=False)
    category: Mapped[str] = mapped_column(String(40), default='village_supplement', index=True, nullable=False)
    village_name: Mapped[str] = mapped_column(String(120), default='', nullable=False)
    city: Mapped[str] = mapped_column(String(40), default='', nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default='new', index=True, nullable=False)

class AdminUser(Base):
    __tablename__ = 'admin_users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), default='Administrator', nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

class AdminSession(Base):
    __tablename__ = 'admin_sessions'
    __table_args__ = (UniqueConstraint('token_hash', name='uq_admin_session_token'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey('admin_users.id', ondelete='CASCADE'), index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    user: Mapped[AdminUser] = relationship()

