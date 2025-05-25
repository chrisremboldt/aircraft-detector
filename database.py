# Database module for storing aircraft detections
import sqlite3
import datetime
import logging
import json

logger = logging.getLogger(__name__)

class Database:
    """SQLite database for storing aircraft detections"""

    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = None

    def initialize(self):
        """Initialize the database and create tables if they don't exist"""
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = self.conn.cursor()

            # Create detections table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS detections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    x INTEGER NOT NULL,
                    y INTEGER NOT NULL,
                    width INTEGER NOT NULL,
                    height INTEGER NOT NULL,
                    contrast REAL NOT NULL,
                    confidence REAL NOT NULL,
                    image_path TEXT,
                    speed REAL,
                    direction REAL
                )
            ''')

            # Create tracking table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tracking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    detection_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    x INTEGER NOT NULL,
                    y INTEGER NOT NULL,
                    FOREIGN KEY (detection_id) REFERENCES detections (id)
                )
            ''')

            # Create ADS-B correlation table
            self.create_adsb_correlation_table()

            self.conn.commit()
            logger.info("Database initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            return False

    def create_adsb_correlation_table(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS adsb_correlations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                detection_id INTEGER,
                aircraft_count INTEGER,
                correlation_timestamp TEXT,
                aircraft_data TEXT,
                FOREIGN KEY (detection_id) REFERENCES detections (id)
            )
        ''')

    def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def record_detection(self, x, y, width, height, contrast, confidence, image_path=None, speed=None, direction=None):
        """Record a new aircraft detection"""
        if not self.conn:
            logger.error("Database not initialized")
            return None

        try:
            cursor = self.conn.cursor()
            timestamp = datetime.datetime.now().isoformat()

            cursor.execute('''
                INSERT INTO detections
                (timestamp, x, y, width, height, contrast, confidence, image_path, speed, direction)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (timestamp, x, y, width, height, contrast, confidence, image_path, speed, direction))

            self.conn.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to record detection: {e}")
            return None

    def record_tracking(self, detection_id, x, y):
        """Record a tracking update for an existing detection"""
        if not self.conn:
            logger.error("Database not initialized")
            return False

        try:
            cursor = self.conn.cursor()
            timestamp = datetime.datetime.now().isoformat()

            cursor.execute('''
                INSERT INTO tracking
                (detection_id, timestamp, x, y)
                VALUES (?, ?, ?, ?)
            ''', (detection_id, timestamp, x, y))

            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to record tracking: {e}")
            return False

    def get_recent_detections(self, limit=100):
        """Get recent aircraft detections"""
        if not self.conn:
            logger.error("Database not initialized")
            return []

        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT * FROM detections
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (limit,))

            columns = [column[0] for column in cursor.description]
            detections = []
            for row in cursor.fetchall():
                detections.append(dict(zip(columns, row)))

            return detections
        except Exception as e:
            logger.error(f"Failed to get recent detections: {e}")
            return []

    def update_detection_with_adsb(self, detection_id, adsb_data):
        """Store ADS-B correlation data for a detection"""
        if not self.conn:
            logger.error("Database not initialized")
            return False

        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO adsb_correlations
                (detection_id, aircraft_count, correlation_timestamp, aircraft_data)
                VALUES (?, ?, ?, ?)
            ''', (
                detection_id,
                adsb_data.get('adsb_aircraft_count', 0),
                adsb_data.get('timestamp'),
                json.dumps(adsb_data.get('aircraft', []))
            ))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to record ADS-B correlation: {e}")
            return False

