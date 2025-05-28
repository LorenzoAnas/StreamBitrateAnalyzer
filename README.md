# RTSP Stream Bitrate Analyzer

This Python script downloads segments of RTSP video streams and calculates the average bitrate with enhanced error handling, configuration management, and logging capabilities.

## Features

- **Accurate Bitrate Measurement**: Uses FFmpeg raw packet capture for precise bitrate analysis
- **Configuration Management**: JSON-based configuration with command-line overrides
- **Authentication Support**: Optional username/password authentication for RTSP streams
- **Robust Error Handling**: Retry mechanisms and timeout handling
- **Enhanced Logging**: Detailed logging to both console and file
- **CSV Input/Output**: Read stream URLs from CSV and export detailed results
- **Statistical Analysis**: Calculate average, standard deviation, min/max bitrates
- **Progress Indicators**: Visual progress bars for long-running operations
- **Flexible CLI**: Comprehensive command-line interface
- **Fallback Support**: OpenCV fallback when FFmpeg is unavailable

## Requirements

- Python 3.7+
- **FFmpeg** (recommended for accurate measurements)
- OpenCV (fallback method)
- numpy
- pymediainfo
- matplotlib
- tqdm

## Installation

1. Clone this repository:
    ```bash
    git clone <repository-url>
    cd StreamBitrateAnalyzer
    ```

2. Install FFmpeg (recommended):
    - **Windows**: Download from [FFmpeg.org](https://ffmpeg.org/download.html) or use `winget install FFmpeg`
    - **macOS**: `brew install ffmpeg`
    - **Linux**: `sudo apt install ffmpeg` (Ubuntu/Debian) or equivalent

3. Install the required Python packages:
    ```bash
    pip install -r requirements.txt
    ```

4. Ensure that `MediaInfo` is installed on your system (for fallback mode). Download from [MediaInfo](https://mediaarea.net/en/MediaInfo).

## Configuration

Create a `config.json` file in the project root:

```json
{
    "samples": 5,
    "segment_duration": 10,
    "discard_threshold": 0.2,
    "output_directory": "output",
    "log_level": "INFO",
    "retry_attempts": 3,
    "timeout_seconds": 30
}
```

Create a `stream_urls.csv` file with your RTSP stream information:

```csv
tvcc-name,ip,extended-path,user,password
Camera 1,192.168.1.100,channel1/stream1,,
Camera 2,192.168.1.101,channel1/stream1,admin,password123
Camera 3,10.0.0.50,live/stream,user,secret
```

**CSV Format:**
- `tvcc-name`: Descriptive name for the camera/stream
- `ip`: IP address of the RTSP server
- `extended-path`: Path component of the RTSP URL (e.g., `channel1/stream1`)
- `user`: Username for authentication (leave empty if not required)
- `password`: Password for authentication (leave empty if not required)

The script will automatically construct RTSP URLs:
- Without auth: `rtsp://192.168.1.100/channel1/stream1`
- With auth: `rtsp://admin:password123@192.168.1.101/channel1/stream1`

## Usage

### Basic Usage

```bash
# Use URLs from stream_urls.csv (default behavior)
python src/bitrate_analyzer.py

# Analyze specific URLs (with manual authentication if needed)
python src/bitrate_analyzer.py rtsp://user:pass@example.com/stream1 rtsp://example.com/stream2

# Use custom configuration
python src/bitrate_analyzer.py --config custom_config.json

# Override specific parameters
python src/bitrate_analyzer.py --samples 10 --duration 15

# Enable verbose logging
python src/bitrate_analyzer.py --verbose
```

### Command Line Options

- `--config, -c`: Specify configuration file (default: config.json)
- `--urls-file, -f`: Specify CSV file with stream URLs
- `--samples, -s`: Number of samples to take per stream
- `--duration, -d`: Segment duration in seconds
- `--output-dir, -o`: Output directory for results
- `--verbose, -v`: Enable verbose logging

## Output

The analyzer generates:

1. **CSV Report** (`output/bitrate_data.csv`): Detailed statistics for each stream
2. **Plot** (`output/bitrate_plot.png`): Bitrate over time visualization
3. **Log File** (`logs/bitrate_analyzer.log`): Detailed execution logs

## Script Components

- **Configuration Management**: JSON-based settings with CLI overrides
- **Stream Processing**: Enhanced RTSP capture with timeout and retry logic
- **Bitrate Analysis**: Statistical analysis of multiple samples
- **Error Handling**: Comprehensive error handling and logging
- **Data Export**: CSV and visualization output

## How It Works

### Accurate Bitrate Measurement

The analyzer uses two methods for bitrate calculation:

1. **FFmpeg Raw Packet Capture (Recommended)**: 
   - Downloads raw stream packets without re-encoding
   - Measures actual network bitrate by analyzing file size vs. duration
   - Provides results that match VLC and other professional tools
   - Also queries stream metadata for declared bitrates

2. **OpenCV Fallback Method**:
   - Used when FFmpeg is not available
   - Re-encodes frames which may affect accuracy
   - Still provides useful estimates but may be 2-3x higher than actual

### Why FFmpeg is More Accurate

The OpenCV method re-encodes video frames, which can introduce significant bitrate inflation:
- Re-encoding with XVID often produces higher bitrates than the source
- FPS detection issues can affect timing calculations
- Unit conversion complexities between different bitrate representations

FFmpeg's copy mode captures exactly what's transmitted over the network without any re-encoding artifacts.

## Troubleshooting

- **Install FFmpeg** for the most accurate results
- Check log files in the `logs/` directory for detailed error information
- Ensure RTSP URLs are accessible and properly formatted
- Verify MediaInfo is installed and accessible (for fallback mode)
- Check network connectivity and firewall settings

## Example Output

```
2024-01-15 10:30:15 - INFO - FFmpeg detected - using accurate raw packet capture method
2024-01-15 10:30:15 - INFO - Processing 3 RTSP stream URLs
2024-01-15 10:30:20 - INFO - Stream metadata declares bitrate: 2048.00 kbps
2024-01-15 10:30:25 - INFO - Measured bitrate for segment 1: 2052341 bps (2052.34 kbps)
2024-01-15 10:30:35 - INFO - Average measured bitrate: 2048532.54 bps (±45.23)
2024-01-15 10:30:45 - INFO - Results written to output/bitrate_data.csv
2024-01-15 10:30:46 - INFO - Plot saved to output/bitrate_plot.png
```

