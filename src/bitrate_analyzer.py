import cv2
import time
import os
import numpy as np
from pymediainfo import MediaInfo
import csv
import argparse
import matplotlib.pyplot as plt
import json
import logging
import tempfile
from pathlib import Path
from datetime import datetime
from tqdm import tqdm

def setup_logging(log_level="INFO"):
    """Set up logging configuration."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / 'bitrate_analyzer.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def load_config(config_file='config.json'):
    """Load configuration from JSON file."""
    default_config = {
        "samples": 5,
        "segment_duration": 10,
        "discard_threshold": 0.2,
        "output_directory": "output",
        "temp_file_prefix": "temp_segment_",
        "csv_filename": "bitrate_data.csv",
        "plot_filename": "bitrate_plot.png",
        "stream_urls_file": "stream_urls.csv",
        "log_level": "INFO",
        "retry_attempts": 3,
        "timeout_seconds": 30
    }
    
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
            # Merge with defaults
            for key, value in default_config.items():
                if key not in config:
                    config[key] = value
            return config
    except FileNotFoundError:
        logger = logging.getLogger(__name__)
        logger.warning(f"Config file {config_file} not found. Using defaults.")
        return default_config
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error loading config: {e}")
        return default_config

def read_stream_urls_from_csv(filename):
    """Read stream URLs from a CSV file."""
    stream_urls = []
    try:
        with open(filename, mode='r', newline='') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row.get('URL', '').strip():
                    stream_urls.append(row['URL'].strip())
    except FileNotFoundError:
        logging.getLogger(__name__).warning(f"Stream URLs file {filename} not found.")
    except Exception as e:
        logging.getLogger(__name__).error(f"Error reading {filename}: {e}")
    return stream_urls

def ensure_output_directory(output_dir):
    """Ensure output directory exists."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)

def download_rtsp_segment(rtsp_url, output_file, duration=5, timeout=30):
    """Enhanced download function with better error handling."""
    logger = logging.getLogger(__name__)
    logger.info(f"Attempting to download RTSP segment from {rtsp_url}")
    
    try:
        cap = cv2.VideoCapture(rtsp_url)
        
        # Set timeout properties
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        if not cap.isOpened():
            logger.error(f"Could not open RTSP stream {rtsp_url}")
            return False
        
        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        if fps <= 0:
            fps = 25
            logger.warning(f"Invalid FPS detected, using default: {fps}")
        
        if width <= 0 or height <= 0:
            logger.error(f"Invalid video dimensions: {width}x{height}")
            cap.release()
            return False
            
        frame_count = int(duration * fps)
        logger.info(f"Capturing {frame_count} frames at {fps} FPS")
        
        # Initialize video writer
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        out = cv2.VideoWriter(output_file, fourcc, fps, (width, height))
        
        frames_captured = 0
        start_time = time.time()
        
        for i in tqdm(range(frame_count), desc="Capturing frames", leave=False):
            if time.time() - start_time > timeout:
                logger.warning(f"Timeout reached while capturing from {rtsp_url}")
                break
                
            ret, frame = cap.read()
            if not ret:
                logger.warning(f"Failed to read frame {i+1}")
                break
            out.write(frame)
            frames_captured += 1
        
        cap.release()
        out.release()
        
        if frames_captured > 0:
            logger.info(f"Successfully captured {frames_captured} frames from {rtsp_url}")
            return True
        else:
            logger.error(f"No frames captured from {rtsp_url}")
            return False
            
    except Exception as e:
        logger.error(f"Exception during download from {rtsp_url}: {e}")
        return False

def get_bitrate(file_path):
    """Extract bitrate from video file using pymediainfo."""
    logger = logging.getLogger(__name__)
    logger.info(f"Getting bitrate for file {file_path}")
    
    try:
        media_info = MediaInfo.parse(file_path)
        for track in media_info.tracks:
            if track.track_type == "Video":
                if track.bit_rate:
                    return track.bit_rate
                elif track.other_bit_rate:
                    return float(track.other_bit_rate[0].replace(" ", "").replace("bps", ""))
    except Exception as e:
        logger.error(f"Error getting bitrate from {file_path}: {e}")
    
    return None

