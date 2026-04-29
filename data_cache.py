import os
import json
import hashlib
import pickle
from datetime import datetime
import pandas as pd

class DataCache:
    """Manages caching of processed data to improve loading times"""
    
    def __init__(self, cache_dir=None):
        # Use default cache directory if none provided
        if cache_dir is None:
            home_dir = os.path.expanduser("~")
            cache_dir = os.path.join(home_dir, '.csv_plotter_cache')
        
        self.cache_dir = cache_dir
        # Create cache directory if it doesn't exist
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
            
        # Create a metadata file to track cache entries
        self.metadata_path = os.path.join(self.cache_dir, 'metadata.json')
        if not os.path.exists(self.metadata_path):
            self._save_metadata({})
    
    def _file_hash(self, file_path):
        """Generate a hash based on file path and modification time"""
        stat = os.stat(file_path)
        # Combine file path and modification time for the hash
        hash_input = f"{file_path}_{stat.st_mtime}_{stat.st_size}"
        return hashlib.md5(hash_input.encode()).hexdigest()
    
    def _load_metadata(self):
        """Load cache metadata"""
        try:
            with open(self.metadata_path, 'r') as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError):
            return {}
    
    def _save_metadata(self, metadata):
        """Save cache metadata"""
        with open(self.metadata_path, 'w') as f:
            json.dump(metadata, f)
    
    def get_cached_data(self, file_path):
        """Retrieve cached data if available and valid"""
        file_hash = self._file_hash(file_path)
        metadata = self._load_metadata()
        
        # Check if file is in cache and the hash matches
        if file_path in metadata and metadata[file_path]['hash'] == file_hash:
            cache_path = os.path.join(self.cache_dir, metadata[file_path]['cache_file'])
            try:
                with open(cache_path, 'rb') as f:
                    return pickle.load(f)
            except (IOError, pickle.PickleError):
                # If there's an error loading the cache, remove the entry
                self._remove_cache_entry(file_path)
        
        return None
    
    def cache_data(self, file_path, data):
        """Cache processed data"""
        file_hash = self._file_hash(file_path)
        cache_filename = f"{os.path.basename(file_path)}_{file_hash}.cache"
        cache_path = os.path.join(self.cache_dir, cache_filename)
        
        # Save data to cache
        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(data, f)
                
            # Update metadata
            metadata = self._load_metadata()
            metadata[file_path] = {
                'hash': file_hash,
                'cache_file': cache_filename,
                'timestamp': datetime.now().isoformat()
            }
            self._save_metadata(metadata)
            return True
        except (IOError, pickle.PickleError):
            return False
    
    def _remove_cache_entry(self, file_path):
        """Remove a file from cache"""
        metadata = self._load_metadata()
        if file_path in metadata:
            cache_path = os.path.join(self.cache_dir, metadata[file_path]['cache_file'])
            try:
                os.remove(cache_path)
            except OSError:
                pass  # File already doesn't exist
            del metadata[file_path]
            self._save_metadata(metadata)
    
    def clear_cache(self):
        """Clear all cached data"""
        metadata = self._load_metadata()
        for file_path in metadata:
            cache_path = os.path.join(self.cache_dir, metadata[file_path]['cache_file'])
            try:
                os.remove(cache_path)
            except OSError:
                pass  # File doesn't exist
        
        self._save_metadata({})
        
    def clean_old_entries(self, days=30):
        """Remove cache entries older than specified days"""
        metadata = self._load_metadata()
        current_time = datetime.now()
        files_to_remove = []
        
        for file_path, info in metadata.items():
            try:
                cache_time = datetime.fromisoformat(info['timestamp'])
                days_old = (current_time - cache_time).days
                if days_old > days:
                    files_to_remove.append(file_path)
            except (ValueError, KeyError):
                # If timestamp is invalid, mark for removal
                files_to_remove.append(file_path)
        
        for file_path in files_to_remove:
            self._remove_cache_entry(file_path)