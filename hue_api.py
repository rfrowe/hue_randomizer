"""Philips Hue CLIP v2 API client classes."""
import logging
import requests
import urllib3
from config import config

logger = logging.getLogger(__name__)

# Disable SSL warnings for self-signed certificate
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# HTTP request timeout (seconds)
REQUEST_TIMEOUT = 2  # Reduced from 5 to speed up fallback on wrong endpoint


class HueClient:
    """Base client for Philips Hue CLIP v2 API."""

    # Shared session across all API clients for connection reuse
    _shared_session = None

    def __init__(self, session=None):
        """Initialize the Hue API client.

        Args:
            session: Optional shared requests.Session. If not provided, uses/creates shared session.
        """
        config.validate()
        self.base_url = config.BASE_URL

        if session:
            self.session = session
        elif HueClient._shared_session:
            self.session = HueClient._shared_session
        else:
            # Create shared session
            self.session = requests.Session()
            self.session.verify = False  # Skip SSL verification for local bridge

            # Configure connection pooling for better performance
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=10,
                pool_maxsize=20,
                max_retries=0  # Disable retries for faster failures
            )
            self.session.mount('https://', adapter)

            # Set up CLIP v2 authentication header
            self.session.headers.update({
                'hue-application-key': config.HUE_API_KEY
            })

            HueClient._shared_session = self.session


class ZoneAPI(HueClient):
    """API methods for Hue zones."""

    def get_all_zones(self):
        """Get all zones."""
        url = f"{self.base_url}/resource/zone"
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()

            zones = {}
            for item in data.get('data', []):
                grouped_light_id = None
                for svc in item.get('services', []):
                    if svc.get('rtype') == 'grouped_light':
                        grouped_light_id = svc.get('rid')
                        break

                zones[item['id']] = {
                    'name': item['metadata']['name'],
                    'type': 'Zone',
                    'lights': [child['rid'] for child in item.get('children', []) if child.get('rtype') == 'light'],
                    'grouped_light_id': grouped_light_id
                }
            logger.debug(f"Retrieved {len(zones)} zones")
            return zones
        except requests.exceptions.RequestException as e:
            logger.error(f"API error getting zones: {e}")
            raise

    def get_zone(self, zone_id):
        """Get a specific zone by ID."""
        url = f"{self.base_url}/resource/zone/{zone_id}"
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()

            if 'data' in data and len(data['data']) > 0:
                item = data['data'][0]
                grouped_light_id = None
                for svc in item.get('services', []):
                    if svc.get('rtype') == 'grouped_light':
                        grouped_light_id = svc.get('rid')
                        break

                return {
                    'name': item['metadata']['name'],
                    'lights': [child['rid'] for child in item.get('children', []) if child.get('rtype') == 'light'],
                    'grouped_light_id': grouped_light_id
                }
            logger.warning(f"Zone {zone_id} not found in response")
            return None
        except requests.exceptions.RequestException as e:
            logger.debug(f"API error getting zone {zone_id}: {e}")
            return None  # Return None to allow fallback to room


class RoomAPI(HueClient):
    """API methods for Hue rooms."""

    def get_all_rooms(self):
        """Get all rooms."""
        url = f"{self.base_url}/resource/room"
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()

            rooms = {}
            for item in data.get('data', []):
                grouped_light_id = None
                for svc in item.get('services', []):
                    if svc.get('rtype') == 'grouped_light':
                        grouped_light_id = svc.get('rid')
                        break

                rooms[item['id']] = {
                    'name': item['metadata']['name'],
                    'type': 'Room',
                    'lights': [child['rid'] for child in item.get('children', []) if child.get('rtype') == 'light'],
                    'grouped_light_id': grouped_light_id
                }
            logger.debug(f"Retrieved {len(rooms)} rooms")
            return rooms
        except requests.exceptions.RequestException as e:
            logger.error(f"API error getting rooms: {e}")
            raise

    def get_room(self, room_id):
        """Get a specific room by ID."""
        url = f"{self.base_url}/resource/room/{room_id}"
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()

            if 'data' in data and len(data['data']) > 0:
                item = data['data'][0]
                grouped_light_id = None
                for svc in item.get('services', []):
                    if svc.get('rtype') == 'grouped_light':
                        grouped_light_id = svc.get('rid')
                        break

                return {
                    'name': item['metadata']['name'],
                    'lights': [child['rid'] for child in item.get('children', []) if child.get('rtype') == 'light'],
                    'grouped_light_id': grouped_light_id
                }
            logger.warning(f"Room {room_id} not found in response")
            return None
        except requests.exceptions.RequestException as e:
            logger.debug(f"API error getting room {room_id}: {e}")
            return None  # Return None to allow fallback


