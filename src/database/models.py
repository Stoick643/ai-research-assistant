"""
SQLAlchemy models for research history and analytics.
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import create_engine, Column, Integer, String, Text, Float, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.sql import func
import structlog

logger = structlog.get_logger()

Base = declarative_base()


class Research(Base):
    """Research session model storing complete research workflows."""
    
    __tablename__ = "research"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    topic = Column(String(500), nullable=False, index=True)
    focus_areas = Column(JSON)  # List of focus area strings
    agent_name = Column(String(100), nullable=False)
    
    # Research execution details
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    completed_at = Column(DateTime)
    processing_time = Column(Float)  # Seconds
    status = Column(String(20), default="in_progress", index=True)  # in_progress, completed, failed
    
    # Research results
    executive_summary = Column(Text)
    key_findings = Column(JSON)  # List of key finding strings
    detailed_analysis = Column(Text)
    report_content = Column(Text)
    report_path = Column(String(500))
    
    # Metadata
    total_queries = Column(Integer, default=0)
    total_sources = Column(Integer, default=0)
    error_message = Column(Text)
    research_metadata = Column(JSON)  # Additional metadata dictionary
    
    # Translation metadata
    original_language = Column(String(10), index=True)  # Language of original topic/query
    research_language = Column(String(10), default='en', index=True)  # Language research was conducted in
    translation_enabled = Column(Boolean, default=False)
    translated_languages = Column(JSON)  # List of languages results were translated to
    
    # Relationships
    queries = relationship("Query", back_populates="research", cascade="all, delete-orphan")
    sources = relationship("Source", back_populates="research", cascade="all, delete-orphan")
    translations = relationship("Translation", back_populates="research", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Research(id={self.id}, topic='{self.topic}', status='{self.status}')>"
    
    def to_dict(self):
        """Convert research record to dictionary."""
        return {
            "id": self.id,
            "topic": self.topic,
            "focus_areas": self.focus_areas,
            "agent_name": self.agent_name,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "processing_time": self.processing_time,
            "status": self.status,
            "executive_summary": self.executive_summary,
            "key_findings": self.key_findings,
            "detailed_analysis": self.detailed_analysis,
            "report_content": self.report_content,
            "report_path": self.report_path,
            "total_queries": self.total_queries,
            "total_sources": self.total_sources,
            "error_message": self.error_message,
            "research_metadata": self.research_metadata,
            "original_language": self.original_language,
            "research_language": self.research_language,
            "translation_enabled": self.translation_enabled,
            "translated_languages": self.translated_languages
        }


class Query(Base):
    """Individual search query model within a research session."""
    
    __tablename__ = "queries"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    research_id = Column(Integer, ForeignKey("research.id"), nullable=False, index=True)
    
    # Query details
    query_text = Column(String(1000), nullable=False, index=True)
    query_order = Column(Integer, nullable=False)  # Order within the research session
    executed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Search parameters
    max_results = Column(Integer, default=5)
    search_depth = Column(String(20), default="basic")
    include_answer = Column(Boolean, default=True)
    
    # Results
    results_count = Column(Integer, default=0)
    ai_answer = Column(Text)  # Tavily's AI-generated answer
    follow_up_questions = Column(JSON)  # List of follow-up question strings
    search_context = Column(Text)
    execution_time = Column(Float)  # Seconds
    success = Column(Boolean, default=True)
    error_message = Column(Text)
    
    # Relationships
    research = relationship("Research", back_populates="queries")
    sources = relationship("Source", back_populates="query", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Query(id={self.id}, query_text='{self.query_text[:50]}...', success={self.success})>"
    
    def to_dict(self):
        """Convert query record to dictionary."""
        return {
            "id": self.id,
            "research_id": self.research_id,
            "query_text": self.query_text,
            "query_order": self.query_order,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "max_results": self.max_results,
            "search_depth": self.search_depth,
            "include_answer": self.include_answer,
            "results_count": self.results_count,
            "ai_answer": self.ai_answer,
            "follow_up_questions": self.follow_up_questions,
            "search_context": self.search_context,
            "execution_time": self.execution_time,
            "success": self.success,
            "error_message": self.error_message
        }


class Source(Base):
    """Individual source/result model from search queries."""
    
    __tablename__ = "sources"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    research_id = Column(Integer, ForeignKey("research.id"), nullable=False, index=True)
    query_id = Column(Integer, ForeignKey("queries.id"), nullable=False, index=True)
    
    # Source details
    title = Column(String(1000), nullable=False)
    url = Column(String(2000), nullable=False, index=True)
    content = Column(Text)
    relevance_score = Column(Float, index=True)
    published_date = Column(String(20))  # Store as string from API
    
    # Processing metadata
    retrieved_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    content_length = Column(Integer)
    domain = Column(String(200), index=True)  # Extracted from URL
    used_in_analysis = Column(Boolean, default=False, index=True)
    
    # Relationships
    research = relationship("Research", back_populates="sources")
    query = relationship("Query", back_populates="sources")
    
    def __repr__(self):
        return f"<Source(id={self.id}, title='{self.title[:50]}...', score={self.relevance_score})>"
    
    def to_dict(self):
        """Convert source record to dictionary."""
        return {
            "id": self.id,
            "research_id": self.research_id,
            "query_id": self.query_id,
            "title": self.title,
            "url": self.url,
            "content": self.content,
            "relevance_score": self.relevance_score,
            "published_date": self.published_date,
            "retrieved_at": self.retrieved_at.isoformat() if self.retrieved_at else None,
            "content_length": self.content_length,
            "domain": self.domain,
            "used_in_analysis": self.used_in_analysis
        }
    
    def extract_domain(self):
        """Extract domain from URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(self.url)
            self.domain = parsed.netloc.lower()
        except Exception:
            self.domain = "unknown"


