"""
Repository layer for data access abstraction.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_
from datetime import datetime, timedelta
import hashlib
import json

from forth_ai_underwriting.core.models import (
    Contact, ValidationRun, ValidationResult, Document, 
    UserFeedback, AuditLog, ValidationCache, SystemMetrics
)
from forth_ai_underwriting.core.schemas import ValidationResult as ValidationResultSchema


class BaseRepository:
    """Base repository with common CRUD operations."""
    
    def __init__(self, db: Session, model_class):
        self.db = db
        self.model_class = model_class
    
    def create(self, **kwargs):
        """Create a new record."""
        instance = self.model_class(**kwargs)
        self.db.add(instance)
        self.db.flush()
        return instance
    
    def get_by_id(self, id: str):
        """Get record by ID."""
        return self.db.query(self.model_class).filter(self.model_class.id == id).first()
    
    def get_all(self, limit: int = 100, offset: int = 0):
        """Get all records with pagination."""
        return self.db.query(self.model_class).offset(offset).limit(limit).all()
    
    def update(self, id: str, **kwargs):
        """Update a record."""
        instance = self.get_by_id(id)
        if instance:
            for key, value in kwargs.items():
                setattr(instance, key, value)
            self.db.flush()
        return instance
    
    def delete(self, id: str):
        """Delete a record."""
        instance = self.get_by_id(id)
        if instance:
            self.db.delete(instance)
            self.db.flush()
        return instance


class ContactRepository(BaseRepository):
    """Repository for Contact operations."""
    
    def __init__(self, db: Session):
        super().__init__(db, Contact)
    
    def get_by_contact_id(self, contact_id: str) -> Optional[Contact]:
        """Get contact by contact_id."""
        return self.db.query(Contact).filter(Contact.contact_id == contact_id).first()
    
    def create_or_update(self, contact_id: str, **data) -> Contact:
        """Create or update contact data."""
        contact = self.get_by_contact_id(contact_id)
        if contact:
            for key, value in data.items():
                setattr(contact, key, value)
            contact.updated_at = datetime.utcnow()
        else:
            contact = Contact(contact_id=contact_id, **data)
            self.db.add(contact)
        self.db.flush()
        return contact
    
    def search_contacts(self, query: str, limit: int = 50) -> List[Contact]:
        """Search contacts by name or email."""
        search_term = f"%{query}%"
        return self.db.query(Contact).filter(
            or_(
                Contact.first_name.ilike(search_term),
                Contact.last_name.ilike(search_term),
                Contact.email.ilike(search_term)
            )
        ).limit(limit).all()


class ValidationRunRepository(BaseRepository):
    """Repository for ValidationRun operations."""
    
    def __init__(self, db: Session):
        super().__init__(db, ValidationRun)
    
    def create_run(self, contact_id: str, triggered_by: str, user_id: str = None) -> ValidationRun:
        """Create a new validation run."""
        run = ValidationRun(
            contact_id=contact_id,
            status="in_progress",
            triggered_by=triggered_by,
            user_id=user_id
        )
        self.db.add(run)
        self.db.flush()
        return run
    
    def complete_run(self, run_id: str, results: List[ValidationResultSchema], processing_time_ms: int):
        """Complete a validation run with results."""
        run = self.get_by_id(run_id)
        if not run:
            return None
        
        # Calculate metrics
        total_checks = len(results)
        passed_checks = sum(1 for r in results if r.result == "Pass")
        success_rate = (passed_checks / total_checks) * 100 if total_checks > 0 else 0
        
        # Update run
        run.status = "completed"
        run.total_checks = total_checks
        run.passed_checks = passed_checks
        run.success_rate = success_rate
        run.processing_time_ms = processing_time_ms
        
        # Store individual results
        for result in results:
            validation_result = ValidationResult(
                validation_run_id=run_id,
                check_type=self._extract_check_type(result.title),
                title=result.title,
                result=result.result,
                reason=result.reason,
                confidence_score=result.confidence
            )
            self.db.add(validation_result)
        
        self.db.flush()
        return run
    
    def fail_run(self, run_id: str, error_message: str):
        """Mark a validation run as failed."""
        run = self.get_by_id(run_id)
        if run:
            run.status = "failed"
            run.reason = error_message
            self.db.flush()
        return run
    
    def get_recent_runs(self, contact_id: str, limit: int = 10) -> List[ValidationRun]:
        """Get recent validation runs for a contact."""
        return self.db.query(ValidationRun).filter(
            ValidationRun.contact_id == contact_id
        ).order_by(desc(ValidationRun.run_timestamp)).limit(limit).all()
    
    def get_run_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get validation run statistics for the last N days."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        total_runs = self.db.query(ValidationRun).filter(
            ValidationRun.run_timestamp >= cutoff_date
        ).count()
        
        successful_runs = self.db.query(ValidationRun).filter(
            and_(
                ValidationRun.run_timestamp >= cutoff_date,
                ValidationRun.status == "completed"
            )
        ).count()
        
        avg_success_rate = self.db.query(ValidationRun.success_rate).filter(
            and_(
                ValidationRun.run_timestamp >= cutoff_date,
                ValidationRun.status == "completed"
            )
        ).all()
        
        avg_success_rate = sum(r[0] for r in avg_success_rate if r[0]) / len(avg_success_rate) if avg_success_rate else 0
        
        return {
            "total_runs": total_runs,
            "successful_runs": successful_runs,
            "success_rate": (successful_runs / total_runs) * 100 if total_runs > 0 else 0,
            "avg_validation_success_rate": avg_success_rate
        }
    
    def _extract_check_type(self, title: str) -> str:
        """Extract check type from validation title."""
        if "hardship" in title.lower():
            return "hardship"
        elif "budget" in title.lower():
            return "budget"
        elif "contract" in title.lower():
            return "contract"
        elif "address" in title.lower():
            return "address"
        elif "draft" in title.lower():
            return "draft"
        else:
            return "other"


class DocumentRepository(BaseRepository):
    """Repository for Document operations."""
    
    def __init__(self, db: Session):
        super().__init__(db, Document)
    
    def create_document(self, contact_id: str, document_url: str, document_name: str, document_type: str = "agreement") -> Document:
        """Create a new document record."""
        document = Document(
            contact_id=contact_id,
            document_url=document_url,
            document_name=document_name,
            document_type=document_type,
            processing_status="pending"
        )
        self.db.add(document)
        self.db.flush()
        return document
    
    def update_processing_status(self, document_id: str, status: str, parsed_data: Dict[str, Any] = None):
        """Update document processing status."""
        document = self.get_by_id(document_id)
        if document:
            document.processing_status = status
            if parsed_data:
                document.parsed_data = parsed_data
            if status == "completed":
                document.processed = True
            self.db.flush()
        return document
    
    def get_pending_documents(self, limit: int = 50) -> List[Document]:
        """Get documents pending processing."""
        return self.db.query(Document).filter(
            Document.processing_status == "pending"
        ).limit(limit).all()


class UserFeedbackRepository(BaseRepository):
    """Repository for UserFeedback operations."""
    
    def __init__(self, db: Session):
        super().__init__(db, UserFeedback)
    
    def create_feedback(self, contact_id: str, user_id: str, rating: int, feedback_text: str, validation_run_id: str = None, conversation_id: str = None) -> UserFeedback:
        """Create user feedback."""
        feedback = UserFeedback(
            contact_id=contact_id,
            user_id=user_id,
            rating=rating,
            feedback_text=feedback_text,
            validation_run_id=validation_run_id,
            conversation_id=conversation_id
        )
        self.db.add(feedback)
        self.db.flush()
        return feedback
    
    def get_feedback_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get feedback statistics."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        feedbacks = self.db.query(UserFeedback).filter(
            UserFeedback.feedback_timestamp >= cutoff_date
        ).all()
        
        if not feedbacks:
            return {"total_feedback": 0, "average_rating": 0, "rating_distribution": {}}
        
        total_feedback = len(feedbacks)
        average_rating = sum(f.rating for f in feedbacks) / total_feedback
        rating_distribution = {}
        
        for i in range(1, 6):
            rating_distribution[i] = sum(1 for f in feedbacks if f.rating == i)
        
        return {
            "total_feedback": total_feedback,
            "average_rating": average_rating,
            "rating_distribution": rating_distribution
        }


class ValidationCacheRepository(BaseRepository):
    """Repository for ValidationCache operations."""
    
    def __init__(self, db: Session):
        super().__init__(db, ValidationCache)
    
    def get_cached_results(self, contact_id: str, data_hash: str) -> Optional[ValidationCache]:
        """Get cached validation results."""
        cache_key = self._generate_cache_key(contact_id, data_hash)
        
        cached = self.db.query(ValidationCache).filter(
            and_(
                ValidationCache.cache_key == cache_key,
                ValidationCache.expires_at > datetime.utcnow()
            )
        ).first()
        
        if cached:
            # Update access statistics
            cached.hit_count += 1
            cached.last_accessed = datetime.utcnow()
            self.db.flush()
        
        return cached
    
    def cache_results(self, contact_id: str, data_hash: str, results: List[ValidationResultSchema], ttl_hours: int = 24) -> ValidationCache:
        """Cache validation results."""
        cache_key = self._generate_cache_key(contact_id, data_hash)
        expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
        
        # Convert results to JSON-serializable format
        cached_results = [
            {
                "title": r.title,
                "result": r.result,
                "reason": r.reason,
                "confidence": r.confidence
            }
            for r in results
        ]
        
        cache = ValidationCache(
            cache_key=cache_key,
            contact_id=contact_id,
            data_hash=data_hash,
            cached_results=cached_results,
            expires_at=expires_at
        )
        self.db.add(cache)
        self.db.flush()
        return cache
    
    def invalidate_cache(self, contact_id: str):
        """Invalidate all cache entries for a contact."""
        self.db.query(ValidationCache).filter(
            ValidationCache.contact_id == contact_id
        ).delete()
        self.db.flush()
    
    def cleanup_expired_cache(self):
        """Remove expired cache entries."""
        self.db.query(ValidationCache).filter(
            ValidationCache.expires_at <= datetime.utcnow()
        ).delete()
        self.db.flush()
    
    def _generate_cache_key(self, contact_id: str, data_hash: str) -> str:
        """Generate cache key."""
        return f"validation_{contact_id}_{data_hash}"


class AuditLogRepository(BaseRepository):
    """Repository for AuditLog operations."""
    
    def __init__(self, db: Session):
        super().__init__(db, AuditLog)
    
    def log_action(self, action: str, entity_type: str, entity_id: str, user_id: str = None, details: Dict[str, Any] = None, ip_address: str = None, user_agent: str = None):
        """Log an audit action."""
        audit = AuditLog(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            user_id=user_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent
        )
        self.db.add(audit)
        self.db.flush()
        return audit


def generate_data_hash(data: Dict[str, Any]) -> str:
    """Generate a hash for data to use in caching."""
    data_str = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(data_str.encode()).hexdigest() 