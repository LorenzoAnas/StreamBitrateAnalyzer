
# RTSP Stream Bitrate Analyzer

This Python script downloads segments of RTSP video streams and calculates the average bitrate. It uses OpenCV to capture the video stream and `pymediainfo` to extract the bitrate information.

## Requirements

- Python 3.x
- OpenCV
- numpy
- pymediainfo

## Installation

1. Clone this repository or download the script files.

2. Install the required Python packages:
    ```
    pip install opencv-python numpy pymediainfo
    ```

3. Ensure that `MediaInfo` is installed on your system. You can download it from [MediaInfo](https://mediaarea.net/en/MediaInfo).

## Usage

1. Update the `stream_urls` list in the script with the RTSP URLs you want to analyze.

2. Run the script:
    ```
    python bitrate_analyzer.py
    ```

## Script Explanation

- `download_rtsp_segment(rtsp_url, output_file, duration=5)`: Downloads a segment of the RTSP stream and saves it to a file.
- `get_bitrate(file_path)`: Extracts the bitrate from the downloaded video file using `pymediainfo`.
- `average_bitrate(rtsp_url, observations=5, segment_duration=5)`: Downloads multiple segments, calculates their bitrates, and returns the average bitrate.
- `main(stream_urls)`: Processes a list of RTSP URLs and prints the average bitrate for each.

## Example

Here's an example of how to use the script:

```python
if __name__ == '__main__':
    stream_urls = [
        'rtsp://your_ip_address_1/your_stream_path',
        'rtsp://your_ip_address_2/your_stream_path',
        # Add more URLs as needed
    ]
    main(stream_urls)
```

The results are then stored in a csv file inside the /output folder of the project

