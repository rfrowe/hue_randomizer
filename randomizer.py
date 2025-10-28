#!/usr/bin/env python3
"""The Randomizer - Blue/Yellow desynchronized light effect."""
import json
import random
import time
import threading
import signal
import sys
import atexit
import logging
import urllib3
import requests
from config import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Disable SSL warnings for self-signed certificate
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# HTTP request timeout (seconds)
REQUEST_TIMEOUT = 5

# Color definitions
BLUE_HUE = 46920  # 65% of 65535
YELLOW_HUE = 12750  # 19% of 65535
MAX_SATURATION = 254
MAX_BRIGHTNESS = 254

# Timing constants (in seconds)
MIN_PERIOD = 1.5
MAX_PERIOD = 2.5
MIN_INITIAL_DELAY = 0.0
MAX_INITIAL_DELAY = 2.0


class HueRandomizer:
    """Control Philips Hue lights with The Randomizer effect."""

    def __init__(self):
        """Initialize the randomizer with configuration."""
        config.validate()
        self.base_url = config.BASE_URL
        self.session = requests.Session()
        self.session.verify = False  # Skip SSL verification for local bridge

    def get_groups(self):
        """Get all available groups/rooms/zones."""
        url = f"{self.base_url}/groups"
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get groups: {e}")
            raise

    def find_group_by_name(self, name):
        """Find a group by name (case-insensitive)."""
        groups = self.get_groups()
        name_lower = name.lower()
        for group_id, group_data in groups.items():
            if group_data.get('name', '').lower() == name_lower:
                return group_id
        return None

    def get_group_state(self, group_id):
        """Get the current state of a group."""
        url = f"{self.base_url}/groups/{group_id}"
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get state for group {group_id}: {e}")
            raise

    def get_light_state(self, light_id):
        """Get the current state of a single light."""
        url = f"{self.base_url}/lights/{light_id}"
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get state for light {light_id}: {e}")
            raise

    def set_light_state(self, light_id, state):
        """Set the state of a single light."""
        url = f"{self.base_url}/lights/{light_id}/state"
        try:
            response = self.session.put(url, json=state, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to set state for light {light_id}: {e}")
            raise

    def restore_light_state(self, light_id, original_state):
        """Restore the original state of a light."""
        state_data = original_state.get('state', {})
        restore_data = {
            "on": state_data.get('on', True),
            "bri": state_data.get('bri', 254),
            "transitiontime": config.TRANSITION_TIME
        }

        # Restore color based on original colormode
        colormode = state_data.get('colormode')
        if colormode == 'ct':
            restore_data['ct'] = state_data.get('ct', 447)
        elif colormode == 'xy':
            restore_data['xy'] = state_data.get('xy', [0.5, 0.5])
        elif colormode == 'hs':
            restore_data['hue'] = state_data.get('hue', 0)
            restore_data['sat'] = state_data.get('sat', 254)
        else:
            # Default to hue/sat if colormode unknown
            restore_data['hue'] = state_data.get('hue', 0)
            restore_data['sat'] = state_data.get('sat', 254)

        self.set_light_state(light_id, restore_data)

    def control_light(self, light_id, duration, original_state, stop_event, brightness=MAX_BRIGHTNESS):
        """Control a single light with blue/yellow alternating pattern.

        Args:
            light_id: The light ID to control
            duration: Total duration of the effect
            original_state: Original state to restore after
            stop_event: Threading event to signal when to stop
            brightness: Brightness level (0-254, default 254)
        """
        # Random initial delay (0-2 seconds)
        initial_delay = random.uniform(MIN_INITIAL_DELAY, MAX_INITIAL_DELAY)

        # Random period (1.5-2.5 seconds)
        period = random.uniform(MIN_PERIOD, MAX_PERIOD)
        half_period = period / 2

        # Wait for initial delay, but check stop_event periodically
        delay_start = time.time()
        while (time.time() - delay_start) < initial_delay:
            if stop_event.is_set():
                # Skip effect entirely if stopped during initial delay
                try:
                    self.restore_light_state(light_id, original_state)
                except:
                    pass
                return
            time.sleep(0.1)  # Check every 100ms

        # Alternate between blue and yellow
        is_blue = True
        start_time = time.time()

        try:
            while (time.time() - start_time) < duration and not stop_event.is_set():
                # Set color based on current state
                color_state = {
                    "on": True,
                    "hue": BLUE_HUE if is_blue else YELLOW_HUE,
                    "sat": MAX_SATURATION,
                    "bri": brightness,
                    "transitiontime": config.TRANSITION_TIME
                }

                self.set_light_state(light_id, color_state)

                # Toggle color for next iteration
                is_blue = not is_blue

                # Wait half period before next color, checking stop_event periodically
                sleep_start = time.time()
                while (time.time() - sleep_start) < half_period:
                    if stop_event.is_set():
                        break
                    time.sleep(0.1)  # Check every 100ms

        except Exception as e:
            logger.error(f"Error controlling light {light_id}: {e}")

        finally:
            # Restore original state
            try:
                logger.info(f"Restoring light {light_id} to original state")
                self.restore_light_state(light_id, original_state)
            except Exception as e:
                logger.error(f"Error restoring light {light_id}: {e}")

    def run_effect(self, group_id, duration=None, brightness=MAX_BRIGHTNESS):
        """Run the randomizer effect on a group.

        Args:
            group_id: The group/room/zone ID or name
            duration: Duration in seconds (uses config default if None)
            brightness: Brightness level (0-254, default 254)

        Returns:
            dict: Status information about the effect
        """
        if duration is None:
            duration = config.EFFECT_DURATION

        # Handle group name lookup
        if not str(group_id).isdigit():
            found_id = self.find_group_by_name(str(group_id))
            if not found_id:
                return {
                    "success": False,
                    "error": f"Group '{group_id}' not found",
                    "available_groups": self._format_groups()
                }
            group_id = found_id

        # Get group info and light IDs
        try:
            group_data = self.get_group_state(group_id)
            group_name = group_data.get('name', f'Group {group_id}')
            light_ids = group_data.get('lights', [])

            if not light_ids:
                return {
                    "success": False,
                    "error": f"No lights found in group '{group_name}'",
                    "group_id": group_id
                }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": f"Failed to get group state: {str(e)}",
                "group_id": group_id
            }

        # Get original states for all lights and filter out unreachable ones
        original_states = {}
        unreachable_lights = []
        for light_id in light_ids:
            try:
                light_state = self.get_light_state(light_id)
                # Check if light is reachable
                if not light_state.get('state', {}).get('reachable', True):
                    logger.warning(f"Light {light_id} ({light_state.get('name')}) is unreachable, skipping")
                    unreachable_lights.append(light_id)
                else:
                    original_states[light_id] = light_state
                    logger.info(f"Light {light_id} ({light_state.get('name')}) is ready")
            except Exception as e:
                logger.error(f"Could not get state for light {light_id}: {e}")
                unreachable_lights.append(light_id)

        if not original_states:
            return {
                "success": False,
                "error": f"No reachable lights found in group '{group_name}'",
                "group_id": group_id,
                "total_lights": len(light_ids),
                "unreachable_lights": len(unreachable_lights)
            }

        # Create threads for each light
        threads = []
        stop_event = threading.Event()
        interrupted = False

        logger.info(f"Starting effect on {len(original_states)} lights for {duration} seconds at {int(brightness/254*100)}% brightness")

        try:
            for light_id in light_ids:
                if light_id in original_states:
                    thread = threading.Thread(
                        target=self.control_light,
                        args=(light_id, duration, original_states[light_id], stop_event, brightness)
                    )
                    thread.daemon = False  # Ensure threads complete before exit
                    thread.start()
                    threads.append(thread)

            # Wait for all threads to complete
            logger.info("Waiting for all light threads to complete...")
            for i, thread in enumerate(threads):
                thread.join(timeout=duration + 10)  # Add buffer to timeout
                if thread.is_alive():
                    logger.warning(f"Thread {i+1}/{len(threads)} is still alive after timeout")

        except KeyboardInterrupt:
            interrupted = True
            logger.warning("Interrupted! Stopping all lights and restoring state...")
            stop_event.set()  # Signal all threads to stop

        except Exception as e:
            interrupted = True
            logger.error(f"Unexpected error: {e}")
            stop_event.set()

        finally:
            # Ensure all threads complete their cleanup
            logger.info("Cleaning up threads and restoring lights...")
            stop_event.set()  # Signal stop in case it wasn't set

            for i, thread in enumerate(threads):
                if thread.is_alive():
                    logger.warning(f"Waiting for thread {i+1}/{len(threads)} to finish cleanup...")
                    thread.join(timeout=5)  # Wait for thread to finish cleanup
                    if thread.is_alive():
                        logger.error(f"Thread {i+1}/{len(threads)} did not finish after 5s timeout")

            # Double-check: restore any lights that might still be in wrong state
            logger.info("Verifying all lights were restored...")
            for light_id, original_state in original_states.items():
                try:
                    current = self.get_light_state(light_id)
                    current_hue = current.get('state', {}).get('hue')

                    # If light is still at blue or yellow, force restore
                    if current_hue in [BLUE_HUE, YELLOW_HUE]:
                        logger.warning(f"Light {light_id} still at effect color, forcing restore")
                        self.restore_light_state(light_id, original_state)
                except Exception as e:
                    logger.error(f"Could not verify/restore light {light_id}: {e}")

        if interrupted:
            logger.warning("Effect was interrupted")
            return {
                "success": False,
                "error": "Effect was interrupted",
                "group_id": group_id,
                "group_name": group_name,
                "lights_controlled": len(threads),
                "unreachable_lights": len(unreachable_lights),
                "message": "All lights restored after interruption"
            }

        logger.info(f"Effect completed successfully on '{group_name}'")
        return {
            "success": True,
            "group_id": group_id,
            "group_name": group_name,
            "duration": duration,
            "lights_controlled": len(threads),
            "unreachable_lights": len(unreachable_lights),
            "message": f"Randomizer effect completed on '{group_name}'"
        }

    def _format_groups(self):
        """Format groups for display."""
        groups = self.get_groups()
        return {
            gid: {"name": data.get('name'), "type": data.get('type')}
            for gid, data in groups.items()
        }


def main():
    """Main entry point for command-line usage."""
    import sys

    randomizer = HueRandomizer()

    # Check command line arguments
    if len(sys.argv) < 2:
        print("Usage: python randomizer.py <group_id_or_name> [duration] [brightness_percent]")
        print("\nAvailable groups:")
        groups = randomizer.get_groups()
        for gid, data in groups.items():
            print(f"  {gid}: {data.get('name')} ({data.get('type')})")
        sys.exit(1)

    group_input = sys.argv[1]
    duration = int(sys.argv[2]) if len(sys.argv) > 2 else None

    # Parse brightness as percentage (0-100) and convert to 0-254
    brightness_percent = int(sys.argv[3]) if len(sys.argv) > 3 else 100
    brightness = int((brightness_percent / 100.0) * 254)

    # Run the effect
    result = randomizer.run_effect(group_input, duration, brightness)

    # Print result as JSON for Shortcuts integration
    print(json.dumps(result, indent=2))

    # Exit with appropriate code
    sys.exit(0 if result['success'] else 1)


if __name__ == '__main__':
    main()