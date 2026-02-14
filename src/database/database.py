"""
Database manager for SQLite operations and initialization.
"""

import os
from pathlib import Path
from typing import Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
import structlog

from .models import Base, Research, Query, Source, create_database_engine, create_tables, get_session_factory

logger = structlog.get_logger()


class DatabaseManager:
    """Manages SQLite database connections and operations."""
    
    def __init__(self, database_url: Optional[str] = None, database_path: Optional[str] = None):
        """
        Initialize database manager.
        
        Args:
            database_url: Full SQLAlchemy database URL
            database_path: Path to SQLite database file (alternative to database_url)
        """
        if database_url:
            self.database_url = database_url
        elif database_path:
            self.database_url = f"sqlite:///{database_path}"
        else:
            # Default to local database in project directory
            default_path = Path("data/research_history.db").absolute()
            self.database_url = f"sqlite:///{default_path}"
        
        self.engine = None
        self.session_factory = None
        self.logger = logger.bind(database=self.database_url)
        
    def initialize(self) -> None:
        """Initialize database engine and create tables if needed."""
        try:
            self.engine = create_database_engine(self.database_url)
            self.session_factory = get_session_factory(self.engine)
            
            # Create tables if they don't exist
            create_tables(self.engine)
            
            self.logger.info("Database initialized successfully")
            
        except Exception as e:
            self.logger.error("Failed to initialize database", error=str(e))
            raise RuntimeError(f"Database initialization failed: {str(e)}") from e
    
    @contextmanager
    def get_session(self) -> Session:
        """Get database session with automatic cleanup."""
        if not self.session_factory:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            self.logger.error("Database session error", error=str(e))
            raise
        finally:
            session.close()
    
    def get_database_stats(self) -> dict:
        """Get basic database statistics."""
        try:
            with self.get_session() as session:
                research_count = session.query(Research).count()
                query_count = session.query(Query).count()
                source_count = session.query(Source).count()
                
                # Get completed research count
                completed_count = session.query(Research).filter(
                    Research.status == "completed"
                ).count()
                
                # Get average processing time
                avg_time = session.query(Research.processing_time).filter(
                    Research.processing_time.isnot(None)
                ).all()
                
                avg_processing_time = None
                if avg_time:
                    times = [t[0] for t in avg_time if t[0] is not None]
                    if times:
                        avg_processing_time = sum(times) / len(times)
                
                return {
                    "total_research_sessions": research_count,
                    "completed_sessions": completed_count,
                    "total_queries": query_count,
                    "total_sources": source_count,
                    "average_processing_time": avg_processing_time,
                    "database_url": self.database_url
                }
                
        except Exception as e:
            self.logger.error("Failed to get database stats", error=str(e))
            return {"error": str(e)}
    
    def cleanup_old_data(self, days_old: int = 30) -> int:
        """
        Clean up research data older than specified days.
        
        Args:
            days_old: Remove data older than this many days
            
        Returns:
            Number of research sessions deleted
        """
        try:
            from datetime import datetime, timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            with self.get_session() as session:
                # Find old research sessions
                old_research = session.query(Research).filter(
                    Research.started_at < cutoff_date
                ).all()
                
                count = len(old_research)
                
                # Delete old research (cascades to queries and sources)
                session.query(Research).filter(
                    Research.started_at < cutoff_date
                ).delete()
                
                self.logger.info("Cleaned up old research data", 
                               deleted_count=count, days_old=days_old)
                return count
                
        except Exception as e:
            self.logger.error("Failed to cleanup old data", error=str(e))
            raise
    
    def backup_database(self, backup_path: str) -> bool:
        """
        Create a backup of the SQLite database.
        
        Args:
            backup_path: Path where backup should be saved
            
        Returns:
            True if backup successful, False otherwise
        """
        try:
            if "sqlite" not in self.database_url.lower():
                self.logger.warning("Backup only supported for SQLite databases")
                return False
            
            # Extract database file path from URL
            db_path = self.database_url.replace("sqlite:///", "")
            
            if not os.path.exists(db_path):
                self.logger.error("Database file not found", path=db_path)
                return False
            
            # Copy database file
            import shutil
            shutil.copy2(db_path, backup_path)
            
            self.logger.info("Database backup created", 
                           source=db_path, backup=backup_path)
            return True
            
        except Exception as e:
            self.logger.error("Database backup failed", error=str(e))
            return False
    
    def migrate_database(self) -> bool:
        """
        Run database migrations (placeholder for future schema changes).
        
        Returns:
            True if migration successful, False otherwise
        """
        try:
            # For now, just ensure all tables exist
            if self.engine:
                create_tables(self.engine)
                self.logger.info("Database migration completed")
                return True
            else:
                self.logger.error("Database not initialized for migration")
                return False
                
        except Exception as e:
            self.logger.error("Database migration failed", error=str(e))
            return False