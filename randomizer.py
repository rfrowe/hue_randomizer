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
from hue_api import ZoneAPI, RoomAPI, LightAPI, GroupedLightAPI
from config import config

# Configure logging with millisecond precision
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Disable SSL warnings for self-signed certificate
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Color definitions (hue/saturation for v1-style state dict)
BLUE_HUE = 46920  # 65% of 65535
YELLOW_HUE = 12750  # 19% of 65535
MAX_SATURATION = 254
MAX_BRIGHTNESS = 254

# Timing constants (in seconds)
MAX_FIRST_COLOR_REDUCTION = 2.0  # Maximum random offset for desynchronization


class HueRandomizer:
    """Control Philips Hue lights with The Randomizer effect."""

    def __init__(self):
        """Initialize the randomizer with configuration."""
        config.validate()

        # Initialize API clients
        self.zone_api = ZoneAPI()
        self.room_api = RoomAPI()
        self.light_api = LightAPI()
        self.grouped_light_api = GroupedLightAPI()

    def get_groups(self):
        """Get all available groups/rooms/zones."""
        groups = {}
        groups.update(self.room_api.get_all_rooms())
        groups.update(self.zone_api.get_all_zones())

        if not groups:
            raise Exception("No groups found")

        return groups

    def find_group_by_name(self, name):
        """Find a group by name (case-insensitive).

        Returns:
            tuple: (group_id, group_type) or (None, None) if not found
        """
        groups = self.get_groups()
        name_lower = name.lower()
        for group_id, group_data in groups.items():
            if group_data.get('name', '').lower() == name_lower:
                return group_id, group_data.get('type')
        return None, None

    def get_group_state(self, group_id, group_type=None):
        """Get the current state of a group.

        Args:
            group_id: The group UUID
            group_type: Optional 'Room' or 'Zone' to skip trying both endpoints
        """
        logger.debug(f"Getting group state for {group_id}, type={group_type}")

        if group_type == 'Zone':
            return self.zone_api.get_zone(group_id)
        elif group_type == 'Room':
            return self.room_api.get_room(group_id)
        else:
            # Try zone first (more common), then room
            result = self.zone_api.get_zone(group_id)
            if result:
                return result
            result = self.room_api.get_room(group_id)
            if result:
                return result
            raise Exception(f"Failed to get state for group {group_id}")

    def set_light_state(self, light_id, state):
        """Set the state of a single light (delegates to LightAPI)."""
        return self.light_api.set_light_state(light_id, state)

    def restore_light_state(self, light_id, original_state):
        """Restore the original state of a light from CLIP v2 format."""
        restore_data = {
            "on": original_state.get('on', {}).get('on', True),
            "transitiontime": config.TRANSITION_TIME
        }

        # Restore brightness
        if 'dimming' in original_state:
            bri_pct = original_state['dimming'].get('brightness', 100)
            restore_data['bri'] = int((bri_pct / 100) * 254)

        # Restore color based on what's available
        if 'color' in original_state and 'xy' in original_state['color']:
            xy = original_state['color']['xy']
            restore_data['xy'] = [xy.get('x', 0.3), xy.get('y', 0.3)]
        elif 'color_temperature' in original_state:
            mirek = original_state['color_temperature'].get('mirek', 447)
            restore_data['ct'] = mirek
        else:
            # Default to neutral white
            restore_data['ct'] = 447

        self.set_light_state(light_id, restore_data)

    def control_light(self, light_id, duration, original_state, stop_event, effect_start_time, brightness=MAX_BRIGHTNESS):
        """Control a single light with blue/yellow alternating pattern.

        Args:
            light_id: The light ID to control
            duration: Total duration of the effect
            original_state: Original state to restore after
            stop_event: Threading event to signal when to stop
            brightness: Brightness level (0-254, default 254)
        """
        # Fixed period between color changes (2 seconds)
        color_change_interval = 2.0

        # Random offset (0.1 - 2 seconds) for first yellow switch
        first_yellow_offset = random.uniform(0.1, MAX_FIRST_COLOR_REDUCTION)

        try:
            # All lights start blue (already set by grouped_light)
            # Wait for random offset before switching to yellow
            if stop_event.wait(timeout=first_yellow_offset):
                return  # stop_event was set, exit early

            # Check if duration exceeded during the wait
            if (time.time() - effect_start_time) >= duration:
                return

            # Now alternate between yellow and blue every 2 seconds
            is_blue = False  # Start with yellow since we're already blue

            # Track when the next color change should happen
            next_change_time = time.time() + color_change_interval

            while (time.time() - effect_start_time) < duration and not stop_event.is_set():
                # Set color
                color_state = {
                    "on": True,
                    "hue": BLUE_HUE if is_blue else YELLOW_HUE,
                    "sat": MAX_SATURATION,
                    "bri": brightness,
                    "transitiontime": config.TRANSITION_TIME
                }

                api_call_start = time.time()
                self.set_light_state(light_id, color_state)
                api_call_duration = time.time() - api_call_start

                # Check if we're past duration after the color change
                if (time.time() - effect_start_time) >= duration:
                    break

                # Toggle color for next iteration
                is_blue = not is_blue

                # Wait until next_change_time, accounting for API call duration
                wait_until = next_change_time
                next_change_time = wait_until + color_change_interval

                time_to_wait = wait_until - time.time()
                if time_to_wait > 0:
                    remaining_time = duration - (time.time() - effect_start_time)
                    actual_wait = min(time_to_wait, remaining_time)
                    if stop_event.wait(timeout=actual_wait):
                        break  # stop_event was set

        except Exception as e:
            logger.error(f"Error controlling light {light_id}: {e}")

        # Don't restore here - let run_effect() handle batch restore at the end

    def run_effect(self, group_id, duration=None, brightness=MAX_BRIGHTNESS, group_type=None, grouped_light_id_hint=None):
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

        # Handle group name lookup (only if not a UUID)
        # UUIDs contain dashes, names don't
        if '-' not in str(group_id):
            # This looks like a name, not an ID - do lookup
            found_id, found_type = self.find_group_by_name(str(group_id))
            if not found_id:
                return {
                    "success": False,
                    "error": f"Group '{group_id}' not found",
                    "available_groups": self._format_groups()
                }
            group_id = found_id
            if not group_type:  # Use found type if not explicitly provided
                group_type = found_type
        # else: group_id is already a UUID, use provided group_type or try both

        # Get group info and light IDs
        try:
            group_data = self.get_group_state(group_id, group_type)
            group_name = group_data.get('name', f'Group {group_id}')
            light_ids = group_data.get('lights', [])
            logger.debug(f"Group '{group_name}' has {len(light_ids)} lights")

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

        # Get original states for all lights in a single batch request
        original_states = {}
        unreachable_lights = []

        try:
            all_lights = self.light_api.get_all_lights()
            logger.debug(f"Retrieved states for {len(all_lights)} lights")

            # Filter to only the lights in this group
            for light_id in light_ids:
                if light_id not in all_lights:
                    logger.warning(f"Light {light_id} not found in bridge")
                    unreachable_lights.append(light_id)
                    continue

                light_state = all_lights[light_id]

                # Check if light is reachable
                if light_state.get('owner', {}).get('rtype') != 'device':
                    logger.debug(f"Light {light_id} ({light_state.get('metadata', {}).get('name')}) is not reachable, skipping")
                    unreachable_lights.append(light_id)
                else:
                    original_states[light_id] = light_state
                    logger.debug(f"Light {light_id} ({light_state.get('metadata', {}).get('name')}) ready")

        except Exception as e:
            logger.error(f"Failed to get light states: {e}")
            return {
                "success": False,
                "error": f"Failed to get light states: {str(e)}",
                "group_id": group_id
            }

        if not original_states:
            return {
                "success": False,
                "error": f"No reachable lights found in group '{group_name}'",
                "group_id": group_id,
                "total_lights": len(light_ids),
                "unreachable_lights": len(unreachable_lights)
            }

        # INSTANT START: Set all lights to blue using grouped_light for immediate visual feedback
        grouped_light_id = grouped_light_id_hint or group_data.get('grouped_light_id')
        if grouped_light_id:
            logger.debug(f"Setting all lights to blue via grouped_light")
            brightness_pct = round((brightness / 254) * 100, 2)
            instant_state = {
                "on": {"on": True},
                "dimming": {"brightness": brightness_pct},
                "color": {"xy": {"x": 0.1691, "y": 0.0441}},  # Blue
                "dynamics": {"duration": 0}  # Instant
            }
            self.grouped_light_api.set_grouped_light_state(grouped_light_id, instant_state)

        # Create threads for each light
        threads = []
        stop_event = threading.Event()
        interrupted = False

        logger.info(f"Starting effect on '{group_name}': {len(original_states)} lights, {duration}s, {int(brightness/254*100)}% brightness")

        # Record effect start time for all threads to synchronize against
        effect_start_time = time.time()

        try:
            for light_id in light_ids:
                if light_id in original_states:
                    thread = threading.Thread(
                        target=self.control_light,
                        args=(light_id, duration, original_states[light_id], stop_event, effect_start_time, brightness)
                    )
                    thread.daemon = False
                    thread.start()
                    threads.append(thread)

            # Wait for all threads to complete
            logger.debug("Waiting for light threads to complete...")
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
            # Ensure all threads complete
            logger.debug("Cleaning up threads...")
            stop_event.set()

            for i, thread in enumerate(threads):
                if thread.is_alive():
                    logger.debug(f"Waiting for thread {i+1}/{len(threads)} to finish...")
                    thread.join(timeout=5)
                    if thread.is_alive():
                        logger.error(f"Thread {i+1}/{len(threads)} did not finish after 5s timeout")

            # Opportunistic batch restore: check if all lights had the same state
            logger.debug(f"Restoring {len(original_states)} lights...")

            # Check if all lights have the same color and brightness
            states_list = list(original_states.values())
            if len(states_list) > 0:
                first_state = states_list[0]
                first_on = first_state.get('on', {}).get('on', True)
                first_brightness = first_state.get('dimming', {}).get('brightness', 100)
                first_color = first_state.get('color', {}).get('xy', {})
                first_ct = first_state.get('color_temperature', {}).get('mirek')

                # Debug: check what's different
                differences = []
                for i, state in enumerate(states_list):
                    if state.get('on', {}).get('on', True) != first_on:
                        differences.append(f"Light {i}: on={state.get('on', {}).get('on')} vs {first_on}")
                    if state.get('dimming', {}).get('brightness', 100) != first_brightness:
                        differences.append(f"Light {i}: brightness={state.get('dimming', {}).get('brightness')} vs {first_brightness}")
                    if state.get('color', {}).get('xy', {}) != first_color:
                        differences.append(f"Light {i}: color xy={state.get('color', {}).get('xy')} vs {first_color}")
                    if state.get('color_temperature', {}).get('mirek') != first_ct:
                        differences.append(f"Light {i}: ct={state.get('color_temperature', {}).get('mirek')} vs {first_ct}")

                if differences:
                    logger.debug(f"State differences: {differences[:3]}")

                all_same = len(differences) == 0

                if all_same and grouped_light_id:
                    # All lights had the same state - use batch restore!
                    logger.debug("Using batch restore (all lights same state)")
                    restore_state = {
                        "on": {"on": first_on},
                        "dimming": {"brightness": first_brightness},
                        "dynamics": {"duration": config.TRANSITION_TIME * 100}
                    }

                    # Add color if available
                    if first_color:
                        restore_state["color"] = {"xy": {"x": first_color.get('x', 0.3), "y": first_color.get('y', 0.3)}}
                    elif first_ct:
                        restore_state["color_temperature"] = {"mirek": first_ct}

                    try:
                        self.grouped_light_api.set_grouped_light_state(grouped_light_id, restore_state)
                        logger.debug("Batch restore completed")
                    except Exception as e:
                        logger.warning(f"Batch restore failed: {e}")
                        # Fall back to individual restore
                        for light_id, original_state in original_states.items():
                            try:
                                self.restore_light_state(light_id, original_state)
                            except Exception as e:
                                logger.error(f"Error restoring light {light_id}: {e}")
                else:
                    # Lights had different states - restore individually
                    logger.debug("Restoring individually (lights had different states)")
                    for light_id, original_state in original_states.items():
                        try:
                            self.restore_light_state(light_id, original_state)
                        except Exception as e:
                            logger.error(f"Error restoring light {light_id}: {e}")

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
    import argparse

    logger.info("=== Randomizer script started ===")
    randomizer = HueRandomizer()

    parser = argparse.ArgumentParser(description='The Randomizer - Philips Hue light effect')
    parser.add_argument('--zone', metavar='ZONE_ID', dest='zone_id',
                       help='Zone ID (fastest - skips all lookups)')
    parser.add_argument('--room', metavar='ROOM_ID', dest='room_id',
                       help='Room ID (fastest - skips all lookups)')
    parser.add_argument('--group', metavar='GROUP', dest='group_name',
                       help='Group name (slower - requires lookup)')
    parser.add_argument('--duration', type=int, default=None,
                       help='Duration in seconds (default: from config)')
    parser.add_argument('--brightness', type=int, default=100,
                       help='Brightness percent 0-100 (default: 100)')
    parser.add_argument('--grouped-light', metavar='GROUPED_LIGHT_ID', dest='grouped_light_id',
                       help='Grouped light ID for batch operations (optional, auto-detected if not provided)')
    parser.add_argument('--list', action='store_true', help='List available groups and exit')

    args = parser.parse_args()

    # Handle --list
    if args.list:
        print("Available groups (use ID with --zone or --room for fastest startup):")
        groups = randomizer.get_groups()
        for gid, data in groups.items():
            print(f"  ID: {gid}")
            print(f"     Name: {data.get('name')} ({data.get('type')})")
        sys.exit(0)

    # Determine which group to use and whether we can use fast path
    if args.zone_id:
        # Fast path: we know it's a zone
        group_input = args.zone_id
        group_type = 'Zone'
    elif args.room_id:
        # Fast path: we know it's a room
        group_input = args.room_id
        group_type = 'Room'
    elif args.group_name:
        # Slow path: need to look up the group by name
        group_input = args.group_name
        group_type = None
    else:
        parser.error("Must specify either --zone, --room, or --group")

    # Parse brightness as percentage (0-100) and convert to 0-254
    brightness = int((args.brightness / 100.0) * 254)

    # Run the effect with optional grouped_light_id hint
    result = randomizer.run_effect(group_input, args.duration, brightness, group_type, args.grouped_light_id)

    # Print result as JSON for Shortcuts integration
    print(json.dumps(result, indent=2))

    # Exit with appropriate code
    sys.exit(0 if result['success'] else 1)


if __name__ == '__main__':
    main()