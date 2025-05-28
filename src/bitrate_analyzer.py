import time
import os
import numpy as np
import csv
import argparse
import matplotlib.pyplot as plt
import json
import logging
import tempfile
from pathlib import Path
from datetime import datetime
from tqdm import tqdm
import subprocess
import socket
import urllib.parse

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
        "csv_filename": "bitrate_data.csv",
        "plot_filename": "bitrate_plot.png",
        "stream_urls_file": "stream_urls.csv",
        "log_level": "INFO",
        "retry_attempts": 3,
        "timeout_seconds": 30,
        "connection_timeout": 10,
        "use_udp_fallback": True
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
    """Read stream URLs from a CSV file and construct RTSP URLs with optional authentication."""
    stream_urls = []
    try:
        with open(filename, mode='r', newline='') as file:
            reader = csv.DictReader(file)
            for row in reader:
                ip = row.get('ip', '').strip()
                extended_path = row.get('extended-path', '').strip()
                user = row.get('user', '').strip()
                password = row.get('password', '').strip()
                tvcc_name = row.get('tvcc-name', '').strip()
                
                if ip and extended_path:
                    # Construct RTSP URL based on authentication availability
                    if user and password:
                        rtsp_url = f"rtsp://{user}:{password}@{ip}/{extended_path}"
                    else:
                        rtsp_url = f"rtsp://{ip}/{extended_path}"
                    
                    stream_urls.append(rtsp_url)
                    logging.getLogger(__name__).info(f"Added stream: {tvcc_name} -> {rtsp_url}")
                else:
                    logging.getLogger(__name__).warning(f"Skipping invalid entry: missing IP or extended-path for {tvcc_name}")
    except FileNotFoundError:
        logging.getLogger(__name__).warning(f"Stream URLs file {filename} not found.")
    except Exception as e:
        logging.getLogger(__name__).error(f"Error reading {filename}: {e}")
    return stream_urls

