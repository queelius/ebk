"""Personal metadata management for ebk libraries."""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class PersonalMetadata:
    """Manage personal metadata like ratings, comments, and reading status."""
    
    def __init__(self, library_path: Path):
        """Initialize personal metadata manager."""
        self.library_path = Path(library_path)
        self.personal_file = self.library_path / "personal_metadata.json"
        self.data = self._load_data()
    
    def _load_data(self) -> Dict[str, Dict]:
        """Load personal metadata from file."""
        if self.personal_file.exists():
            try:
                with open(self.personal_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading personal metadata: {e}")
                return {}
        return {}
    
    def _save_data(self):
        """Save personal metadata to file."""
        try:
            with open(self.personal_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving personal metadata: {e}")
            raise
    
    def get_entry_metadata(self, entry_id: str) -> Dict[str, Any]:
        """Get all personal metadata for an entry."""
        return self.data.get(entry_id, {})
    
    def set_rating(self, entry_id: str, rating: float) -> None:
        """Set rating for an entry (0-5 stars)."""
        if not 0 <= rating <= 5:
            raise ValueError("Rating must be between 0 and 5")
        
        if entry_id not in self.data:
            self.data[entry_id] = {}
        
        self.data[entry_id]["rating"] = rating
        self.data[entry_id]["rating_date"] = datetime.now().isoformat()
        self._save_data()
    
    def add_comment(self, entry_id: str, comment: str) -> None:
        """Add a comment/note to an entry."""
        if entry_id not in self.data:
            self.data[entry_id] = {}
        
        if "comments" not in self.data[entry_id]:
            self.data[entry_id]["comments"] = []
        
        self.data[entry_id]["comments"].append({
            "text": comment,
            "date": datetime.now().isoformat()
        })
        self._save_data()
    
    def set_read_status(self, entry_id: str, status: str, 
                       progress: Optional[int] = None) -> None:
        """
        Set reading status for an entry.
        
        Status can be: 'unread', 'reading', 'read', 'abandoned'
        Progress is optional percentage (0-100)
        """
        valid_statuses = ['unread', 'reading', 'read', 'abandoned']
        if status not in valid_statuses:
            raise ValueError(f"Status must be one of: {', '.join(valid_statuses)}")
        
        if progress is not None and not 0 <= progress <= 100:
            raise ValueError("Progress must be between 0 and 100")
        
        if entry_id not in self.data:
            self.data[entry_id] = {}
        
        self.data[entry_id]["read_status"] = status
        self.data[entry_id]["status_date"] = datetime.now().isoformat()
        
        if progress is not None:
            self.data[entry_id]["progress"] = progress
        
        # Add to reading history
        if "reading_history" not in self.data[entry_id]:
            self.data[entry_id]["reading_history"] = []
        
        self.data[entry_id]["reading_history"].append({
            "status": status,
            "progress": progress,
            "date": datetime.now().isoformat()
        })
        
        self._save_data()
    
    def add_personal_tags(self, entry_id: str, tags: List[str]) -> None:
        """Add personal tags to an entry."""
        if entry_id not in self.data:
            self.data[entry_id] = {}
        
        if "personal_tags" not in self.data[entry_id]:
            self.data[entry_id]["personal_tags"] = []
        
        # Add new tags, avoiding duplicates
        existing_tags = set(self.data[entry_id]["personal_tags"])
        for tag in tags:
            if tag not in existing_tags:
                self.data[entry_id]["personal_tags"].append(tag)
        
        self._save_data()
    
    def remove_personal_tags(self, entry_id: str, tags: List[str]) -> None:
        """Remove personal tags from an entry."""
        if entry_id in self.data and "personal_tags" in self.data[entry_id]:
            self.data[entry_id]["personal_tags"] = [
                t for t in self.data[entry_id]["personal_tags"] 
                if t not in tags
            ]
            self._save_data()
    
    def set_favorite(self, entry_id: str, is_favorite: bool = True) -> None:
        """Mark an entry as favorite."""
        if entry_id not in self.data:
            self.data[entry_id] = {}
        
        self.data[entry_id]["is_favorite"] = is_favorite
        self.data[entry_id]["favorite_date"] = datetime.now().isoformat()
        self._save_data()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about personal metadata."""
        stats = {
            "total_rated": 0,
            "average_rating": 0.0,
            "total_read": 0,
            "total_reading": 0,
            "total_unread": 0,
            "total_abandoned": 0,
            "total_favorites": 0,
            "total_with_comments": 0,
            "total_with_tags": 0,
            "rating_distribution": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        }
        
        ratings = []
        
        for entry_id, metadata in self.data.items():
            if "rating" in metadata:
                stats["total_rated"] += 1
                rating = metadata["rating"]
                ratings.append(rating)
                # Round to nearest integer for distribution
                rounded = int(round(rating))
                if rounded in stats["rating_distribution"]:
                    stats["rating_distribution"][rounded] += 1
            
            if "read_status" in metadata:
                status = metadata["read_status"]
                if status == "read":
                    stats["total_read"] += 1
                elif status == "reading":
                    stats["total_reading"] += 1
                elif status == "unread":
                    stats["total_unread"] += 1
                elif status == "abandoned":
                    stats["total_abandoned"] += 1
            
            if metadata.get("is_favorite"):
                stats["total_favorites"] += 1
            
            if metadata.get("comments"):
                stats["total_with_comments"] += 1
            
            if metadata.get("personal_tags"):
                stats["total_with_tags"] += 1
        
        if ratings:
            stats["average_rating"] = sum(ratings) / len(ratings)
        
        return stats
    
    def search_by_personal_metadata(self, 
                                   min_rating: Optional[float] = None,
                                   read_status: Optional[str] = None,
                                   personal_tags: Optional[List[str]] = None,
                                   is_favorite: Optional[bool] = None) -> List[str]:
        """Search entries by personal metadata criteria."""
        matching_ids = []
        
        for entry_id, metadata in self.data.items():
            # Check rating
            if min_rating is not None:
                if metadata.get("rating", 0) < min_rating:
                    continue
            
            # Check read status
            if read_status is not None:
                if metadata.get("read_status") != read_status:
                    continue
            
            # Check personal tags
            if personal_tags is not None:
                entry_tags = set(metadata.get("personal_tags", []))
                if not all(tag in entry_tags for tag in personal_tags):
                    continue
            
            # Check favorite status
            if is_favorite is not None:
                if metadata.get("is_favorite", False) != is_favorite:
                    continue
            
            matching_ids.append(entry_id)
        
        return matching_ids
    
    def export_for_web(self) -> Dict[str, Dict]:
        """Export personal metadata in a format suitable for web display."""
        # Return a cleaned version without internal dates
        export_data = {}
        
        for entry_id, metadata in self.data.items():
            clean_metadata = {}
            
            # Include user-facing fields
            for field in ["rating", "read_status", "progress", "is_favorite", 
                         "personal_tags", "comments"]:
                if field in metadata:
                    if field == "comments":
                        # Include only comment text, not dates
                        clean_metadata[field] = [c["text"] for c in metadata[field]]
                    else:
                        clean_metadata[field] = metadata[field]
            
            if clean_metadata:
                export_data[entry_id] = clean_metadata
        
        return export_data