def average_bitrate(rtsp_url, config):
    """Enhanced bitrate calculation with better file handling."""
    logger = logging.getLogger(__name__)
    logger.info(f"Calculating average bitrate for {rtsp_url}")
    
    bitrates = []
    segment_bitrates = []
    
    samples = config['samples']
    segment_duration = config['segment_duration']
    discard_threshold = config['discard_threshold']
    retry_attempts = config.get('retry_attempts', 3)
    timeout = config.get('timeout_seconds', 30)
    
    discard_samples = int(discard_threshold * samples)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        for i in range(samples):
            output_file = Path(temp_dir) / f"{config['temp_file_prefix']}{i}.avi"
            logger.info(f"Observation {i+1}/{samples}")
            
            success = False
            for attempt in range(retry_attempts):
                if download_rtsp_segment(rtsp_url, str(output_file), segment_duration, timeout):
                    bitrate = get_bitrate(str(output_file))
                    if bitrate:
                        logger.info(f"Bitrate for segment {i+1}: {bitrate} bps")
                        if i >= discard_samples:
                            bitrates.append(bitrate)
                        segment_bitrates.append(bitrate)
                        success = True
                        break
                    else:
                        logger.warning(f"Failed to get bitrate for segment {i+1}, attempt {attempt+1}")
                else:
                    logger.warning(f"Failed to download segment {i+1}, attempt {attempt+1}")
                
                if attempt < retry_attempts - 1:
                    time.sleep(2)
            
            if not success:
                logger.error(f"Failed to get valid data for segment {i+1} after {retry_attempts} attempts")
            
            time.sleep(1)
    
    if bitrates:
        average = np.mean(bitrates)
        std_dev = np.std(bitrates)
        min_bitrate = np.min(bitrates)
        max_bitrate = np.max(bitrates)
        logger.info(f"Average bitrate: {average:.2f} bps (±{std_dev:.2f})")
        return average, segment_bitrates, std_dev, min_bitrate, max_bitrate
    
    logger.warning(f"No valid bitrates collected for {rtsp_url}")
    return None, [], None, None, None

