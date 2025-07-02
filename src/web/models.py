"""
Flask-SQLAlchemy models for research history and analytics.
"""

from datetime import datetime
from typing import List, Optional
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

# db will be set by app.py
db = None


class Research(db.Model):
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
        """Convert research object to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'topic': self.topic,
            'focus_areas': self.focus_areas,
            'agent_name': self.agent_name,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'processing_time': self.processing_time,
            'status': self.status,
            'executive_summary': self.executive_summary,
            'key_findings': self.key_findings,
            'detailed_analysis': self.detailed_analysis,
            'total_queries': self.total_queries,
            'total_sources': self.total_sources,
            'original_language': self.original_language,
            'research_language': self.research_language,
            'translation_enabled': self.translation_enabled,
            'translated_languages': self.translated_languages
        }


class Query(db.Model):
    """Individual search queries made during research."""
    
    __tablename__ = "queries"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    research_id = Column(Integer, ForeignKey('research.id'), nullable=False, index=True)
    query_text = Column(Text, nullable=False)
    query_language = Column(String(10), default='en')
    query_order = Column(Integer)  # Order of query in research sequence
    executed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Query execution details
    processing_time = Column(Float)  # Seconds
    results_count = Column(Integer, default=0)
    success = Column(Boolean, default=True)
    error_message = Column(Text)
    search_provider = Column(String(50))  # e.g., 'tavily', 'google'
    
    # Query metadata
    query_metadata = Column(JSON)
    
    # Relationships
    research = relationship("Research", back_populates="queries")
    
    def __repr__(self):
        return f"<Query(id={self.id}, research_id={self.research_id}, query='{self.query_text[:50]}...')>"


class Source(db.Model):
    """Sources found and used during research."""
    
    __tablename__ = "sources"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    research_id = Column(Integer, ForeignKey('research.id'), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    url = Column(Text, nullable=False)
    content_snippet = Column(Text)
    relevance_score = Column(Float)
    
    # Source metadata
    domain = Column(String(200))
    published_date = Column(DateTime)
    content_type = Column(String(50))  # article, pdf, etc.
    language = Column(String(10))
    credibility_score = Column(Float)
    
    # Discovery metadata
    discovered_via_query = Column(String(500))  # Which query found this source
    position_in_results = Column(Integer)  # Position in search results
    accessed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Source analysis
    content_length = Column(Integer)
    key_quotes = Column(JSON)  # Important quotes extracted from source
    topics_covered = Column(JSON)  # Topics/themes this source addresses
    
    # Relationships
    research = relationship("Research", back_populates="sources")
    
    def __repr__(self):
        return f"<Source(id={self.id}, title='{self.title}', url='{self.url}')>"


class Translation(db.Model):
    """Translation records for multi-language research results."""
    
    __tablename__ = "translations"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    research_id = Column(Integer, ForeignKey('research.id'), nullable=False, index=True)
    target_language = Column(String(10), nullable=False, index=True)
    source_language = Column(String(10), default='en')
    
    # Translation content
    translated_summary = Column(Text)
    translated_findings = Column(JSON)  # List of translated findings
    translated_analysis = Column(Text)
    translation_quality_score = Column(Float)
    
    # Translation metadata
    translation_provider = Column(String(50))  # google, deepl, etc.
    translated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processing_time = Column(Float)  # Seconds
    character_count = Column(Integer)
    confidence_score = Column(Float)
    
    # Translation file paths
    translated_report_path = Column(String(500))
    
    # Relationships
    research = relationship("Research", back_populates="translations")
    
    def __repr__(self):
        return f"<Translation(id={self.id}, research_id={self.research_id}, target_language='{self.target_language}')>"