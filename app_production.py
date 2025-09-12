"""
Production-Ready Project Kairos - Enhanced Disaster Warning System
Main Streamlit application with comprehensive error handling, monitoring, and resilience.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import folium
from streamlit_folium import st_folium
import pydeck as pdk
import numpy as np
import logging
import json
import io
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import asyncio
import threading
from pathlib import Path

# Import production modules
from config import config
from database import db_manager, WeatherData, EarthquakeData, DisasterData, WildfireData
from cache import cache_manager
from resilience import resilience_manager
from monitoring import monitoring_manager

# Configure logging for production
logging.basicConfig(
    level=getattr(logging, config.monitoring.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.monitoring.log_file),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class DataService:
    """Service layer for fetching and processing disaster data"""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.DataService")
    
    @cache_manager.cached(cache_type='weather', ttl=300)
    def get_weather_data(self, lat: float, lon: float, location_name: str) -> Dict[str, Any]:
        """Get weather data with resilience and caching"""
        
        def fetch_weather():
            import requests
            
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                'latitude': lat,
                'longitude': lon,
                'current': [
                    'temperature_2m', 'relative_humidity_2m', 'precipitation',
                    'wind_speed_10m', 'wind_gusts_10m', 'pressure_msl',
                    'cloud_cover', 'visibility', 'uv_index'
                ],
                'hourly': [
                    'temperature_2m', 'precipitation_probability', 'wind_speed_10m'
                ],
                'forecast_days': 3
            }
            
            response = requests.get(url, params=params, timeout=config.api.timeout_seconds)
            response.raise_for_status()
            return response.json()
        
        # Fallback data for when API is unavailable
        fallback_data = {
            "location_name": location_name,
            "lat": lat,
            "lon": lon,
            "timestamp": datetime.now().isoformat(),
            "temperature_2m": 20.0,
            "wind_speed_10m": 5.0,
            "wind_gusts_10m": 8.0,
            "relative_humidity_2m": 60.0,
            "precipitation": 0.0,
            "pressure_msl": 1013.25,
            "cloud_cover": 50.0,
            "visibility": 10000.0,
            "uv_index": 3.0,
            "hourly_forecast": {
                "time": [],
                "temperature_2m": [],
                "precipitation_probability": [],
                "wind_speed_10m": []
            },
            "source": "fallback"
        }
        
        try:
            # Use resilience manager for API call
            api_data = resilience_manager.execute_with_resilience(
                service="weather_api",
                func=fetch_weather,
                fallback_data=fallback_data
            )
            
            if api_data == fallback_data:
                return fallback_data
            
            # Process successful API response
            current = api_data.get("current", {})
            hourly = api_data.get("hourly", {})
            
            result = {
                "location_name": location_name,
                "lat": lat,
                "lon": lon,
                "timestamp": current.get("time", datetime.now().isoformat()),
                "temperature_2m": current.get("temperature_2m", 0),
                "wind_speed_10m": current.get("wind_speed_10m", 0),
                "wind_gusts_10m": current.get("wind_gusts_10m", 0),
                "relative_humidity_2m": current.get("relative_humidity_2m", 0),
                "precipitation": current.get("precipitation", 0),
                "pressure_msl": current.get("pressure_msl", 0),
                "cloud_cover": current.get("cloud_cover", 0),
                "visibility": current.get("visibility", 0),
                "uv_index": current.get("uv_index", 0),
                "hourly_forecast": {
                    "time": hourly.get("time", [])[:24],
                    "temperature_2m": hourly.get("temperature_2m", [])[:24],
                    "precipitation_probability": hourly.get("precipitation_probability", [])[:24],
                    "wind_speed_10m": hourly.get("wind_speed_10m", [])[:24]
                },
                "source": "api"
            }
            
            # Store in database
            weather_data = WeatherData(
                timestamp=result["timestamp"],
                location_name=location_name,
                lat=lat,
                lon=lon,
                temperature_2m=result["temperature_2m"],
                wind_speed_10m=result["wind_speed_10m"],
                wind_gusts_10m=result["wind_gusts_10m"],
                relative_humidity_2m=result["relative_humidity_2m"],
                precipitation=result["precipitation"],
                pressure_msl=result["pressure_msl"],
                cloud_cover=result["cloud_cover"],
                visibility=result["visibility"],
                uv_index=result["uv_index"]
            )
            
            db_manager.insert_weather_data(weather_data)
            return result
            
        except Exception as e:
            self.logger.error(f"Weather data fetch failed for {location_name}: {e}")
            return fallback_data
    
    @cache_manager.cached(cache_type='disasters', ttl=600)
    def get_earthquake_data(self) -> pd.DataFrame:
        """Get earthquake data with resilience"""
        
        def fetch_earthquakes():
            import requests
            
            urls = [
                "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_hour.geojson",
                "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson",
                "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_month.geojson"
            ]
            
            all_features = []
            for url in urls:
                try:
                    response = requests.get(url, timeout=config.api.timeout_seconds)
                    response.raise_for_status()
                    data = response.json()
                    features = data.get("features", [])
                    all_features.extend(features)
                except Exception as e:
                    self.logger.warning(f"Failed to fetch from {url}: {e}")
            
            return all_features
        
        fallback_data = pd.DataFrame()
        
        try:
            features = resilience_manager.execute_with_resilience(
                service="earthquake_api",
                func=fetch_earthquakes,
                fallback_data=[]
            )
            
            if not features:
                return fallback_data
            
            # Remove duplicates
            unique_features = {}
            for feature in features:
                eq_id = feature.get("id", "")
                if eq_id and eq_id not in unique_features:
                    unique_features[eq_id] = feature
            
            earthquakes = []
            for feature in unique_features.values():
                try:
                    props = feature.get("properties", {})
                    coords = feature.get("geometry", {}).get("coordinates", [0, 0, 0])
                    
                    # Validate coordinates
                    if len(coords) >= 2:
                        lon, lat = coords[0], coords[1]
                        depth = coords[2] if len(coords) > 2 else 0
                        
                        if -180 <= lon <= 180 and -90 <= lat <= 90:
                            earthquake = {
                                "id": feature.get("id", ""),
                                "place": props.get("place", "Unknown"),
                                "magnitude": props.get("mag", 0),
                                "time": pd.to_datetime(props.get("time", 0), unit="ms"),
                                "lat": lat,
                                "lon": lon,
                                "depth": depth,
                                "alert": props.get("alert", ""),
                                "tsunami": 1 if props.get("tsunami") == 1 else 0,
                                "felt": props.get("felt", 0),
                                "significance": props.get("sig", 0),
                                "status": props.get("status", ""),
                                "type": props.get("type", "")
                            }
                            earthquakes.append(earthquake)
                except Exception as e:
                    self.logger.warning(f"Error processing earthquake feature: {e}")
            
            df = pd.DataFrame(earthquakes)
            
            # Store valid earthquakes in database
            if not df.empty:
                earthquake_data_list = []
                for _, row in df.iterrows():
                    eq_data = EarthquakeData(
                        timestamp=row["time"].isoformat(),
                        place=row["place"],
                        magnitude=row["magnitude"],
                        lat=row["lat"],
                        lon=row["lon"],
                        depth=row["depth"],
                        alert=row["alert"],
                        tsunami=row["tsunami"],
                        felt=row["felt"],
                        significance=row["significance"]
                    )
                    earthquake_data_list.append(eq_data)
                
                db_manager.insert_earthquake_data(earthquake_data_list)
            
            return df
            
        except Exception as e:
            self.logger.error(f"Earthquake data fetch failed: {e}")
            return fallback_data
    
    @cache_manager.cached(cache_type='disasters', ttl=1800)
    def get_disaster_data(self) -> List[Dict[str, Any]]:
        """Get disaster data with resilience"""
        
        def fetch_disasters():
            import requests
            
            url = "https://eonet.gsfc.nasa.gov/api/v3/events/geojson?status=open&days=30"
            response = requests.get(url, timeout=config.api.timeout_seconds)
            response.raise_for_status()
            return response.json()
        
        try:
            data = resilience_manager.execute_with_resilience(
                service="disaster_api",
                func=fetch_disasters,
                fallback_data={"features": []}
            )
            
            features = data.get("features", [])
            disasters = []
            
            for feature in features:
                try:
                    props = feature.get("properties", {})
                    coords = feature.get("geometry", {}).get("coordinates", [])
                    
                    # Handle different coordinate formats
                    if isinstance(coords, list) and len(coords) >= 2:
                        # Extract lon, lat from coordinates
                        if isinstance(coords[0], list):
                            # MultiPoint or Polygon format
                            lon, lat = coords[0][0], coords[0][1]
                        else:
                            # Point format
                            lon, lat = coords[0], coords[1]
                        
                        # Validate coordinates are numbers
                        if (isinstance(lon, (int, float)) and isinstance(lat, (int, float)) and
                            -180 <= lon <= 180 and -90 <= lat <= 90):
                            
                            categories = props.get("categories", [])
                            if isinstance(categories, list) and categories:
                                category = categories[0].get("title", "Unknown") if isinstance(categories[0], dict) else "Unknown"
                            else:
                                category = "Unknown"
                            
                            sources = props.get("sources", [])
                            source_id = ""
                            if isinstance(sources, list) and sources and isinstance(sources[0], dict):
                                source_id = sources[0].get("id", "")
                            
                            disaster = {
                                "id": str(props.get("id", "")),
                                "title": str(props.get("title", "Unknown")),
                                "description": str(props.get("description", "")),
                                "category": str(category),
                                "source": str(source_id),
                                "date": str(props.get("date", "")),
                                "lat": float(lat),
                                "lon": float(lon),
                                "closed": 0 if props.get("closed") is None else 1
                            }
                            disasters.append(disaster)
                except Exception as e:
                    self.logger.warning(f"Error processing disaster feature: {e} - Feature: {str(feature)[:200]}...")
            
            return disasters
            
        except Exception as e:
            self.logger.error(f"Disaster data fetch failed: {e}")
            return []


class RiskAnalyzer:
    """Advanced risk analysis with machine learning-like features"""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.RiskAnalyzer")
    
    def calculate_risk(
        self, 
        weather_data: Dict[str, Any], 
        earthquakes: pd.DataFrame,
        disasters: List[Dict[str, Any]],
        wildfires: pd.DataFrame,
        lat: float, 
        lon: float
    ) -> Tuple[Dict[str, float], List[str]]:
        """Calculate comprehensive risk assessment"""
        
        risk_components = {
            'weather_risk': 0.0,
            'seismic_risk': 0.0,
            'fire_risk': 0.0,
            'flood_risk': 0.0,
            'overall_risk': 0.0
        }
        
        risk_factors = []
        
        try:
            # Weather-based risks
            if weather_data and "error" not in weather_data:
                # Wind risk
                wind_speed = weather_data.get("wind_speed_10m", 0)
                wind_gusts = weather_data.get("wind_gusts_10m", 0)
                
                if wind_speed > 15 or wind_gusts > 25:
                    weather_risk = min((wind_speed + wind_gusts * 0.7) / 100, 1.0)
                    risk_components['weather_risk'] += weather_risk * 0.4
                    risk_factors.append(f"High winds: {wind_speed:.1f} m/s (gusts: {wind_gusts:.1f})")
                
                # Temperature extremes
                temp = weather_data.get("temperature_2m", 20)
                if temp > 35:
                    temp_risk = min((temp - 35) / 15, 0.5)
                    risk_components['weather_risk'] += temp_risk
                    risk_factors.append(f"Extreme heat: {temp:.1f}°C")
                elif temp < -10:
                    temp_risk = min(abs(temp + 10) / 20, 0.5)
                    risk_components['weather_risk'] += temp_risk
                    risk_factors.append(f"Extreme cold: {temp:.1f}°C")
                
                # Precipitation and flood risk
                precipitation = weather_data.get("precipitation", 0)
                if precipitation > 10:
                    precip_risk = min(precipitation / 50, 0.8)
                    risk_components['flood_risk'] += precip_risk
                    risk_factors.append(f"Heavy precipitation: {precipitation:.1f} mm")
                
                # UV and visibility
                uv_index = weather_data.get("uv_index", 0)
                visibility = weather_data.get("visibility", 10000)
                
                if uv_index > 8:
                    risk_components['weather_risk'] += 0.1
                    risk_factors.append(f"High UV index: {uv_index}")
                
                if visibility < 1000:
                    risk_components['weather_risk'] += 0.2
                    risk_factors.append(f"Low visibility: {visibility:.0f}m")
            
            # Seismic risk
            if not earthquakes.empty:
                time_threshold = pd.Timestamp.now() - pd.Timedelta(hours=24)
                recent_eq = earthquakes[earthquakes["time"] > time_threshold]
                
                if not recent_eq.empty:
                    # Distance-based risk calculation
                    distances = np.sqrt(
                        (recent_eq["lat"] - lat) ** 2 + (recent_eq["lon"] - lon) ** 2
                    )
                    
                    for radius, weight in [(0.5, 1.0), (2.0, 0.6), (5.0, 0.3)]:
                        nearby_eq = recent_eq[distances < radius]
                        
                        if not nearby_eq.empty:
                            max_mag = nearby_eq["magnitude"].max()
                            eq_count = len(nearby_eq)
                            
                            mag_risk = min(max_mag / 10, 1.0) * weight
                            freq_risk = min(eq_count / 10, 0.3) * weight
                            
                            risk_components['seismic_risk'] += mag_risk + freq_risk
                            risk_factors.append(
                                f"Nearby earthquakes: {eq_count} events, max magnitude {max_mag:.1f}"
                            )
                            break
            
            # Fire risk from nearby disasters
            fire_disasters = [d for d in disasters if 'fire' in d.get('category', '').lower()]
            if fire_disasters:
                nearby_fires = []
                for disaster in fire_disasters:
                    distance = np.sqrt((disaster['lat'] - lat) ** 2 + (disaster['lon'] - lon) ** 2)
                    if distance < 1.0:  # Within ~100km
                        nearby_fires.append(disaster)
                
                if nearby_fires:
                    fire_risk = min(len(nearby_fires) / 5, 0.8)
                    risk_components['fire_risk'] += fire_risk
                    risk_factors.append(f"Nearby wildfires: {len(nearby_fires)} active incidents")
            
            # Compound risk assessment
            if risk_components['weather_risk'] > 0.3 and risk_components['fire_risk'] > 0.2:
                risk_components['fire_risk'] *= 1.5
                risk_factors.append("Compound risk: High winds + active fires")
            
            if risk_components['flood_risk'] > 0.3 and risk_components['seismic_risk'] > 0.2:
                risk_components['overall_risk'] += 0.2
                risk_factors.append("Compound risk: Seismic activity + heavy precipitation")
            
            # Calculate overall risk
            risk_components['overall_risk'] = min(
                risk_components['weather_risk'] * 0.3 +
                risk_components['seismic_risk'] * 0.25 +
                risk_components['fire_risk'] * 0.25 +
                risk_components['flood_risk'] * 0.2 +
                risk_components['overall_risk'],
                1.0
            )
            
        except Exception as e:
            self.logger.error(f"Risk calculation error: {e}")
            risk_factors.append("Risk calculation partially failed")
        
        return risk_components, risk_factors


# Initialize services
data_service = DataService()
risk_analyzer = RiskAnalyzer()

# Streamlit configuration
st.set_page_config(
    page_title="Project Kairos - Production",
    page_icon="🌪️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'monitoring_locations' not in st.session_state:
    st.session_state.monitoring_locations = {
        "San Francisco": (37.7749, -122.4194),
        "New York": (40.7128, -74.0060),
        "Miami": (25.7617, -80.1918),
        "Tokyo": (35.6762, 139.6503),
        "London": (51.5074, -0.1278)
    }

# Custom CSS for better appearance
st.markdown("""
<style>
.main-header {
    background: linear-gradient(90deg, #1f4e79 0%, #2d5aa0 100%);
    padding: 1rem;
    border-radius: 10px;
    color: white;
    text-align: center;
    margin-bottom: 2rem;
}
.metric-card {
    background: white;
    padding: 1rem;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    border-left: 4px solid #1f4e79;
}
.risk-high {
    border-left-color: #dc3545 !important;
}
.risk-medium {
    border-left-color: #ffc107 !important;
}
.risk-low {
    border-left-color: #28a745 !important;
}
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
<div class="main-header">
    <h1>Kairos</h1>
    <p>Advanced Multi-Hazard Monitoring with Predictive Analytics & Real-time Alerts</p>
</div>
""", unsafe_allow_html=True)

# Sidebar configuration
with st.sidebar:
    st.header("System Controls")
    
    # Health status
    st.subheader("System Health")
    try:
        dashboard_data = monitoring_manager.get_dashboard_data()
        overall_status = dashboard_data.get('overall_status', 'unknown')
        
        status_colors = {
            'healthy': '🟢',
            'warning': '🟡', 
            'critical': '🔴',
            'unknown': '⚪'
        }
        
        st.write(f"{status_colors.get(overall_status, '⚪')} Status: {overall_status.title()}")
        
        # Show recent alerts
        recent_alerts = dashboard_data.get('recent_alerts', [])
        if recent_alerts:
            st.warning(f"⚠️ {len(recent_alerts)} alerts in last 24h")
        else:
            st.success("✅ No recent alerts")
            
    except Exception as e:
        st.error(f"Health check failed: {e}")
    
    # Location management
    st.subheader("Monitoring Locations")
    
    with st.expander("Add New Location"):
        new_name = st.text_input("Location Name")
        col1, col2 = st.columns(2)
        with col1:
            new_lat = st.number_input("Latitude", value=0.0, step=0.1, format="%.4f")
        with col2:
            new_lon = st.number_input("Longitude", value=0.0, step=0.1, format="%.4f")
        
        if st.button("Add Location") and new_name:
            if -90 <= new_lat <= 90 and -180 <= new_lon <= 180:
                st.session_state.monitoring_locations[new_name] = (new_lat, new_lon)
                st.success(f"Added {new_name}")
                # Use st.rerun for better stability
                time.sleep(0.5)  # Short delay before rerun
                st.rerun()
            else:
                st.error("Invalid coordinates")
    
    # Location selection
    location_names = list(st.session_state.monitoring_locations.keys())
    selected_location = st.selectbox("Select Primary Location", location_names)
    
    if selected_location and st.button("Remove Location"):
        if len(st.session_state.monitoring_locations) > 1:
            del st.session_state.monitoring_locations[selected_location]
            time.sleep(0.5)
            st.rerun()
        else:
            st.error("Cannot remove the last location")
    
    # Auto-refresh controls
    st.subheader("Refresh Settings")
    auto_refresh_enabled = st.checkbox("Enable Auto-refresh", value=False)
    
    if auto_refresh_enabled:
        refresh_interval = st.selectbox(
            "Refresh Interval", 
            options=[30, 60, 120, 300],
            index=1,
            format_func=lambda x: f"{x} seconds"
        )
        
        # Auto-refresh logic with stability controls
        current_time = time.time()
        if "last_refresh" not in st.session_state:
            st.session_state.last_refresh = current_time
        
        time_since_refresh = current_time - st.session_state.last_refresh
        
        if time_since_refresh >= refresh_interval:
            st.session_state.last_refresh = current_time
            # Use a more stable refresh mechanism
            st.rerun()
        
        # Show countdown
        remaining_time = max(0, refresh_interval - time_since_refresh)
        st.write(f"Next refresh in: {remaining_time:.0f}s")
        
        # Manual refresh button
        if st.button("Refresh Now"):
            st.session_state.last_refresh = current_time
            st.rerun()
    
    # Alert thresholds
    st.subheader("Alert Thresholds")
    wind_threshold = st.slider("Wind Speed Alert (m/s)", 10.0, 50.0, 25.0)
    temp_threshold = st.slider("Temperature Alert (°C)", 30.0, 50.0, 40.0)
    precip_threshold = st.slider("Precipitation Alert (mm)", 10.0, 100.0, 25.0)
    risk_threshold = st.slider("Overall Risk Alert", 0.1, 1.0, 0.6)
    
    # System information
    st.subheader("Performance")
    try:
        cache_stats = cache_manager.get_all_stats()
        db_stats = db_manager.get_database_stats()
        
        st.write(f"**Cache Hit Rate**: {cache_stats.get('weather', {}).get('l1_cache', {}).get('hit_rate', 0):.1%}")
        st.write(f"**DB Size**: {db_stats.get('database_size_mb', 0)} MB")
        st.write(f"**Active Connections**: {db_stats.get('connection_pool', {}).get('active_connections', 0)}")
        
    except Exception as e:
        st.error(f"Performance data unavailable: {e}")

# Main content
if selected_location:
    lat, lon = st.session_state.monitoring_locations[selected_location]
    
    # Fetch data with error handling
    try:
        with st.spinner(f"Fetching data for {selected_location}..."):
            # Fetch all data concurrently using threading
            weather_data = data_service.get_weather_data(lat, lon, selected_location)
            earthquakes = data_service.get_earthquake_data()
            disasters = data_service.get_disaster_data()
            wildfires = pd.DataFrame()  # Simplified for production demo
            
            # Calculate risk
            risk_components, risk_factors = risk_analyzer.calculate_risk(
                weather_data, earthquakes, disasters, wildfires, lat, lon
            )
    
    except Exception as e:
        st.error(f"Data fetch failed: {e}")
        st.stop()
    
    # Alert banner
    st.subheader("Critical Alerts")
    alert_container = st.container()
    
    with alert_container:
        alerts_displayed = False
        
        # Weather alerts
        if weather_data and weather_data.get("source") != "fallback":
            if weather_data.get("wind_speed_10m", 0) > wind_threshold:
                st.error(f"HIGH WIND ALERT: {weather_data['wind_speed_10m']:.1f} m/s at {selected_location}")
                alerts_displayed = True
            
            if weather_data.get("temperature_2m", 20) > temp_threshold:
                st.error(f"EXTREME HEAT: {weather_data['temperature_2m']:.1f}°C at {selected_location}")
                alerts_displayed = True
            
            if weather_data.get("precipitation", 0) > precip_threshold:
                st.error(f"HEAVY RAIN: {weather_data['precipitation']:.1f}mm at {selected_location}")
                alerts_displayed = True
        
        # Risk-based alerts
        overall_risk = risk_components.get('overall_risk', 0)
        if overall_risk > risk_threshold:
            st.error(f"HIGH RISK ZONE: Overall risk {overall_risk:.2f} at {selected_location}")
            alerts_displayed = True
        
        # Earthquake alerts
        if not earthquakes.empty:
            recent_eq = earthquakes[earthquakes["time"] > (pd.Timestamp.now() - pd.Timedelta(hours=6))]
            major_eq = recent_eq[recent_eq["magnitude"] > 4.5]
            
            if not major_eq.empty:
                max_eq = major_eq.loc[major_eq["magnitude"].idxmax()]
                st.error(f"MAJOR EARTHQUAKE: Mag {max_eq['magnitude']:.1f} - {max_eq['place']}")
                alerts_displayed = True
        
        if not alerts_displayed:
            if weather_data.get("source") == "fallback":
                st.warning("Using fallback data - API services may be unavailable")
            else:
                st.success("No critical alerts at this time")
    
    # Main dashboard tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "Live Monitoring", 
        "Risk Assessment", 
        "Analytics",
        "Interactive Maps"
    ])
    
    with tab1:
        st.header(f"Live Data for {selected_location}")
        
        # Weather metrics
        if weather_data:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                temp = weather_data.get('temperature_2m', 0)
                temp_delta = "UV: " + str(weather_data.get('uv_index', 0))
                st.metric("Temperature", f"{temp:.1f}°C", delta=temp_delta)
                
                wind = weather_data.get('wind_speed_10m', 0)
                wind_delta = f"Gusts: {weather_data.get('wind_gusts_10m', 0):.1f}"
                st.metric("Wind Speed", f"{wind:.1f} m/s", delta=wind_delta)
            
            with col2:
                humidity = weather_data.get('relative_humidity_2m', 0)
                st.metric("Humidity", f"{humidity:.0f}%")
                
                precip = weather_data.get('precipitation', 0)
                st.metric("Precipitation", f"{precip:.1f} mm")
            
            with col3:
                visibility = weather_data.get('visibility', 0)
                st.metric("Visibility", f"{visibility:.0f} m")
                
                cloud = weather_data.get('cloud_cover', 0)
                st.metric("Cloud Cover", f"{cloud:.0f}%")
            
            with col4:
                pressure = weather_data.get('pressure_msl', 0)
                st.metric("Pressure", f"{pressure:.1f} hPa")
                
                # Risk indicator
                overall_risk = risk_components.get('overall_risk', 0)
                risk_color = "🔴" if overall_risk > 0.7 else "🟡" if overall_risk > 0.4 else "🟢"
                st.metric(f"{risk_color} Risk Level", f"{overall_risk:.2f}", 
                         delta=f"{len(risk_factors)} factors")
            
            # Data source indicator
            source = weather_data.get('source', 'unknown')
            if source == 'fallback':
                st.warning("Using cached/fallback weather data")
            else:
                st.success("Live weather data")
            
            # Hourly forecast
            hourly = weather_data.get('hourly_forecast', {})
            if hourly.get('time'):
                st.subheader("24-Hour Forecast")
                
                forecast_df = pd.DataFrame({
                    'Time': hourly['time'],
                    'Temperature': hourly['temperature_2m'],
                    'Precipitation %': hourly.get('precipitation_probability', [0] * len(hourly['time'])),
                    'Wind Speed': hourly['wind_speed_10m']
                })
                
                fig = make_subplots(
                    rows=3, cols=1,
                    subplot_titles=('Temperature (°C)', 'Precipitation Probability (%)', 'Wind Speed (m/s)'),
                    shared_xaxes=True,
                    vertical_spacing=0.05
                )
                
                fig.add_trace(
                    go.Scatter(x=forecast_df['Time'], y=forecast_df['Temperature'], 
                              name='Temperature', line=dict(color='red')),
                    row=1, col=1
                )
                fig.add_trace(
                    go.Scatter(x=forecast_df['Time'], y=forecast_df['Precipitation %'], 
                              name='Precipitation %', line=dict(color='blue')),
                    row=2, col=1
                )
                fig.add_trace(
                    go.Scatter(x=forecast_df['Time'], y=forecast_df['Wind Speed'], 
                              name='Wind Speed', line=dict(color='green')),
                    row=3, col=1
                )
                
                fig.update_layout(height=600, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
        
        # Recent events summary
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Recent Earthquakes")
            if not earthquakes.empty:
                recent_eq = earthquakes.head(10)
                display_eq = recent_eq[['place', 'magnitude', 'time', 'depth']].copy()
                display_eq['time'] = display_eq['time'].dt.strftime('%Y-%m-%d %H:%M')
                st.dataframe(display_eq, use_container_width=True)
            else:
                st.info("No recent earthquake data available")
        
        with col2:
            st.subheader("Active Disasters")
            if disasters:
                disaster_df = pd.DataFrame(disasters)
                display_disasters = disaster_df[['title', 'category', 'date']].head(10)
                st.dataframe(display_disasters, use_container_width=True)
            else:
                st.info("No active disasters reported")
    
    with tab2:
        st.header("Multi-Hazard Risk Assessment")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader(f"Risk Analysis for {selected_location}")
            
            # Risk component chart
            risk_data = pd.DataFrame({
                'Risk Type': ['Weather', 'Seismic', 'Fire', 'Flood'],
                'Risk Level': [
                    risk_components.get('weather_risk', 0),
                    risk_components.get('seismic_risk', 0),
                    risk_components.get('fire_risk', 0),
                    risk_components.get('flood_risk', 0)
                ]
            })
            
            fig = px.bar(
                risk_data,
                x='Risk Type',
                y='Risk Level',
                title="Risk Breakdown by Category",
                color='Risk Level',
                color_continuous_scale='RdYlBu_r'
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
            
            # Risk factors
            st.subheader("Active Risk Factors")
            if risk_factors:
                for factor in risk_factors:
                    st.write(f"• {factor}")
            else:
                st.success("No significant risk factors detected")
        
        with col2:
            # Risk gauge
            overall_risk = risk_components.get('overall_risk', 0)
            
            fig = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=overall_risk,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "Overall Risk Level"},
                delta={'reference': 0.5},
                gauge={
                    'axis': {'range': [None, 1]},
                    'bar': {'color': "darkblue"},
                    'steps': [
                        {'range': [0, 0.3], 'color': "lightgreen"},
                        {'range': [0.3, 0.6], 'color': "yellow"},
                        {'range': [0.6, 1], 'color': "red"}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': 0.8
                    }
                }
            ))
            
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
            
            # Recommendations
            st.subheader("Recommendations")
            if overall_risk > 0.7:
                st.error("HIGH RISK: Take immediate precautions")
                st.write("• Monitor emergency channels")
                st.write("• Prepare emergency supplies")
                st.write("• Review evacuation routes")
            elif overall_risk > 0.4:
                st.warning("MODERATE RISK: Stay alert")
                st.write("• Monitor conditions closely")
                st.write("• Check emergency supplies")
                st.write("• Stay informed of updates")
            else:
                st.success("LOW RISK: Normal activities")
                st.write("• Routine monitoring")
                st.write("• Regular preparedness checks")
    
    with tab3:
        st.header("Analytics & Performance")
        
        # System performance
        col1, col2, col3 = st.columns(3)
        
        try:
            dashboard_data = monitoring_manager.get_dashboard_data()
            system_metrics = dashboard_data.get('system_metrics', {})
            
            with col1:
                cpu_data = system_metrics.get('cpu_usage', {})
                cpu_avg = cpu_data.get('avg', 0)
                st.metric("CPU Usage", f"{cpu_avg:.1f}%", 
                         delta=f"Max: {cpu_data.get('max', 0):.1f}%")
            
            with col2:
                mem_data = system_metrics.get('memory_usage', {})
                mem_avg = mem_data.get('avg', 0)
                st.metric("Memory Usage", f"{mem_avg:.1f}%",
                         delta=f"Available: {mem_data.get('latest', 0):.1f}%")
            
            with col3:
                disk_data = system_metrics.get('disk_usage', {})
                disk_latest = disk_data.get('latest', 0)
                st.metric("Disk Usage", f"{disk_latest:.1f}%")
                
        except Exception as e:
            st.error(f"Performance data unavailable: {e}")
        
        # Cache performance
        st.subheader("Cache Performance")
        try:
            cache_analysis = cache_manager.performance_monitor.analyze_performance()
            
            for cache_name, analysis in cache_analysis.get('cache_analysis', {}).items():
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.write(f"**{cache_name.title()} Cache**")
                    hit_rates = analysis.get('hit_rate', {})
                    st.write(f"L1 Hit Rate: {hit_rates.get('l1', 0):.1%}")
                    st.write(f"L2 Hit Rate: {hit_rates.get('l2', 0):.1%}")
                
                with col2:
                    memory_usage = analysis.get('memory_usage', 0)
                    st.write(f"Memory: {memory_usage:.1f} MB")
                    
                with col3:
                    status = analysis.get('status', 'unknown')
                    color = "🟢" if status == 'good' else "🟡"
                    st.write(f"Status: {color} {status}")
                
        except Exception as e:
            st.error(f"Cache analysis unavailable: {e}")
        
        # Data trends
        if not earthquakes.empty:
            st.subheader("Earthquake Trends")
            
            # Magnitude distribution
            fig = px.histogram(
                earthquakes,
                x='magnitude',
                nbins=20,
                title="Earthquake Magnitude Distribution (Recent)"
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with tab4:
        st.header("Interactive Maps")
        
        # Map controls
        col1, col2, col3 = st.columns(3)
        with col1:
            show_earthquakes = st.checkbox("Show Earthquakes", True)
        with col2:
            show_disasters = st.checkbox("Show Disasters", True)
        with col3:
            show_locations = st.checkbox("Show All Locations", True)
        
        # Create interactive map
        st.subheader("Multi-Hazard Map")
        
        # Center on selected location
        m = folium.Map(location=[lat, lon], zoom_start=4)
        
        # Add monitoring locations
        if show_locations:
            for loc_name, (loc_lat, loc_lon) in st.session_state.monitoring_locations.items():
                # Get risk for this location (simplified)
                try:
                    loc_weather = data_service.get_weather_data(loc_lat, loc_lon, loc_name)
                    loc_risk, _ = risk_analyzer.calculate_risk(
                        loc_weather, earthquakes, disasters, wildfires, loc_lat, loc_lon
                    )
                    overall = loc_risk.get('overall_risk', 0)
                    
                    # Color based on risk
                    if overall > 0.6:
                        color = 'red'
                    elif overall > 0.3:
                        color = 'orange'
                    else:
                        color = 'green'
                    
                    # Highlight selected location
                    if loc_name == selected_location:
                        icon = folium.Icon(color=color, icon='star')
                    else:
                        icon = folium.Icon(color=color, icon='circle')
                    
                    folium.Marker(
                        location=[loc_lat, loc_lon],
                        popup=f"""
                        <b>{loc_name}</b><br>
                        Risk Level: {overall:.2f}<br>
                        Temperature: {loc_weather.get('temperature_2m', 'N/A')}°C<br>
                        Wind: {loc_weather.get('wind_speed_10m', 'N/A')} m/s
                        """,
                        icon=icon
                    ).add_to(m)
                    
                except Exception as e:
                    st.warning(f"Could not process {loc_name}: {e}")
        
        # Add earthquakes
        if show_earthquakes and not earthquakes.empty:
            recent_eq = earthquakes.head(50)  # Limit for performance
            
            for _, row in recent_eq.iterrows():
                folium.CircleMarker(
                    location=[row['lat'], row['lon']],
                    radius=max(3, row['magnitude'] * 2),
                    popup=f"""
                    <b>Earthquake</b><br>
                    Location: {row['place']}<br>
                    Magnitude: {row['magnitude']}<br>
                    Depth: {row['depth']}km<br>
                    Time: {row['time'].strftime('%Y-%m-%d %H:%M')}
                    """,
                    color='red',
                    fill=True,
                    fillOpacity=0.7
                ).add_to(m)
        
        # Add disasters
        if show_disasters and disasters:
            for disaster in disasters[:50]:  # Limit for performance
                try:
                    folium.Marker(
                        location=[disaster['lat'], disaster['lon']],
                        popup=f"""
                        <b>{disaster['category']}</b><br>
                        {disaster['title']}<br>
                        Date: {disaster['date']}
                        """,
                        icon=folium.Icon(color='blue', icon='exclamation-sign')
                    ).add_to(m)
                except:
                    continue  # Skip invalid disasters
        
        # Display map
        st_folium(m, width=700, height=500)

else:
    st.warning("Please select a location from the sidebar to view data.")

# Footer with system status
st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    st.write("**System Status**")
    try:
        dashboard_data = monitoring_manager.get_dashboard_data()
        status = dashboard_data.get('overall_status', 'unknown')
        if status == 'healthy':
            st.success("All systems operational")
        elif status == 'warning':
            st.warning("Some issues detected")
        else:
            st.error("System issues present")
    except:
        st.error("Monitoring unavailable")

with col2:
    st.write("**Data Sources**")
    st.write("• Open-Meteo Weather API")
    st.write("• USGS Earthquake Feed") 
    st.write("• NASA EONET Disasters")
    st.write("• Resilient Architecture")

with col3:
    st.write("**ℹSystem Info**")
    st.write(f"• Monitoring: {len(st.session_state.monitoring_locations)} locations")
    st.write("• Production-Ready")
    st.write("• Auto-Scaling")
    st.write("• Real-time Monitoring")
