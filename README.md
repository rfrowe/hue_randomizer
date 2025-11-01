# The Randomizer

A Python script that recreates "The Randomizer" light effect from the TV game show *The Floor*. Control your Philips Hue lights with a chaotic, desynchronized blue-and-yellow flashing pattern.

## What It Does

The Randomizer creates a dramatic lighting effect where all lights in a room/zone alternate between **blue** and **yellow** with:
- **Desynchronized timing**: Each light has a random 0-2 second initial delay
- **Random periods**: Each light changes color every 1.5-2.5 seconds (avg ~2s)
- **Configurable brightness**: Set any brightness level (great for late-night use!)
- **State restoration**: All lights return to their original state after the effect

Perfect for game nights, dramatic entrances, or just having fun with your smart lights!

## Features

- ✨ **Desynchronized multi-light control** - Creates chaotic, eye-catching patterns
- 🎨 **Blue/yellow color scheme** - Matches the original TV show effect
- ⚡ **Fast execution** - Threaded control for instant response
- 🔒 **Safe & robust** - Automatic state restoration, even on interrupts
- 🚨 **Smart filtering** - Automatically skips unreachable lights
- 📊 **Detailed logging** - Know exactly what's happening with your lights
- ⏱️ **Request timeouts** - Never hangs on unresponsive lights
- 🎚️ **Custom brightness** - Set any brightness level (0-100%)

## Requirements

- Python 3.9+
- Philips Hue Bridge on local network
- Poetry (for dependency management)

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd randomizer
   ```

2. **Install dependencies with Poetry**
   ```bash
   poetry install
   ```

3. **Configure your Hue Bridge**

   Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

4. **Get your Hue Bridge hostname and API key**

   The script needs to authenticate with your Hue Bridge:

   **a) Find your bridge hostname:**
   ```bash
   # On macOS/Linux with mDNS:
   dns-sd -L "Hue Bridge - <YOUR_ID>" _hue._tcp local
   ```

   **b) Get an API key:**
   - Press the physical link button on your Hue Bridge
   - Within 30 seconds, run:
   ```bash
   curl -k -X POST https://YOUR-BRIDGE-HOSTNAME.local/api \
     -H "Content-Type: application/json" \
     -d '{"devicetype":"randomizer_app#python"}'
   ```
   - Copy the username from the response (this is your API key)

5. **Update your `.env` file**
   ```env
   HUE_BRIDGE_HOST=your-bridge-hostname.local
   HUE_API_KEY=your-api-key-here
   ```

## Usage

### List Available Groups

See all available rooms/zones with their IDs:
```bash
poetry run python randomizer.py --list
```

### Fast Mode (Recommended)

Use zone or room ID directly for fastest startup:
```bash
# Using zone ID (fastest - skips lookups)
poetry run python randomizer.py --zone "5a5f38bf-98b7-4d35-8cdf-40458deac02d" --duration 5 --brightness 100

# Using room ID
poetry run python randomizer.py --room "ROOM-UUID-HERE" --duration 10 --brightness 50
```

### Name-Based Usage

Use group name (slower due to lookup):
```bash
poetry run python randomizer.py --group "Living Room" --duration 5 --brightness 100
```

### Default Duration and Brightness

Duration defaults to config value, brightness defaults to 100%:
```bash
poetry run python randomizer.py --zone "ZONE-UUID"  # Uses config duration, 100% brightness
```

### macOS Shortcut

For the fastest execution in Shortcuts, use:
```bash
cd /path/to/randomizer && poetry run python randomizer.py --zone "YOUR-ZONE-ID" --duration 5 --brightness 100
```

## Configuration

Only two settings required in `.env`:

| Variable | Description |
|----------|-------------|
| `HUE_BRIDGE_HOST` | Your Hue Bridge hostname (e.g., `whale-island.local`) |
| `HUE_API_KEY` | Your Hue Bridge API key |

All other settings (duration, brightness) are specified via CLI arguments.

## How It Works

1. **Group Lookup**: Finds the zone/room (or uses provided ID)
2. **Batch State Fetch**: Gets all light states in a single API call
3. **Instant Start**: Uses grouped_light API to set all lights to blue simultaneously
4. **Desynchronized Effect**: Each thread:
   - Waits random offset (0.1-2 seconds)
   - Alternates between yellow and blue every 2 seconds
   - Uses shared effect start time for accurate duration
5. **Batch Restore**: If all lights had the same original state, restores in one API call
6. **Individual Restore**: Falls back to per-light restoration if states differed

## Technical Details

### API Architecture
- **CLIP v2 API**: Uses Philips Hue's modern REST API
- **Shared Session**: Connection pooling for optimal performance
- **Batch Operations**: grouped_light endpoint for instant start/restore
- **Modular Design**: Separate API classes (`hue_api.py`) for reusability

### Colors (XY Color Space)
- **Blue**: XY (0.1691, 0.0441)
- **Yellow**: XY (0.5, 0.5)

### Performance Optimizations
- Batch GET for all lights (1 API call vs 10+)
- Batch PUT via grouped_light for instant synchronization
- Connection reuse across all API clients
- 2-second timeouts for fast fallback
- Event-based waiting (no polling)
- API call duration accounted for in timing

### Timing
- Fixed 2-second interval between color changes
- Random 0.1-2s offset creates desynchronization
- Effect duration accuracy: ±10%
- Startup time with --zone: ~2-3 seconds

## Troubleshooting

### Script hangs or times out
- Check that your bridge hostname is correct
- Ensure you're on the same network as your Hue Bridge
- Disable VPN if connected
- Some lights may be unreachable - check logs for warnings

### Lights don't restore properly
- The script verifies and force-restores if needed
- Check the logs for restoration errors
- Unreachable lights can't be restored (they'll return to their state when they come back online)

### "Network is unreachable" error
- Confirm bridge hostname with: `ping YOUR-BRIDGE-HOSTNAME.local`
- Make sure you're on your local network (not VPN)
- Try using the bridge's IP address instead of hostname

## Future Plans

- [ ] iOS Shortcuts integration for quick triggering
- [ ] Sound effect playback alongside lights
- [ ] Custom color schemes (red/green, rainbow, etc.)
- [ ] Web API for remote triggering
- [ ] Configurable timing patterns
- [ ] Support for light groups/scenes

## Inspiration

This project recreates the dramatic lighting effect from the TV game show *The Floor*, where contestants face "The Randomizer" - a suspenseful moment where blue and yellow lights flash chaotically before revealing the outcome.

## License

MIT

## Contributing

Contributions welcome! Feel free to:
- Report bugs
- Suggest features
- Submit pull requests
- Share your custom configurations

---

**Note**: This is an unofficial fan project and is not affiliated with the TV show *The Floor* or its producers.