def ensure_output_directory(output_dir):
    """Ensure output directory exists."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)

def check_ffmpeg_availability():
    """Check if FFmpeg is available on the system with Windows winget path detection."""
    import platform
    import glob
    
    # First try the standard PATH check
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              stdout=subprocess.PIPE, 
                              stderr=subprocess.PIPE, 
                              check=True, 
                              text=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    # Windows-specific winget path detection
    if platform.system() == "Windows":
        logger = logging.getLogger(__name__)
        
        # Common winget FFmpeg installation paths
        winget_base = os.path.expanduser(r"~\AppData\Local\Microsoft\WinGet\Packages")
        ffmpeg_patterns = [
            os.path.join(winget_base, "Gyan.FFmpeg*", "ffmpeg-*", "bin", "ffmpeg.exe"),
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\FFmpeg\bin\ffmpeg.exe",
        ]
        
        for pattern in ffmpeg_patterns:
            matches = glob.glob(pattern)
            if matches:
                ffmpeg_path = matches[0]
                bin_dir = os.path.dirname(ffmpeg_path)
                logger.info(f"Found FFmpeg at: {ffmpeg_path}")
                
                # Add to PATH for this session
                current_path = os.environ.get('PATH', '')
                if bin_dir not in current_path:
                    os.environ['PATH'] = bin_dir + os.pathsep + current_path
                    logger.info(f"Added {bin_dir} to PATH for this session")
                
                # Test again
                try:
                    subprocess.run(['ffmpeg', '-version'], 
                                  stdout=subprocess.PIPE, 
                                  stderr=subprocess.PIPE, 
                                  check=True)
                    return True
                except:
                    continue
    
    return False

def test_stream_connectivity(rtsp_url, timeout=5):
    """Test basic connectivity to RTSP stream before analysis."""
    logger = logging.getLogger(__name__)
    
    try:
        # Parse RTSP URL to get host and port
        parsed = urllib.parse.urlparse(rtsp_url)
        host = parsed.hostname
        port = parsed.port or 554  # Default RTSP port
        
        if not host:
            logger.warning(f"Invalid URL format: {rtsp_url}")
            return False
        
        # Test TCP connection
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            logger.info(f"TCP connection to {host}:{port} successful")
            return True
        else:
            logger.warning(f"Cannot connect to {host}:{port} (error: {result})")
            return False
            
    except Exception as e:
        logger.warning(f"Connectivity test failed for {rtsp_url}: {e}")
        return False

def diagnose_rtsp_stream(rtsp_url, timeout=10):
    """Diagnose RTSP stream issues using ffprobe."""
    logger = logging.getLogger(__name__)
    
    try:
        cmd = [
            'ffprobe', 
            '-v', 'error',
            '-rtsp_transport', 'tcp',
            '-rtsp_flags', 'prefer_tcp',
            '-timeout', str(timeout * 1000000),  # Changed from -stimeout to -timeout
            '-show_streams',
            '-show_format',
            '-of', 'json',
            rtsp_url
        ]
        
        logger.info(f"Diagnosing stream: {rtsp_url}")
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            text=True
        )
        
        if result.returncode == 0:
            logger.info("Stream diagnosis successful - stream is accessible")
            return True
        else:
            stderr_output = result.stderr
            logger.warning(f"Stream diagnosis failed: {stderr_output}")
            
            # Analyze common error patterns
            if "Connection refused" in stderr_output:
                logger.error("RTSP server refused connection - check if service is running")
            elif "Invalid data found" in stderr_output:
                logger.error("Invalid stream format - check RTSP path or stream type")
            elif "401 Unauthorized" in stderr_output or "Authentication" in stderr_output:
                logger.error("Authentication required - add credentials to stream_urls.csv")
            elif "404 Not Found" in stderr_output:
                logger.error("Stream path not found - verify the RTSP path")
            elif "timeout" in stderr_output.lower():
                logger.error("Connection timeout - stream may be slow or unresponsive")
            else:
                logger.error(f"Unknown stream error: {stderr_output}")
            
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"Stream diagnosis timeout after {timeout} seconds")
        return False
    except Exception as e:
        logger.error(f"Exception during stream diagnosis: {e}")
        return False

def get_stream_bitrate_direct_tcp(rtsp_url, duration=10, timeout=30, connection_timeout=10):
    """Get bitrate using TCP transport with enhanced error handling."""
    logger = logging.getLogger(__name__)
    
    try:
        # Enhanced FFmpeg command with better RTSP handling
        cmd = [
            'ffmpeg', 
            '-rtsp_transport', 'tcp',
            '-rtsp_flags', 'prefer_tcp',
            '-timeout', str(connection_timeout * 1000000),
            '-analyzeduration', '2000000',  # Increased analyze duration
            '-probesize', '2000000',        # Increased probe size
            '-fflags', '+genpts',           # Generate presentation timestamps
            '-i', rtsp_url,
            '-t', str(duration),
            '-f', 'null',
            '-y',
            '-'
        ]
        
        logger.debug(f"Running FFmpeg TCP command: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            text=True
        )
        
        # Parse FFmpeg output for bitrate information
        stderr_output = result.stderr
        logger.debug(f"FFmpeg TCP stderr: {stderr_output}")
        
        # Check for connection/stream errors
        if "Connection refused" in stderr_output or "No route to host" in stderr_output:
            logger.warning("FFmpeg TCP connection refused")
            return None
        
        if "Invalid data found when processing input" in stderr_output:
            logger.warning("FFmpeg TCP: Invalid stream data")
            return None
            
        if "401 Unauthorized" in stderr_output:
            logger.warning("FFmpeg TCP: Authentication required")
            return None
            
        if "404 Not Found" in stderr_output:
            logger.warning("FFmpeg TCP: Stream path not found")
            return None
            
        if "Connection timed out" in stderr_output or "Server returned 4XX/5XX" in stderr_output:
            logger.warning("FFmpeg TCP: Connection timeout or server error")
            return None
        
        # Look for bitrate information in FFmpeg output with multiple patterns
        bitrate = None
        for line in stderr_output.split('\n'):
            # Pattern 1: bitrate= N kbits/s
            if 'bitrate=' in line and 'kbits/s' in line:
                try:
                    bitrate_str = line.split('bitrate=')[1].split('kbits/s')[0].strip()
                    if bitrate_str and bitrate_str != 'N/A':
                        bitrate_kbps = float(bitrate_str)
                        bitrate = int(bitrate_kbps * 1000)
                        logger.info(f"FFmpeg TCP reports stream bitrate: {bitrate_kbps:.2f} kbps")
                        break
                except (ValueError, IndexError):
                    continue
            
            # Pattern 2: speed= throughput info
            if 'speed=' in line and 'size=' in line:
                try:
                    # Extract size and time information for calculation
                    size_match = line.split('size=')[1].split()[0].strip()
                    if 'kB' in size_match:
                        size_kb = float(size_match.replace('kB', ''))
                        estimated_bitrate = (size_kb * 8 * 1000) / duration  # Convert to bps
                        if not bitrate:  # Only use if we don't have a better measurement
                            bitrate = int(estimated_bitrate)
                            logger.info(f"FFmpeg TCP estimated bitrate from size: {estimated_bitrate/1000:.2f} kbps")
                except (ValueError, IndexError):
                    continue
        
        if result.returncode != 0 and not bitrate:
            logger.warning(f"FFmpeg TCP failed with return code {result.returncode}")
            return None
        
        return bitrate
        
    except subprocess.TimeoutExpired:
        logger.warning(f"FFmpeg TCP timeout after {timeout} seconds")
        return None
    except Exception as e:
        logger.error(f"Exception during FFmpeg TCP analysis: {e}")
        return None

def get_stream_bitrate_direct_udp(rtsp_url, duration=10, timeout=30):
    """Get bitrate using UDP transport as fallback."""
    logger = logging.getLogger(__name__)
    
    try:
        cmd = [
            'ffmpeg', 
            '-rtsp_transport', 'udp',
            '-analyzeduration', '2000000',
            '-probesize', '2000000',
            '-fflags', '+genpts',
            '-i', rtsp_url,
            '-t', str(duration),
            '-f', 'null',
            '-y',
            '-'
        ]
        
        logger.debug(f"Running FFmpeg UDP command: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            text=True
        )
        
        stderr_output = result.stderr
        logger.debug(f"FFmpeg UDP stderr: {stderr_output}")
        
        # Look for bitrate information with multiple patterns
        bitrate = None
        for line in stderr_output.split('\n'):
            if 'bitrate=' in line and 'kbits/s' in line:
                try:
                    bitrate_str = line.split('bitrate=')[1].split('kbits/s')[0].strip()
                    if bitrate_str and bitrate_str != 'N/A':
                        bitrate_kbps = float(bitrate_str)
                        bitrate = int(bitrate_kbps * 1000)
                        logger.info(f"FFmpeg UDP reports stream bitrate: {bitrate_kbps:.2f} kbps")
                        break
                except (ValueError, IndexError):
                    continue
        
        if result.returncode != 0 and not bitrate:
            logger.warning(f"FFmpeg UDP failed with return code {result.returncode}")
            return None
        
        return bitrate
        
    except subprocess.TimeoutExpired:
        logger.warning(f"FFmpeg UDP timeout after {timeout} seconds")
        return None
    except Exception as e:
        logger.error(f"Exception during FFmpeg UDP analysis: {e}")
        return None

def get_stream_bitrate_simple(rtsp_url, duration=10, timeout=30):
    """Simple FFmpeg method with minimal options as last resort."""
    logger = logging.getLogger(__name__)
    
    try:
        cmd = [
            'ffmpeg', 
            '-i', rtsp_url,
            '-t', str(duration),
            '-f', 'null',
            '-y',
            '-'
        ]
        
        logger.debug(f"Running simple FFmpeg command: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            text=True
        )
        
        stderr_output = result.stderr
        logger.debug(f"Simple FFmpeg stderr: {stderr_output}")
        
        # Look for bitrate information
        bitrate = None
        for line in stderr_output.split('\n'):
            if 'bitrate=' in line and 'kbits/s' in line:
                try:
                    bitrate_str = line.split('bitrate=')[1].split('kbits/s')[0].strip()
                    if bitrate_str and bitrate_str != 'N/A':
                        bitrate_kbps = float(bitrate_str)
                        bitrate = int(bitrate_kbps * 1000)
                        logger.info(f"Simple FFmpeg reports stream bitrate: {bitrate_kbps:.2f} kbps")
                        break
                except (ValueError, IndexError):
                    continue
        
        return bitrate
        
    except subprocess.TimeoutExpired:
        logger.warning(f"Simple FFmpeg timeout after {timeout} seconds")
        return None
    except Exception as e:
        logger.error(f"Exception during simple FFmpeg analysis: {e}")
        return None

def get_stream_bitrate_direct(rtsp_url, duration=10, timeout=30, connection_timeout=10, use_udp_fallback=True):
    """Get bitrate with TCP first, UDP fallback, then simple method."""
    logger = logging.getLogger(__name__)
    
    # Try TCP first
    logger.debug("Attempting TCP transport...")
    bitrate = get_stream_bitrate_direct_tcp(rtsp_url, duration, timeout, connection_timeout)
    
    if bitrate and bitrate > 0:
        logger.info(f"TCP method successful: {bitrate/1000:.2f} kbps")
        return bitrate
    
    # Try UDP fallback if enabled and TCP failed
    if use_udp_fallback:
        logger.info("TCP failed, trying UDP transport...")
        bitrate = get_stream_bitrate_direct_udp(rtsp_url, duration, timeout)
        if bitrate and bitrate > 0:
            logger.info(f"UDP method successful: {bitrate/1000:.2f} kbps")
            return bitrate
    
    # Try simple method without transport specification
    logger.info("UDP failed, trying simple method...")
    bitrate = get_stream_bitrate_simple(rtsp_url, duration, timeout)
    if bitrate and bitrate > 0:
        logger.info(f"Simple method successful: {bitrate/1000:.2f} kbps")
        return bitrate
    
    # Fallback to file size method
    logger.info("All direct methods failed, trying file size method...")
    return get_stream_bitrate_filesize(rtsp_url, duration, timeout, connection_timeout)

def get_stream_bitrate_filesize(rtsp_url, duration=10, timeout=30, connection_timeout=10):
    """Fallback method: measure bitrate by file size with improved connection handling."""
    logger = logging.getLogger(__name__)
    
    with tempfile.NamedTemporaryFile(suffix='.ts', delete=False) as temp_file:
        output_file = temp_file.name
    
    try:
        cmd = [
            'ffmpeg', '-y',
            '-rtsp_transport', 'tcp',
            '-rtsp_flags', 'prefer_tcp',
            '-timeout', str(connection_timeout * 1000000),  # Changed from -stimeout to -timeout
            '-i', rtsp_url,
            '-t', str(duration),
            '-c', 'copy',
            '-avoid_negative_ts', 'make_zero',
            '-f', 'mpegts',
            output_file
        ]
        
        logger.debug(f"Running FFmpeg filesize command: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            text=True
        )
        
        logger.debug(f"FFmpeg filesize stderr: {result.stderr}")
        
        if result.returncode == 0 and os.path.exists(output_file):
            file_size = os.path.getsize(output_file)
            if file_size > 0:
                bitrate = (file_size * 8) / duration  # bits per second
                logger.info(f"Calculated bitrate from file size: {bitrate/1000:.2f} kbps")
                return int(bitrate)
        
        return None
        
    except subprocess.TimeoutExpired:
        logger.warning(f"FFmpeg filesize timeout after {timeout} seconds")
        return None
    except Exception as e:
        logger.error(f"Exception during file size measurement: {e}")
        return None
    finally:
        # Clean up temporary file
        try:
            if os.path.exists(output_file):
                os.unlink(output_file)
        except:
            pass

def get_declared_bitrate(rtsp_url, timeout=10):
    """Get declared bitrate from stream metadata using ffprobe."""
    logger = logging.getLogger(__name__)
    
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=bit_rate',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            rtsp_url
        ]
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            text=True
        )
        
        if result.returncode == 0 and result.stdout.strip():
            bitrate = int(result.stdout.strip())
            logger.info(f"Stream declares bitrate: {bitrate/1000:.2f} kbps")
            return bitrate
        
        return None
            
    except (subprocess.TimeoutExpired, ValueError, subprocess.CalledProcessError) as e:
        logger.debug(f"ffprobe failed: {e}")
        return None

def select_bitrate_method():
    """Interactive method selection for bitrate measurement."""
    logger = logging.getLogger(__name__)
    
    methods = {
        '1': {
            'name': 'TCP Transport (Direct)',
            'description': 'Uses FFmpeg with TCP transport to measure bitrate directly',
            'function': 'tcp'
        },
        '2': {
            'name': 'UDP Transport (Direct)',
            'description': 'Uses FFmpeg with UDP transport to measure bitrate directly',
            'function': 'udp'
        },
        '3': {
            'name': 'Simple Method (Auto Transport)',
            'description': 'Uses FFmpeg without specifying transport protocol',
            'function': 'simple'
        },
        '4': {
            'name': 'File Size Method',
            'description': 'Downloads stream to file and calculates bitrate from file size',
            'function': 'filesize'
        },
        '5': {
            'name': 'Auto Method (Try All)',
            'description': 'Tries all methods in order until one succeeds',
            'function': 'auto'
        }
    }
    
    print("\n" + "="*60)
    print("BITRATE MEASUREMENT METHOD SELECTION")
    print("="*60)
    print("\nAvailable methods:")
    
    for key, method in methods.items():
        print(f"\n{key}. {method['name']}")
        print(f"   {method['description']}")
    
    print("\n" + "-"*60)
    
    while True:
        try:
            choice = input("\nSelect method (1-5) [default: 4 - File Size]: ").strip()
            
            if not choice:  # Default to file size method
                choice = '4'
            
            if choice in methods:
                selected_method = methods[choice]
                print(f"\nSelected: {selected_method['name']}")
                print(f"Description: {selected_method['description']}")
                
                confirm = input("\nConfirm selection? (y/n) [default: y]: ").strip().lower()
                if not confirm or confirm in ['y', 'yes']:
                    logger.info(f"User selected bitrate method: {selected_method['name']}")
                    return selected_method['function']
                else:
                    print("\nPlease select again:")
                    continue
            else:
                print(f"Invalid choice '{choice}'. Please select 1-5.")
                continue
                
        except KeyboardInterrupt:
            print("\n\nOperation cancelled by user.")
            return None
        except Exception as e:
            print(f"Error: {e}")
            continue

def get_stream_bitrate_by_method(rtsp_url, method, duration=10, timeout=30, connection_timeout=10, use_udp_fallback=True):
    """Get bitrate using the specified method only."""
    logger = logging.getLogger(__name__)
    
    logger.info(f"Using {method} method for bitrate measurement")
    
    if method == 'tcp':
        return get_stream_bitrate_direct_tcp(rtsp_url, duration, timeout, connection_timeout)
    elif method == 'udp':
        return get_stream_bitrate_direct_udp(rtsp_url, duration, timeout)
    elif method == 'simple':
        return get_stream_bitrate_simple(rtsp_url, duration, timeout)
    elif method == 'filesize':
        return get_stream_bitrate_filesize(rtsp_url, duration, timeout, connection_timeout)
    elif method == 'auto':
        return get_stream_bitrate_direct(rtsp_url, duration, timeout, connection_timeout, use_udp_fallback)
    else:
        logger.error(f"Unknown method: {method}")
        return None

def analyze_stream_bitrate(rtsp_url, config, selected_method=None):
    """Analyze stream bitrate using FFmpeg-based methods with enhanced diagnostics."""
    logger = logging.getLogger(__name__)
    logger.info(f"Analyzing bitrate for {rtsp_url}")
    
    # Test connectivity first
    connection_timeout = config.get('connection_timeout', 10)
    if not test_stream_connectivity(rtsp_url, connection_timeout):
        logger.error(f"Stream {rtsp_url} is not accessible - skipping")
        return None, [], None, None, None
    
    # Skip diagnosis for file size method as it's more tolerant
    if selected_method != 'filesize':
        # Diagnose stream format and accessibility
        if not diagnose_rtsp_stream(rtsp_url, connection_timeout):
            logger.warning(f"Stream diagnosis failed for {rtsp_url}")
            
            if selected_method in ['tcp', 'udp', 'simple']:
                logger.error("Selected method requires proper stream diagnosis - skipping")
                logger.info("Troubleshooting suggestions:")
                logger.info("1. Try the 'File Size Method' instead")
                logger.info("2. Verify RTSP path is correct")
                logger.info("3. Check if authentication is required")
                return None, [], None, None, None
            else:
                logger.info("Continuing with selected method despite diagnosis failure...")
    
    bitrates = []
    segment_bitrates = []
    
    samples = config['samples']
    segment_duration = config['segment_duration']
    discard_threshold = config['discard_threshold']
    retry_attempts = config.get('retry_attempts', 3)
    timeout = config.get('timeout_seconds', 30)
    use_udp_fallback = config.get('use_udp_fallback', True)
    
    discard_samples = int(discard_threshold * samples)
    
    # Get declared bitrate from stream metadata (only if not using file size method)
    declared_bitrate = None
    if selected_method != 'filesize':
        declared_bitrate = get_declared_bitrate(rtsp_url)
    
    for i in range(samples):
        logger.info(f"Sample {i+1}/{samples}")
        
        success = False
        for attempt in range(retry_attempts):
            # Use the selected method only
            if selected_method:
                bitrate = get_stream_bitrate_by_method(
                    rtsp_url, 
                    selected_method,
                    segment_duration, 
                    timeout, 
                    connection_timeout,
                    use_udp_fallback
                )
            else:
                # Fallback to auto method
                bitrate = get_stream_bitrate_direct(
                    rtsp_url, 
                    segment_duration, 
                    timeout, 
                    connection_timeout,
                    use_udp_fallback
                )
            
            if bitrate and bitrate > 0:
                logger.info(f"Measured bitrate for sample {i+1}: {bitrate/1000:.2f} kbps")
                
                if i >= discard_samples:
                    bitrates.append(bitrate)
                segment_bitrates.append(bitrate)
                success = True
                break
            else:
                logger.warning(f"Failed to measure bitrate for sample {i+1}, attempt {attempt+1}")
                if attempt < retry_attempts - 1:
                    time.sleep(2)
        
        if not success:
            logger.error(f"Failed to get valid bitrate for sample {i+1} after {retry_attempts} attempts")
        
        # Brief pause between samples
        time.sleep(1)
    
    if bitrates:
        average = np.mean(bitrates)
        std_dev = np.std(bitrates)
        min_bitrate = np.min(bitrates)
        max_bitrate = np.max(bitrates)
        logger.info(f"Average measured bitrate: {average/1000:.2f} kbps (±{std_dev/1000:.2f})")
        
        # Compare with declared bitrate if available
        if declared_bitrate and abs(average - declared_bitrate) / declared_bitrate > 0.1:
            logger.warning(f"Measured bitrate ({average/1000:.2f} kbps) differs from declared ({declared_bitrate/1000:.2f} kbps)")
        
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
        description='Analyze bitrate of RTSP video streams using FFmpeg',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python bitrate_analyzer.py rtsp://example.com/stream1 rtsp://example.com/stream2
  python bitrate_analyzer.py --config custom_config.json --urls-file streams.csv
  python bitrate_analyzer.py --samples 10 --duration 15
  python bitrate_analyzer.py --method filesize  # Use only file size method
  python bitrate_analyzer.py  # Uses default stream_urls.csv if available

Methods:
  tcp      - FFmpeg with TCP transport (direct bitrate measurement)
  udp      - FFmpeg with UDP transport (direct bitrate measurement)  
  simple   - FFmpeg without transport specification
  filesize - Download to file and calculate from file size
  auto     - Try all methods until one succeeds  
  
Requirements:
  FFmpeg must be installed and available in system PATH
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
    parser.add_argument('--method', '-m', 
                       choices=['tcp', 'udp', 'simple', 'filesize', 'auto'],
                       help='Bitrate measurement method (skips interactive selection)')
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
    
    # Check FFmpeg availability - now required
    if not check_ffmpeg_availability():
        logger.error("FFmpeg is required but not found in system PATH")
        logger.error("Please install FFmpeg:")
        logger.error("  Windows: Download from https://ffmpeg.org or use 'winget install FFmpeg'")
        logger.error("  macOS: brew install ffmpeg")
        logger.error("  Linux: sudo apt install ffmpeg")
        return 1
    
    logger.info("FFmpeg detected - ready for accurate bitrate analysis")
    
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
        return 1
    
    # Select bitrate measurement method
    if args.method:
        selected_method = args.method
        logger.info(f"Using command-line specified method: {selected_method}")
    else:
        selected_method = select_bitrate_method()
        if selected_method is None:
            logger.info("No method selected. Exiting.")
            return 1
    
    logger.info(f"Processing {len(stream_urls)} RTSP stream URLs using {selected_method} method")
    
    results = []
    all_segment_bitrates = []
    
    for url in tqdm(stream_urls, desc="Processing streams"):
        logger.info(f"Processing URL: {url}")
        avg_bitrate, segment_bitrates, std_dev, min_br, max_br = analyze_stream_bitrate(url, config, selected_method)
        
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
    
    return 0

if __name__ == '__main__':
    exit(main())