class LightAPI(HueClient):
    """API methods for Hue lights."""

    def get_all_lights(self):
        """Get all lights' states in a single batch request."""
        url = f"{self.base_url}/resource/light"
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            lights_dict = {light['id']: light for light in data.get('data', [])}
            logger.debug(f"Retrieved {len(lights_dict)} lights")
            return lights_dict
        except requests.exceptions.RequestException as e:
            logger.error(f"API error getting lights: {e}")
            raise

    def get_light(self, light_id):
        """Get the current state of a single light."""
        url = f"{self.base_url}/resource/light/{light_id}"
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            if 'data' in data and len(data['data']) > 0:
                return data['data'][0]
            logger.warning(f"No data returned for light {light_id}")
            raise Exception(f"No data returned for light {light_id}")
        except requests.exceptions.RequestException as e:
            logger.error(f"API error getting light {light_id}: {e}")
            raise

    def set_light_state(self, light_id, state):
        """Set the state of a single light using CLIP v2.

        Converts v1-style state dict to CLIP v2 format.
        """
        url = f"{self.base_url}/resource/light/{light_id}"

        # Convert v1 state format to CLIP v2 format
        v2_state = {}

        # Handle on/off
        if 'on' in state:
            v2_state['on'] = {'on': state['on']}

        # Handle brightness (bri -> dimming)
        if 'bri' in state:
            v2_state['dimming'] = {'brightness': round((state['bri'] / 254) * 100, 2)}

        # Handle color - convert hue/sat to xy
        if 'hue' in state and 'sat' in state:
            # Simplified conversion for blue and yellow
            hue = state['hue']
            BLUE_HUE = 46920
            YELLOW_HUE = 12750

            if hue == BLUE_HUE:
                v2_state['color'] = {'xy': {'x': 0.1691, 'y': 0.0441}}  # Blue
            elif hue == YELLOW_HUE:
                v2_state['color'] = {'xy': {'x': 0.5, 'y': 0.5}}  # Yellow
            else:
                # Generic conversion
                v2_state['color'] = {'xy': {'x': 0.3, 'y': 0.3}}

        # Handle color temperature
        if 'ct' in state:
            v2_state['color_temperature'] = {'mirek': state['ct']}

        # Handle xy color
        if 'xy' in state:
            v2_state['color'] = {'xy': {'x': state['xy'][0], 'y': state['xy'][1]}}

        # Dynamics/transition - CLIP v2 uses duration in ms
        if 'transitiontime' in state:
            duration_ms = state['transitiontime'] * 100
            v2_state['dynamics'] = {'duration': duration_ms}

        try:
            response = self.session.put(url, json=v2_state, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to set state for light {light_id}: {e}")
            # Don't raise - continue the effect


class GroupedLightAPI(HueClient):
    """API methods for Hue grouped lights (rooms/zones)."""

    def set_grouped_light_state(self, grouped_light_id, state):
        """Set the state of a grouped light (all lights in room/zone at once)."""
        url = f"{self.base_url}/resource/grouped_light/{grouped_light_id}"
        try:
            response = self.session.put(url, json=state, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to set grouped light {grouped_light_id}: {e}")
            # Don't raise - this is just for instant start
