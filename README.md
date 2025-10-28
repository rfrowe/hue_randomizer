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
   EFFECT_DURATION=10
   TRANSITION_TIME=0
   ```

## Usage

### Basic Usage

Run the effect on a room/zone:
```bash
poetry run python randomizer.py "Living Room"
```

### Custom Duration

Run for a specific number of seconds:
```bash
poetry run python randomizer.py "Kitchen" 15
```

### Custom Brightness

Set brightness as a percentage (great for nighttime!):
```bash
poetry run python randomizer.py "Bedroom" 10 10  # 10 seconds at 10% brightness
```

### List Available Groups

See all available rooms/zones:
```bash
poetry run python randomizer.py
```

## Configuration

All configuration is managed through the `.env` file:

| Variable | Description | Default |
|----------|-------------|---------|
| `HUE_BRIDGE_HOST` | Your Hue Bridge hostname | Required |
| `HUE_API_KEY` | Your Hue Bridge API key | Required |
| `EFFECT_DURATION` | Default duration in seconds | 10 |
| `TRANSITION_TIME` | Color transition speed (0=instant) | 0 |

## How It Works

1. **Discovery**: Queries the Hue Bridge for all lights in the specified group
2. **State Capture**: Saves the original state of each light
3. **Reachability Check**: Filters out unreachable/offline lights
4. **Threaded Control**: Launches a thread for each light with:
   - Random initial delay (0-2 seconds)
   - Random alternating period (1.5-2.5 seconds)
5. **Color Alternation**: Each light flashes between blue and yellow
6. **Restoration**: All lights return to their original state
7. **Verification**: Double-checks all lights were restored correctly

## Technical Details

### Colors
- **Blue**: Hue 46920 (65% of 65535), Saturation 254
- **Yellow**: Hue 12750 (19% of 65535), Saturation 254

### Safety Features
- 5-second HTTP request timeout (prevents hanging)
- Automatic unreachable light detection and skipping
- Graceful interrupt handling (Ctrl+C)
- Thread cleanup with timeouts
- Force restoration verification
- Comprehensive error logging

### Performance
- Handles 10+ lights simultaneously
- Typical execution time: Duration + 2-3 seconds for setup/cleanup
- Non-blocking threaded execution
- Respects Hue Bridge rate limits (~10 commands/sec per light)

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