def write_to_csv(data, filename):
    """Write results to CSV with enhanced data."""
    logger = logging.getLogger(__name__)
    try:
        with open(filename, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([
                "URL", "Average Bitrate (kbps)", "Std Dev (kbps)", 
                "Min (kbps)", "Max (kbps)", "Samples", "Timestamp"
            ])
            for item in data:
                writer.writerow(item)
        logger.info(f"Results written to {filename}")
    except Exception as e:
        logger.error(f"Failed to write CSV: {e}")

def plot_bitrate_over_time(segment_bitrates, stream_urls, segment_duration, output_file):
    """Enhanced plotting function."""
    logger = logging.getLogger(__name__)
    try:
        plt.figure(figsize=(12, 8))
        for i, url in enumerate(stream_urls):
            if i < len(segment_bitrates) and segment_bitrates[i]:
                x = np.arange(1, len(segment_bitrates[i]) + 1) * segment_duration
                y = [br / 1000 for br in segment_bitrates[i]]  # Convert to kbps
                plt.plot(x, y, marker='o', label=f"Stream {i+1}", linewidth=2, markersize=4)

        plt.xlabel('Time (s)')
        plt.ylabel('Bitrate (kbps)')
        plt.title('Bitrate over Time')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        logger.info(f"Plot saved to {output_file}")
    except Exception as e:
        logger.error(f"Failed to create plot: {e}")

def create_argument_parser():
    """Create and configure argument parser."""
    parser = argparse.ArgumentParser(
        description='Analyze bitrate of RTSP video streams',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python bitrate_analyzer.py rtsp://example.com/stream1 rtsp://example.com/stream2
  python bitrate_analyzer.py --config custom_config.json --urls-file streams.csv
  python bitrate_analyzer.py --samples 10 --duration 15
  python bitrate_analyzer.py  # Uses default stream_urls.csv if available
        """
    )
    
    parser.add_argument('stream_urls', metavar='URL', type=str, nargs='*',
                       help='RTSP stream URLs to analyze')
    parser.add_argument('--config', '-c', default='config.json',
                       help='Configuration file (default: config.json)')
    parser.add_argument('--urls-file', '-f',
                       help='CSV file containing stream URLs (default: stream_urls.csv)')
    parser.add_argument('--samples', '-s', type=int,
                       help='Number of samples to take (overrides config)')
    parser.add_argument('--duration', '-d', type=int,
                       help='Segment duration in seconds (overrides config)')
    parser.add_argument('--output-dir', '-o', 
                       help='Output directory (overrides config)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    return parser

def main():
    """Main function with enhanced argument handling."""
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    
    # Override config with command line arguments
    if args.samples:
        config['samples'] = args.samples
    if args.duration:
        config['segment_duration'] = args.duration
    if args.output_dir:
        config['output_directory'] = args.output_dir
    if args.verbose:
        config['log_level'] = 'DEBUG'
    
    # Setup logging
    logger = setup_logging(config['log_level'])
    
    # Ensure output directory exists
    ensure_output_directory(config['output_directory'])
    
    # Get stream URLs
    stream_urls = []
    if args.stream_urls:
        stream_urls.extend(args.stream_urls)
    
    # Use specified URLs file or default to stream_urls.csv
    urls_file = args.urls_file if args.urls_file else config['stream_urls_file']
    if Path(urls_file).exists():
        logger.info(f"Loading stream URLs from {urls_file}")
        stream_urls.extend(read_stream_urls_from_csv(urls_file))
    elif not args.urls_file:  # Only show warning if using default file
        logger.info(f"Default stream URLs file '{urls_file}' not found. Use --urls-file to specify a different file or provide URLs as arguments.")
    
    if not stream_urls:
        logger.error("No stream URLs provided. Use command line arguments, create stream_urls.csv, or use --urls-file to specify a CSV file")
        return
    
    logger.info(f"Processing {len(stream_urls)} RTSP stream URLs")
    
    results = []
    all_segment_bitrates = []
    
    for url in tqdm(stream_urls, desc="Processing streams"):
        logger.info(f"Processing URL: {url}")
        avg_bitrate, segment_bitrates, std_dev, min_br, max_br = average_bitrate(url, config)
        
        if avg_bitrate:
            avg_kbps = avg_bitrate / 1000
            std_kbps = std_dev / 1000 if std_dev else 0
            min_kbps = min_br / 1000 if min_br else 0
            max_kbps = max_br / 1000 if max_br else 0
            
            logger.info(f'Average bitrate for {url}: {avg_kbps:.2f} kbps (±{std_kbps:.2f})')
            
            results.append([
                url, f"{avg_kbps:.2f}", f"{std_kbps:.2f}", 
                f"{min_kbps:.2f}", f"{max_kbps:.2f}", 
                len(segment_bitrates), datetime.now().isoformat()
            ])
            all_segment_bitrates.append(segment_bitrates)
        else:
            logger.warning(f'No bitrate data collected for {url}')
            all_segment_bitrates.append([])
    
    # Write results
    csv_path = Path(config['output_directory']) / config['csv_filename']
    write_to_csv(results, csv_path)
    
    # Create plot
    plot_path = Path(config['output_directory']) / config['plot_filename']
    plot_bitrate_over_time(all_segment_bitrates, stream_urls, config['segment_duration'], plot_path)

if __name__ == '__main__':
    main()
