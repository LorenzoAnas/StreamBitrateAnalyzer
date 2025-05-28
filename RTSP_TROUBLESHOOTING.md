# RTSP Stream Troubleshooting Guide

## Common Issues and Solutions

### 1. Authentication Required

**Error**: `401 Unauthorized` or `Authentication required`

**Solution**: Add credentials to your `stream_urls.csv`:
```csv
tvcc-name,ip,extended-path,user,password
Camera1,10.184.17.85,t06045920.sdp,admin,password123
```

### 2. Wrong RTSP Path

**Error**: `404 Not Found` or `Stream path not found`

**Common RTSP paths to try**:
- `/stream1`
- `/live`
- `/cam/realmonitor`
- `/h264`
- `/media/video1`
- `/channel1/stream1`
- `/live/main`

### 3. Connection Issues

**Error**: `Connection refused` or `timeout`

**Solutions**:
1. Check if RTSP service is running on the target device
2. Verify firewall settings allow RTSP traffic (port 554)
3. Try UDP transport: add `"use_udp_fallback": true` to config.json

### 4. Manual Testing

Test your stream with VLC:
1. Open VLC Media Player
2. Go to Media → Open Network Stream
3. Enter your RTSP URL: `rtsp://10.184.17.85/t06045920.sdp`
4. If authentication needed: `rtsp://user:pass@10.184.17.85/t06045920.sdp`

Test with FFmpeg directly:
```cmd
ffmpeg -rtsp_transport tcp -i rtsp://10.184.17.85/t06045920.sdp -t 5 -f null -
```

### 5. Network Diagnostics

Check basic connectivity:
```cmd
ping 10.184.17.85
telnet 10.184.17.85 554
```

### 6. Alternative Stream URLs

If `.sdp` extension fails, try:
- `rtsp://10.184.17.85/t06045920`
- `rtsp://10.184.17.85/stream/t06045920`
- `rtsp://10.184.17.85/live/t06045920`

### 7. Camera-Specific Paths

Different camera brands use different paths:
- **Hikvision**: `/Streaming/Channels/101`
- **Dahua**: `/cam/realmonitor?channel=1&subtype=0`
- **Axis**: `/axis-media/media.amp`
- **Foscam**: `/videoMain`
- **Generic**: `/stream1`, `/live`, `/h264`
