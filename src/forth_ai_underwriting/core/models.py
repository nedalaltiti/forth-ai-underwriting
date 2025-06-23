"""
Database models for the Forth AI Underwriting System.
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Boolean, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from typing import Optional
import uuid

Base = declarative_base()


class Contact(Base):
    """Contact information from Forth CRM."""
    __tablename__ = "contacts"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    contact_id = Column(String, unique=True, nullable=False, index=True)
    first_name = Column(String(100))
    last_name = Column(String(100))
    email = Column(String(255))
    phone = Column(String(20))
    address_data = Column(JSON)  # Store full address as JSON
    enrollment_date = Column(DateTime)
    first_draft_date = Column(DateTime)
    affiliate = Column(String(100))
    assigned_company = Column(String(100))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    validation_runs = relationship("ValidationRun", back_populates="contact")
    documents = relationship("Document", back_populates="contact")


class ValidationRun(Base):
    """Validation run results for a contact."""
    __tablename__ = "validation_runs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    contact_id = Column(String, ForeignKey("contacts.contact_id"), nullable=False, index=True)
    run_timestamp = Column(DateTime, default=func.now(), nullable=False)
    status = Column(String(20), nullable=False)  # "completed", "failed", "in_progress"
    total_checks = Column(Integer, default=0)
    passed_checks = Column(Integer, default=0)
    success_rate = Column(Float)
    processing_time_ms = Column(Integer)
    triggered_by = Column(String(50))  # "webhook", "teams_bot", "manual"
    user_id = Column(String(100))  # Teams user who triggered
    
    # Relationships
    contact = relationship("Contact", back_populates="validation_runs")
    validation_results = relationship("ValidationResult", back_populates="validation_run")


class ValidationResult(Base):
    """Individual validation check results."""
    __tablename__ = "validation_results"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    validation_run_id = Column(String, ForeignKey("validation_runs.id"), nullable=False, index=True)
    check_type = Column(String(50), nullable=False)  # "hardship", "budget", "contract", etc.
    title = Column(String(200), nullable=False)
    result = Column(String(20), nullable=False)  # "Pass", "No Pass"
    reason = Column(Text)
    confidence_score = Column(Float)
    execution_time_ms = Column(Integer)
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    validation_run = relationship("ValidationRun", back_populates="validation_results")


class Document(Base):
    """Contract documents and metadata."""
    __tablename__ = "documents"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    contact_id = Column(String, ForeignKey("contacts.contact_id"), nullable=False, index=True)
    document_url = Column(String(500), nullable=False)
    document_name = Column(String(255))
    document_type = Column(String(50))  # "agreement", "contract", etc.
    file_size = Column(Integer)
    mime_type = Column(String(100))
    upload_timestamp = Column(DateTime, default=func.now())
    processed = Column(Boolean, default=False)
    processing_status = Column(String(20))  # "pending", "processing", "completed", "failed"
    parsed_data = Column(JSON)  # Store AI-parsed data
    
    # Relationships
    contact = relationship("Contact", back_populates="documents")


class UserFeedback(Base):
    """User feedback from Teams bot interactions."""
    __tablename__ = "user_feedback"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    contact_id = Column(String, nullable=False, index=True)
    validation_run_id = Column(String, ForeignKey("validation_runs.id"), index=True)
    user_id = Column(String(100), nullable=False)
    conversation_id = Column(String(100))
    rating = Column(Integer, nullable=False)  # 1-5 stars
    feedback_text = Column(Text)
    feedback_timestamp = Column(DateTime, default=func.now())
    
    # Relationships
    validation_run = relationship("ValidationRun")


class AuditLog(Base):
    """Audit trail for all system actions."""
    __tablename__ = "audit_logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    action = Column(String(100), nullable=False)
    entity_type = Column(String(50))  # "contact", "validation", "document"
    entity_id = Column(String(100))
    user_id = Column(String(100))
    timestamp = Column(DateTime, default=func.now())
    details = Column(JSON)
    ip_address = Column(String(45))
    user_agent = Column(String(500))


class ValidationCache(Base):
    """Cache for validation results to improve performance."""
    __tablename__ = "validation_cache"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    cache_key = Column(String(255), unique=True, nullable=False, index=True)
    contact_id = Column(String, nullable=False, index=True)
    data_hash = Column(String(64))  # Hash of input data for cache invalidation
    cached_results = Column(JSON)
    created_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime)
    hit_count = Column(Integer, default=0)
    last_accessed = Column(DateTime, default=func.now())


class SystemMetrics(Base):
    """System performance and usage metrics."""
    __tablename__ = "system_metrics"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    metric_name = Column(String(100), nullable=False)
    metric_value = Column(Float)
    metric_type = Column(String(20))  # "counter", "gauge", "histogram"
    labels = Column(JSON)  # Additional metric labels
    timestamp = Column(DateTime, default=func.now()) 