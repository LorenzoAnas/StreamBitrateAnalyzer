import cv2
import time
import os
import numpy as np
from pymediainfo import MediaInfo
import csv
import argparse
import matplotlib.pyplot as plt

samples = 1
segment_duration = 4
discard_threshold = 0.05

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
    # Get the bitrate of the video track, if available
    for track in media_info.tracks:
        if track.track_type == "Video":
            if track.bit_rate:
                return track.bit_rate
            # If the bitrate is not available, try to get it from the other_bit_rate field
            elif track.other_bit_rate:
                return float(track.other_bit_rate[0].replace(" ", "").replace("bps", ""))
    return None

def average_bitrate(rtsp_url, samples, segment_duration, discard_threshold):
    print(f"Calculating average bitrate for {rtsp_url}")
    bitrates = []
    segment_bitrates = []

    discard_samples = int(discard_threshold * samples)  # Discard first 20% of samples, as they may contain initial buffering
    for i in range(samples):
        output_file = f'temp_segment_{i}.avi'
        print(f"Observation {i+1}/{samples}")
        if download_rtsp_segment(rtsp_url, output_file, segment_duration):
            bitrate = get_bitrate(output_file)
            if bitrate:
                print(f"Bitrate for segment {i+1}: {bitrate} bps")
                if i >= discard_samples:
                    bitrates.append(bitrate)
                segment_bitrates.append(bitrate)
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
        return average, segment_bitrates
    print(f"No valid bitrates collected for {rtsp_url}")
    return None, []

def write_to_csv(data, filename):
    with open(filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["IP Address", "Average Bitrate (kbps)"])
        for item in data:
            writer.writerow(item)

def plot_bitrate_over_time(segment_bitrates, stream_urls, segment_duration):
    plt.figure(figsize=(12, 6))
    for i, url in enumerate(stream_urls):
        x = np.arange(1, len(segment_bitrates[i]) + 1) * segment_duration
        y = segment_bitrates[i]
        plt.plot(x, y, marker='o', label=url)

    plt.xlabel('Time (s)')
    plt.ylabel('Bitrate (bps)')
    plt.title('Bitrate over Time')
    plt.legend()
    plt.grid(True)
    plt.savefig('output/bitrate_plot.png')

def main(stream_urls):
    results = []
    all_segment_bitrates = []

    print(f"Processing {len(stream_urls)} RTSP stream URLs")
    for url in stream_urls:
        print(f"Processing URL {url}")
        avg_bitrate, segment_bitrates = average_bitrate(url, samples, segment_duration, discard_threshold)
        if avg_bitrate:
            print(f'The average bitrate for {url} is {avg_bitrate / 1000:.2f} kbps')
            results.append([url, avg_bitrate / 1000])
            all_segment_bitrates.append(segment_bitrates)
        else:
            print(f'No bitrate data collected for {url}')
    write_to_csv(results, 'output/bitrate_data.csv')
    plot_bitrate_over_time(all_segment_bitrates, stream_urls, segment_duration)

# Insert your RTSP stream URLs here
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Process RTSP stream URLs.')
    parser.add_argument('stream_urls', metavar='N', type=str, nargs='*',
                        help='an RTSP stream URL for processing')
    args = parser.parse_args()

    # Default URLs to use if none are passed as arguments
    default_stream_urls = [
                # Add your default stream URLs here
                # PEDASO : 
        'rtsp://10.154.1.50/channel3/stream2',
        
        # MONTE GALLETTO : 
        'rtsp://10.178.8.189/channel3/stream2',

        # SOLAGNE :
        'rtsp://10.154.5.82/channel1/stream2',
    ]

    # Combine the URLs from arguments and default list
    stream_urls = args.stream_urls + default_stream_urls
    main(stream_urls)
