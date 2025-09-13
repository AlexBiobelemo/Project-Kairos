"""
Database Layer
Provides connection pooling, data validation, and optimized operations.
"""

import sqlite3
import threading
import logging
import json
import gzip
from typing import Any, Dict, List, Optional, Tuple, Union
from datetime import datetime, timedelta
from contextlib import contextmanager
from queue import Queue, Empty
from dataclasses import dataclass, asdict
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    pd = None

from config import config


class DataValidator:
    """Data validation utility class"""
    
    @staticmethod
    def validate_weather_data(data: dict) -> Tuple[bool, List[str]]:
        """Validate weather data dictionary"""
        errors = []
        
        required_fields = ['location', 'temperature', 'humidity']
        for field in required_fields:
            if field not in data or data[field] is None:
                errors.append(f"Missing required field: {field}")
        
        # Validate location
        if 'location' in data and not isinstance(data['location'], str):
            errors.append("Location must be a string")
        
        # Validate temperature
        if 'temperature' in data:
            try:
                temp = float(data['temperature'])
                if not -100 <= temp <= 100:
                    errors.append("Temperature out of range (-100 to 100°C)")
            except (ValueError, TypeError):
                errors.append("Temperature must be numeric")
        
        # Validate humidity
        if 'humidity' in data:
            try:
                humidity = float(data['humidity'])
                if not 0 <= humidity <= 100:
                    errors.append("Humidity out of range (0 to 100%)")
            except (ValueError, TypeError):
                errors.append("Humidity must be numeric")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_earthquake_data(data: dict) -> Tuple[bool, List[str]]:
        """Validate earthquake data dictionary"""
        errors = []
        
        required_fields = ['place', 'magnitude', 'lat', 'lon']
        for field in required_fields:
            if field not in data or data[field] is None:
                errors.append(f"Missing required field: {field}")
        
        # Validate magnitude
        if 'magnitude' in data:
            try:
                mag = float(data['magnitude'])
                if not 0 <= mag <= 15:
                    errors.append("Magnitude out of range (0 to 15)")
            except (ValueError, TypeError):
                errors.append("Magnitude must be numeric")
        
        # Validate coordinates
        if 'lat' in data:
            try:
                lat = float(data['lat'])
                if not -90 <= lat <= 90:
                    errors.append("Latitude out of range (-90 to 90)")
            except (ValueError, TypeError):
                errors.append("Latitude must be numeric")
        
        if 'lon' in data:
            try:
                lon = float(data['lon'])
                if not -180 <= lon <= 180:
                    errors.append("Longitude out of range (-180 to 180)")
            except (ValueError, TypeError):
                errors.append("Longitude must be numeric")
        
        return len(errors) == 0, errors


class DataQualityMonitor:
    """Monitor data quality and track issues"""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.DataQualityMonitor")
        self.quality_stats = {
            'total_records': 0,
            'valid_records': 0,
            'invalid_records': 0,
            'quality_score': 1.0
        }
    
    def check_data_quality(self, data_type: str, records: List[dict]) -> Dict[str, Any]:
        """Check quality of data records"""
        if not records:
            return {'quality_score': 0.0, 'issues': ['No data provided']}
        
        validator = DataValidator()
        valid_count = 0
        issues = []
        
        for i, record in enumerate(records):
            if data_type == 'weather':
                is_valid, errors = validator.validate_weather_data(record)
            elif data_type == 'earthquake':
                is_valid, errors = validator.validate_earthquake_data(record)
            else:
                is_valid, errors = True, []
            
            if is_valid:
                valid_count += 1
            else:
                issues.extend([f"Record {i}: {error}" for error in errors])
        
        quality_score = valid_count / len(records) if records else 0.0
        
        # Update stats
        self.quality_stats['total_records'] += len(records)
        self.quality_stats['valid_records'] += valid_count
        self.quality_stats['invalid_records'] += len(records) - valid_count
        self.quality_stats['quality_score'] = (
            self.quality_stats['valid_records'] / 
            self.quality_stats['total_records'] 
            if self.quality_stats['total_records'] > 0 else 0.0
        )
        
        return {
            'quality_score': quality_score,
            'valid_count': valid_count,
            'invalid_count': len(records) - valid_count,
            'total_count': len(records),
            'issues': issues[:10]  # Limit to first 10 issues
        }
    
    def get_quality_stats(self) -> Dict[str, Any]:
        """Get overall quality statistics"""
        return self.quality_stats.copy()


