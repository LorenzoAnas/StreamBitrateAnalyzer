# RTSP Stream Bitrate Analyzer

This Python script downloads segments of RTSP video streams and calculates the average bitrate with enhanced error handling, configuration management, and logging capabilities.

## Features

- **Configuration Management**: JSON-based configuration with command-line overrides
- **Robust Error Handling**: Retry mechanisms and timeout handling
- **Enhanced Logging**: Detailed logging to both console and file
- **CSV Input/Output**: Read stream URLs from CSV and export detailed results
- **Statistical Analysis**: Calculate average, standard deviation, min/max bitrates
- **Progress Indicators**: Visual progress bars for long-running operations
- **Flexible CLI**: Comprehensive command-line interface

## Requirements

- Python 3.7+
- OpenCV
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

2. Install the required Python packages:
    ```bash
    pip install -r requirements.txt
    ```

3. Ensure that `MediaInfo` is installed on your system. Download from [MediaInfo](https://mediaarea.net/en/MediaInfo).

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

Create a `stream_urls.csv` file with your RTSP URLs:

```csv
URL,Description,Location
rtsp://your_ip_address_1/your_stream_path,Camera 1,Location 1
rtsp://your_ip_address_2/your_stream_path,Camera 2,Location 2
```

## Usage

### Basic Usage

```bash
# Use URLs from stream_urls.csv
python src/bitrate_analyzer.py

# Analyze specific URLs
python src/bitrate_analyzer.py rtsp://example.com/stream1 rtsp://example.com/stream2

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

## Troubleshooting

- Check log files in the `logs/` directory for detailed error information
- Ensure RTSP URLs are accessible and properly formatted
- Verify MediaInfo is installed and accessible
- Check network connectivity and firewall settings

## Example Output

```
2024-01-15 10:30:15 - INFO - Processing 3 RTSP stream URLs
2024-01-15 10:30:20 - INFO - Average bitrate for rtsp://10.154.1.50/channel3/stream2: 2152.54 kbps (±45.23)
2024-01-15 10:30:45 - INFO - Results written to output/bitrate_data.csv
2024-01-15 10:30:46 - INFO - Plot saved to output/bitrate_plot.png
```

