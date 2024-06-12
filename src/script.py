# Insert your RTSP stream URLs in the stream_urls list in the main function at the bottom of the script

import cv2
import time
import os
import numpy as np
from pymediainfo import MediaInfo

# Function to download a segment of an RTSP stream
def download_rtsp_segment(rtsp_url, output_file, duration=5):
    print(f"Attempting to download RTSP segment from {rtsp_url}")
    cap = cv2.VideoCapture(rtsp_url)
    if not cap.isOpened():
        print(f"Error: Could not open RTSP stream {rtsp_url}")
        return False
    
    # Get the frame rate and calculate the number of frames to capture
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps == 0:
        fps = 25
    frame_count = int(duration * fps)

    # Write the frames to a video file
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    out = cv2.VideoWriter(output_file, fourcc, fps, (int(cap.get(3)), int(cap.get(4))))

    # Capture the frames
    for _ in range(frame_count):
        ret, frame = cap.read()
        if not ret:
            break
        out.write(frame)

    cap.release()
    out.release()

    print(f"Downloaded RTSP segment from {rtsp_url}")
    return True


def get_bitrate(file_path):
    print(f"Getting bitrate for file {file_path}")
    media_info = MediaInfo.parse(file_path)
    for track in media_info.tracks:
        if track.track_type == "Video":
            if track.bit_rate:
                return track.bit_rate
            elif track.other_bit_rate:
                return float(track.other_bit_rate[0].replace(" ", "").replace("bps", ""))
    return None


def average_bitrate(rtsp_url, observations=1, segment_duration=2): # Default segment duration is 2 seconds and number of observations is 1, change as needed!
    print(f"Calculating average bitrate for {rtsp_url}")
    bitrates = []
    for i in range(observations):
        output_file = f'temp_segment_{i}.avi'
        print(f"Observation {i+1}/{observations}")
        if download_rtsp_segment(rtsp_url, output_file, segment_duration):
            bitrate = get_bitrate(output_file)
            if bitrate:
                print(f"Bitrate for segment {i+1}: {bitrate} bps")
                bitrates.append(bitrate)
            else:
                print(f"Failed to get bitrate for segment {i+1}")
            print(f"Removing temporary file {output_file}")
            os.remove(output_file)
        else:
            print(f"Failed to download segment {i+1}")
        time.sleep(5)
    if bitrates:
        average = np.mean(bitrates)
        print(f"Average bitrate: {average:.2f} bps")
        return average
    print(f"No valid bitrates collected for {rtsp_url}")
    return None

def main(stream_urls):
    for url in stream_urls:
        print(f"Processing URL {url}")
        avg_bitrate = average_bitrate(url)
        if avg_bitrate:
            print(f'The average bitrate for {url} is {avg_bitrate / 1000:.2f} kbps')
        else:
            print(f'No bitrate data collected for {url}')

# Insert your RTSP stream URLs here
if __name__ == '__main__':
    stream_urls = [
        # Example: 'rtsp://ipaddress/stream',
    ]
    main(stream_urls)