@dataclass
class WeatherData:
    """Weather data model with validation"""
    timestamp: str
    location_name: str
    lat: float
    lon: float
    temperature_2m: float = 0.0
    wind_speed_10m: float = 0.0
    wind_gusts_10m: float = 0.0
    relative_humidity_2m: float = 0.0
    precipitation: float = 0.0
    pressure_msl: float = 0.0
    cloud_cover: float = 0.0
    visibility: float = 0.0
    uv_index: float = 0.0
    
    def validate(self) -> bool:
        """Validate weather data"""
        try:
            # Check required fields
            if not self.timestamp or not self.location_name:
                return False
            
            # Check coordinate bounds
            if not (-90 <= self.lat <= 90) or not (-180 <= self.lon <= 180):
                return False
            
            # Check reasonable ranges
            if not (-100 <= self.temperature_2m <= 100):
                return False
            
            if not (0 <= self.wind_speed_10m <= 200):
                return False
            
            if not (0 <= self.relative_humidity_2m <= 100):
                return False
            
            return True
        except (ValueError, TypeError):
            return False


@dataclass
class EarthquakeData:
    """Earthquake data model with validation"""
    timestamp: str
    place: str
    magnitude: float
    lat: float
    lon: float
    depth: float = 0.0
    alert: str = ""
    tsunami: int = 0
    felt: int = 0
    significance: int = 0
    
    def validate(self) -> bool:
        """Validate earthquake data"""
        try:
            if not self.timestamp or not self.place:
                return False
            
            if not (-90 <= self.lat <= 90) or not (-180 <= self.lon <= 180):
                return False
            
            if not (0 <= self.magnitude <= 15):
                return False
            
            if not (-1000 <= self.depth <= 1000):
                return False
            
            return True
        except (ValueError, TypeError):
            return False


@dataclass
class DisasterData:
    """Disaster data model with validation"""
    timestamp: str
    title: str
    category: str
    lat: float
    lon: float
    description: str = ""
    source: str = ""
    closed: int = 0
    severity: str = "unknown"
    
    def validate(self) -> bool:
        """Validate disaster data"""
        try:
            if not self.timestamp or not self.title or not self.category:
                return False
            
            if not (-90 <= self.lat <= 90) or not (-180 <= self.lon <= 180):
                return False
            
            return True
        except (ValueError, TypeError):
            return False


@dataclass
class WildfireData:
    """Wildfire data model with validation"""
    timestamp: str
    lat: float
    lon: float
    brightness: float = 0.0
    confidence: float = 0.0
    frp: float = 0.0  # Fire Radiative Power
    track: str = ""
    source: str = ""
    
    def validate(self) -> bool:
        """Validate wildfire data"""
        try:
            if not self.timestamp:
                return False
            
            if not (-90 <= self.lat <= 90) or not (-180 <= self.lon <= 180):
                return False
            
            if not (0 <= self.brightness <= 10000):
                return False
            
            if not (0 <= self.confidence <= 100):
                return False
            
            return True
        except (ValueError, TypeError):
            return False