class Translation(Base):
    """Translation tracking model for research content."""
    
    __tablename__ = "translations"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    research_id = Column(Integer, ForeignKey("research.id"), nullable=False, index=True)
    
    # Translation details
    source_text = Column(Text, nullable=False)
    translated_text = Column(Text, nullable=False)
    source_language = Column(String(10), nullable=False, index=True)
    target_language = Column(String(10), nullable=False, index=True)
    
    # Translation metadata
    content_type = Column(String(50), nullable=False, index=True)  # topic, summary, analysis, finding
    provider = Column(String(50), nullable=False)
    confidence_score = Column(Float)
    character_count = Column(Integer)
    processing_time = Column(Float)  # Seconds
    
    # Tracking
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    cache_hit = Column(Boolean, default=False)
    
    # Relationships
    research = relationship("Research", back_populates="translations")
    
    def __repr__(self):
        return f"<Translation(id={self.id}, {self.source_language}->{self.target_language}, type='{self.content_type}')>"
    
    def to_dict(self):
        """Convert translation record to dictionary."""
        return {
            "id": self.id,
            "research_id": self.research_id,
            "source_text": self.source_text,
            "translated_text": self.translated_text,
            "source_language": self.source_language,
            "target_language": self.target_language,
            "content_type": self.content_type,
            "provider": self.provider,
            "confidence_score": self.confidence_score,
            "character_count": self.character_count,
            "processing_time": self.processing_time,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "cache_hit": self.cache_hit
        }


# Database utility functions

def create_database_engine(database_url: str):
    """Create SQLAlchemy engine with appropriate settings."""
    engine = create_engine(
        database_url,
        echo=False,  # Set to True for SQL debugging
        pool_pre_ping=True,
        pool_recycle=300
    )
    return engine


def create_tables(engine):
    """Create all tables in the database (skips existing tables)."""
    try:
        Base.metadata.create_all(engine, checkfirst=True)
        logger.info("Database tables created successfully")
    except Exception as e:
        # On persistent volumes, tables may already exist from a previous deploy.
        # Log and continue — the tables are there, just not freshly created.
        if "already exists" in str(e):
            logger.warning("Tables already exist, continuing", error=str(e))
        else:
            logger.error("Failed to create database tables", error=str(e))
            raise


def get_session_factory(engine):
    """Create session factory for database operations."""
    return sessionmaker(bind=engine)