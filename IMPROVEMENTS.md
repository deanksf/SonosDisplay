# Raspberry Pi Stability Improvements

## Issues Identified and Fixed

### 1. Memory Leaks in Image Processing (`get_metadata_soco.py`)
**Problem**: PIL Image objects were not being explicitly cleaned up, causing memory accumulation over time.

**Solution**:
- Added explicit `img.close()` calls in `finally` blocks
- Added `cleanup_image_objects()` function with forced garbage collection
- Added periodic cleanup every 10 loop iterations
- Added temp file cleanup to remove old `.temp` files

### 2. Excessive System Resource Monitoring
**Problem**: `psutil.cpu_percent(interval=1)` was called every loop iteration, overwhelming the Pi.

**Solution**:
- Reduced resource check frequency from every loop to every 30 seconds
- Added thread-safe resource monitoring with locks
- Implemented overload detection with automatic sleep when system is stressed
- Reduced CPU monitoring interval from 1 second to 0.1 seconds

### 3. Unbounded Thread Growth (`artwork_server.py`)
**Problem**: No limits on concurrent threads or connections, leading to resource exhaustion.

**Solution**:
- Reduced `MAX_CONNECTIONS` from 20 to 10
- Added `MAX_THREADS = 8` limit
- Implemented `verify_request()` to reject connections when thread limit exceeded
- Added socket timeout (30 seconds) to prevent hanging connections

### 4. File I/O Performance Issues
**Problem**: Large chunk sizes and no periodic flushing causing memory buildup.

**Solution**:
- Reduced chunk size from 8KB to 4KB for better Pi performance
- Added periodic `wfile.flush()` every 40KB to prevent memory accumulation
- Added better error handling for file transfers
- Added permission and accessibility checks for Qualia mount point

### 5. Temporary File Accumulation
**Problem**: Temporary files could accumulate and consume disk space.

**Solution**:
- Added `cleanup_temp_files()` function
- Automatic cleanup of files older than 5 minutes
- Periodic cleanup every 10 loop iterations

## Configuration Changes

### Resource Limits
- **CPU Threshold**: 70% (reduced from 80%)
- **Memory Threshold**: 80% (reduced from 85%)
- **Max Threads**: 8 concurrent threads
- **Max Connections**: 10 concurrent connections
- **Request Timeout**: 30 seconds
- **Chunk Size**: 4KB (reduced from 8KB)

### Monitoring Intervals
- **Resource Check**: Every 30 seconds (was every loop)
- **Garbage Collection**: Every 10 loops
- **Temp File Cleanup**: Every 10 loops
- **CPU Monitoring**: 0.1 second interval (was 1 second)

## Expected Improvements

1. **Reduced Memory Usage**: Explicit cleanup should prevent memory leaks
2. **Better CPU Performance**: Reduced monitoring frequency and optimized image processing
3. **Stable Threading**: Limited concurrent connections prevent resource exhaustion
4. **Improved File I/O**: Smaller chunks and periodic flushing reduce memory pressure
5. **Automatic Cleanup**: Temporary files and memory are cleaned up automatically

## Monitoring

The system now provides better logging for:
- Resource usage warnings
- Thread limit rejections
- Memory cleanup operations
- Temporary file cleanup
- File transfer errors

## Recommendations

1. **Monitor logs** for resource warnings and thread rejections
2. **Check system resources** periodically with `htop` or `top`
3. **Restart services** if you see repeated resource warnings
4. **Consider reducing polling frequency** further if issues persist

## Service Files

Both services (`get_metadata_soco.service` and `artwork_server.service`) have:
- `Restart=always` for automatic recovery
- `RestartSec=10` to prevent rapid restart loops
- Proper working directory and user configuration 