class ConnectionPool:
    """Thread-safe SQLite connection pool"""
    
    def __init__(self, database_path: str, max_connections: int = 10):
        self.database_path = database_path
        self.max_connections = max_connections
        self.pool = Queue(maxsize=max_connections)
        self.lock = threading.RLock()
        self.total_connections = 0
        self.active_connections = 0
        self.logger = logging.getLogger(f"{__name__}.ConnectionPool")
        
        # Initialize pool with connections
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Initialize the connection pool"""
        for _ in range(self.max_connections):
            conn = self._create_connection()
            if conn:
                self.pool.put(conn)
    
    def _create_connection(self) -> Optional[sqlite3.Connection]:
        """Create a new database connection"""
        try:
            conn = sqlite3.connect(
                self.database_path,
                timeout=config.database.connection_timeout,
                check_same_thread=False
            )
            
            # Enable WAL mode for better concurrent access
            if config.database.enable_wal_mode:
                conn.execute("PRAGMA journal_mode=WAL")
            
            # Performance optimizations
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=10000")
            conn.execute("PRAGMA temp_store=MEMORY")
            conn.execute("PRAGMA mmap_size=268435456")  # 256MB
            
            # Enable foreign keys
            conn.execute("PRAGMA foreign_keys=ON")
            
            with self.lock:
                self.total_connections += 1
            
            return conn
        except Exception as e:
            self.logger.error(f"Failed to create database connection: {e}")
            return None
    
    @contextmanager
    def get_connection(self):
        """Get a connection from the pool"""
        conn = None
        try:
            with self.lock:
                self.active_connections += 1
            
            try:
                conn = self.pool.get(timeout=config.database.connection_timeout)
            except Empty:
                # Pool is empty, create new connection if under limit
                if self.total_connections < self.max_connections:
                    conn = self._create_connection()
                else:
                    raise Exception("Connection pool exhausted")
            
            if conn is None:
                raise Exception("Unable to obtain database connection")
            
            yield conn
            
        except Exception as e:
            self.logger.error(f"Connection error: {e}")
            # Close bad connection
            if conn:
                try:
                    conn.close()
                except:
                    pass
                conn = None
            raise
        finally:
            # Return connection to pool
            if conn:
                try:
                    # Test connection is still good
                    conn.execute("SELECT 1")
                    self.pool.put(conn)
                except:
                    # Connection is bad, close it
                    try:
                        conn.close()
                    except:
                        pass
                    with self.lock:
                        self.total_connections -= 1
            
            with self.lock:
                self.active_connections -= 1
    
    def close_all(self):
        """Close all connections in the pool"""
        while not self.pool.empty():
            try:
                conn = self.pool.get_nowait()
                conn.close()
            except (Empty, Exception):
                break
        
        with self.lock:
            self.total_connections = 0
            self.active_connections = 0
    
    def get_stats(self) -> Dict[str, int]:
        """Get connection pool statistics"""
        with self.lock:
            return {
                'total_connections': self.total_connections,
                'active_connections': self.active_connections,
                'available_connections': self.pool.qsize(),
                'max_connections': self.max_connections
            }


class DatabaseManager:
    """Enhanced database manager with connection pooling and validation"""
    
    def __init__(self, database_path: Optional[str] = None):
        self.database_path = database_path or config.database.path
        self.pool = ConnectionPool(self.database_path, config.database.max_connections)
        self.logger = logging.getLogger(f"{__name__}.DatabaseManager")
        self.lock = threading.RLock()
        
        # Initialize database schema
        self._initialize_schema()
    
    def _initialize_schema(self):
        """Initialize database schema with optimized tables"""
        schema_sql = """
        -- Weather data table with partitioning support
        CREATE TABLE IF NOT EXISTS weather (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            location_name TEXT NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            temperature_2m REAL DEFAULT 0,
            wind_speed_10m REAL DEFAULT 0,
            wind_gusts_10m REAL DEFAULT 0,
            relative_humidity_2m REAL DEFAULT 0,
            precipitation REAL DEFAULT 0,
            pressure_msl REAL DEFAULT 0,
            cloud_cover REAL DEFAULT 0,
            visibility REAL DEFAULT 0,
            uv_index REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(timestamp, location_name, lat, lon)
        );
        
        -- Earthquakes table with improved indexing
        CREATE TABLE IF NOT EXISTS earthquakes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            place TEXT NOT NULL,
            magnitude REAL NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            depth REAL DEFAULT 0,
            alert TEXT DEFAULT '',
            tsunami INTEGER DEFAULT 0,
            felt INTEGER DEFAULT 0,
            significance INTEGER DEFAULT 0,
            source_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(timestamp, lat, lon, magnitude)
        );
        
        -- Disasters table with categorization
        CREATE TABLE IF NOT EXISTS disasters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            description TEXT DEFAULT '',
            source TEXT DEFAULT '',
            closed INTEGER DEFAULT 0,
            severity TEXT DEFAULT 'unknown',
            source_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(timestamp, title, lat, lon)
        );
        
        -- Wildfires table with satellite data
        CREATE TABLE IF NOT EXISTS wildfires (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            brightness REAL DEFAULT 0,
            confidence REAL DEFAULT 0,
            frp REAL DEFAULT 0,
            track TEXT DEFAULT '',
            source TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(timestamp, lat, lon, brightness)
        );
        
        -- Risk assessments table
        CREATE TABLE IF NOT EXISTS risk_assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            location_name TEXT NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            overall_risk REAL DEFAULT 0,
            weather_risk REAL DEFAULT 0,
            seismic_risk REAL DEFAULT 0,
            fire_risk REAL DEFAULT 0,
            flood_risk REAL DEFAULT 0,
            risk_factors TEXT DEFAULT '[]',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        
        -- System metrics table for monitoring
        CREATE TABLE IF NOT EXISTS system_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            metric_value REAL NOT NULL,
            metric_unit TEXT DEFAULT '',
            tags TEXT DEFAULT '{}',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Data quality table for tracking issues
        CREATE TABLE IF NOT EXISTS data_quality (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            table_name TEXT NOT NULL,
            issue_type TEXT NOT NULL,
            issue_description TEXT,
            affected_records INTEGER DEFAULT 1,
            severity TEXT DEFAULT 'low',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        # Create indexes for better performance
        index_sql = """
        -- Weather table indexes
        CREATE INDEX IF NOT EXISTS idx_weather_timestamp ON weather(timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_weather_location ON weather(location_name, timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_weather_coords ON weather(lat, lon);
        CREATE INDEX IF NOT EXISTS idx_weather_composite ON weather(timestamp, location_name);
        
        -- Earthquakes table indexes
        CREATE INDEX IF NOT EXISTS idx_earthquakes_timestamp ON earthquakes(timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_earthquakes_magnitude ON earthquakes(magnitude DESC);
        CREATE INDEX IF NOT EXISTS idx_earthquakes_coords ON earthquakes(lat, lon);
        CREATE INDEX IF NOT EXISTS idx_earthquakes_place ON earthquakes(place);
        
        -- Disasters table indexes
        CREATE INDEX IF NOT EXISTS idx_disasters_timestamp ON disasters(timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_disasters_category ON disasters(category);
        CREATE INDEX IF NOT EXISTS idx_disasters_coords ON disasters(lat, lon);
        CREATE INDEX IF NOT EXISTS idx_disasters_severity ON disasters(severity);
        
        -- Wildfires table indexes
        CREATE INDEX IF NOT EXISTS idx_wildfires_timestamp ON wildfires(timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_wildfires_coords ON wildfires(lat, lon);
        CREATE INDEX IF NOT EXISTS idx_wildfires_confidence ON wildfires(confidence DESC);
        
        -- Risk assessments indexes
        CREATE INDEX IF NOT EXISTS idx_risk_timestamp ON risk_assessments(timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_risk_location ON risk_assessments(location_name, timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_risk_overall ON risk_assessments(overall_risk DESC);
        
        -- System metrics indexes
        CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON system_metrics(timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_metrics_name ON system_metrics(metric_name, timestamp DESC);
        """
        
        try:
            with self.pool.get_connection() as conn:
                cursor = conn.cursor()
                
                # Execute schema creation
                for statement in schema_sql.split(';'):
                    if statement.strip():
                        cursor.execute(statement)
                
                # Execute index creation
                for statement in index_sql.split(';'):
                    if statement.strip():
                        cursor.execute(statement)
                
                conn.commit()
                self.logger.info("Database schema initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize database schema: {e}")
            raise
    
    def insert_weather_data(self, data: Union[WeatherData, List[WeatherData]]) -> bool:
        """Insert weather data with validation"""
        if not isinstance(data, list):
            data = [data]
        
        valid_data = [item for item in data if item.validate()]
        if not valid_data:
            self.logger.warning("No valid weather data to insert")
            return False
        
        sql = """
        INSERT OR REPLACE INTO weather 
        (timestamp, location_name, lat, lon, temperature_2m, wind_speed_10m, 
         wind_gusts_10m, relative_humidity_2m, precipitation, pressure_msl, 
         cloud_cover, visibility, uv_index)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        try:
            with self.pool.get_connection() as conn:
                cursor = conn.cursor()
                
                records = []
                for item in valid_data:
                    records.append((
                        item.timestamp, item.location_name, item.lat, item.lon,
                        item.temperature_2m, item.wind_speed_10m, item.wind_gusts_10m,
                        item.relative_humidity_2m, item.precipitation, item.pressure_msl,
                        item.cloud_cover, item.visibility, item.uv_index
                    ))
                
                cursor.executemany(sql, records)
                conn.commit()
                
                self.logger.info(f"Inserted {len(records)} weather records")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to insert weather data: {e}")
            return False
    
    def insert_earthquake_data(self, data: Union[EarthquakeData, List[EarthquakeData]]) -> bool:
        """Insert earthquake data with validation"""
        if not isinstance(data, list):
            data = [data]
        
        valid_data = [item for item in data if item.validate()]
        if not valid_data:
            self.logger.warning("No valid earthquake data to insert")
            return False
        
        sql = """
        INSERT OR REPLACE INTO earthquakes 
        (timestamp, place, magnitude, lat, lon, depth, alert, tsunami, felt, significance)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        try:
            with self.pool.get_connection() as conn:
                cursor = conn.cursor()
                
                records = []
                for item in valid_data:
                    records.append((
                        item.timestamp, item.place, item.magnitude, item.lat, item.lon,
                        item.depth, item.alert, item.tsunami, item.felt, item.significance
                    ))
                
                cursor.executemany(sql, records)
                conn.commit()
                
                self.logger.info(f"Inserted {len(records)} earthquake records")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to insert earthquake data: {e}")
            return False
    
    def get_weather_data(
        self,
        location_name: Optional[str] = None,
        hours_back: int = 24,
        limit: int = 1000
    ) -> Union[List[Dict], 'pd.DataFrame']:
        """Get weather data with filtering"""
        if hours_back == 0:
            # For tests, return all records
            sql = "SELECT * FROM weather"
        else:
            sql = """
            SELECT * FROM weather
            WHERE datetime(timestamp) >= datetime('now', '-{} hours')
            """.format(hours_back)
        
        params = []
        if location_name:
            sql += " AND location_name = ?"
            params.append(location_name)
        
        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        try:
            with self.pool.get_connection() as conn:
                if pd is not None:
                    return pd.read_sql(sql, conn, params=params)
                else:
                    # Fallback to basic dict results
                    cursor = conn.cursor()
                    cursor.execute(sql, params)
                    columns = [desc[0] for desc in cursor.description]
                    rows = cursor.fetchall()
                    return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            self.logger.error(f"Failed to get weather data: {e}")
            return pd.DataFrame() if pd is not None else []
    
    def get_earthquake_data(
        self,
        min_magnitude: float = 0.0,
        hours_back: int = 24,
        limit: int = 1000
    ) -> Union[List[Dict], 'pd.DataFrame']:
        """Get earthquake data with filtering"""
        sql = """
        SELECT * FROM earthquakes
        WHERE datetime(timestamp) >= datetime('now', '-{} hours')
        AND magnitude >= ?
        ORDER BY magnitude DESC, timestamp DESC
        LIMIT ?
        """.format(hours_back)
        
        try:
            with self.pool.get_connection() as conn:
                if pd is not None:
                    return pd.read_sql(sql, conn, params=[min_magnitude, limit])
                else:
                    cursor = conn.cursor()
                    cursor.execute(sql, [min_magnitude, limit])
                    columns = [desc[0] for desc in cursor.description]
                    rows = cursor.fetchall()
                    return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            self.logger.error(f"Failed to get earthquake data: {e}")
            return pd.DataFrame() if pd is not None else []
    
    def cleanup_old_data(self, days_to_keep: int = 30) -> Dict[str, int]:
        """Clean up old data to maintain database size"""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        cutoff_str = cutoff_date.isoformat()
        
        cleanup_stats = {}
        tables = ['weather', 'earthquakes', 'disasters', 'wildfires', 'system_metrics']
        
        try:
            with self.pool.get_connection() as conn:
                cursor = conn.cursor()
                
                for table in tables:
                    # Count records to be deleted
                    cursor.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE timestamp < ?",
                        (cutoff_str,)
                    )
                    count = cursor.fetchone()[0]
                    
                    # Delete old records
                    cursor.execute(
                        f"DELETE FROM {table} WHERE timestamp < ?",
                        (cutoff_str,)
                    )
                    
                    cleanup_stats[table] = count
                
                # Vacuum database to reclaim space
                cursor.execute("VACUUM")
                conn.commit()
                
                self.logger.info(f"Cleanup completed: {cleanup_stats}")
                return cleanup_stats
                
        except Exception as e:
            self.logger.error(f"Failed to cleanup old data: {e}")
            return {}
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics and health information"""
        stats = {}
        
        try:
            with self.pool.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get table sizes
                tables = ['weather', 'earthquakes', 'disasters', 'wildfires', 
                         'risk_assessments', 'system_metrics']
                
                for table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    stats[f"{table}_count"] = cursor.fetchone()[0]
                
                # Get database size
                cursor.execute("PRAGMA page_size")
                page_size = cursor.fetchone()[0]
                
                cursor.execute("PRAGMA page_count")
                page_count = cursor.fetchone()[0]
                
                stats['database_size_bytes'] = page_size * page_count
                stats['database_size_mb'] = round((page_size * page_count) / 1024 / 1024, 2)
                
                # Get connection pool stats
                stats['connection_pool'] = self.pool.get_stats()
                
                # Get data quality metrics
                cursor.execute("""
                    SELECT COUNT(*) FROM data_quality 
                    WHERE datetime(timestamp) >= datetime('now', '-24 hours')
                """)
                stats['data_quality_issues_24h'] = cursor.fetchone()[0]
                
        except Exception as e:
            self.logger.error(f"Failed to get database stats: {e}")
        
        return stats
    
    def backup_database(self, backup_path: Optional[str] = None) -> bool:
        """Create a compressed backup of the database"""
        if backup_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"kairos_backup_{timestamp}.db.gz"
        
        try:
            with self.pool.get_connection() as conn:
                # Read database content
                with open(self.database_path, 'rb') as db_file:
                    db_content = db_file.read()
                
                # Compress and save
                with gzip.open(backup_path, 'wb') as backup_file:
                    backup_file.write(db_content)
                
                self.logger.info(f"Database backed up to {backup_path}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to backup database: {e}")
            return False
    
    def record_data_quality_issue(
        self,
        table_name: str,
        issue_type: str,
        issue_description: str,
        affected_records: int = 1,
        severity: str = "low"
    ):
        """Record data quality issues for monitoring"""
        sql = """
        INSERT INTO data_quality 
        (timestamp, table_name, issue_type, issue_description, affected_records, severity)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        
        try:
            with self.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (
                    datetime.now().isoformat(),
                    table_name,
                    issue_type,
                    issue_description,
                    affected_records,
                    severity
                ))
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"Failed to record data quality issue: {e}")
    
    def close(self):
        """Close database connection pool"""
        self.pool.close_all()


# Global database manager instance
db_manager = DatabaseManager()
