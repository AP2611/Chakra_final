# Analytics System Setup Guide

## Overview

The analytics system tracks agent performance in real-time, storing data in Redis and displaying it in a dashboard that updates every 3 seconds.

## Setup Instructions

### 1. Start Docker Services

```bash
cd /Users/arjunpanse/Desktop/chakra_full
docker-compose up -d
```

This will start:
- **Redis** on port 6379
- **MySQL** on port 3306

### 2. Install Backend Dependencies

```bash
cd Chakra/backend
pip install -r requirements.txt
```

This installs:
- `redis==5.0.1` - Redis client
- `pymysql==1.1.0` - MySQL client (for future use)

### 3. Install Frontend Dependencies

```bash
cd chakra_ui
npm install
```

This installs:
- `recharts` - Chart library for analytics visualization

### 4. Start Services

**Backend:**
```bash
cd Chakra/backend
python api.py
```

**Frontend:**
```bash
cd chakra_ui
npm run dev
```

## How It Works

### Data Collection

1. **Automatic Recording**: When a task completes through `/process` or `/process-stream`, analytics are automatically recorded
2. **Non-Blocking**: Analytics recording runs in background threads, so it doesn't slow down responses
3. **Metrics Calculated**:
   - Initial score (Yantra output)
   - Final score (Agni output)
   - Improvement percentage
   - Duration
   - Iteration count

### Data Storage (Redis)

- **Task Records**: Stored in Redis hashes (`analytics:task:{id}`)
- **Iterations**: Stored per task (`analytics:iteration:{task_id}:{iter_num}`)
- **Ordering**: Task IDs stored in sorted set by timestamp
- **Cleanup**: Automatically keeps only last 100 tasks

### API Endpoints

- `GET /analytics/metrics` - Overall metrics (avg improvement, latency, accuracy, etc.)
- `GET /analytics/quality-improvement?limit=20` - Quality improvement chart data
- `GET /analytics/performance-history?hours=24` - Performance over time
- `GET /analytics/recent-tasks?limit=10` - Recent tasks for learning history

### Frontend Dashboard

- **Real-Time Updates**: Fetches data every 3 seconds
- **Metrics Cards**: Shows avg improvement, latency, accuracy, total tasks
- **Quality Chart**: Bar chart showing before/after scores
- **Performance Chart**: Line chart showing latency and accuracy over time
- **Learning History**: Table of recent tasks with improvements

## Configuration

### Redis Connection

The system uses environment variables or defaults:
- `REDIS_HOST` (default: `localhost`)
- `REDIS_PORT` (default: `6379`)
- `REDIS_DB` (default: `0`)
- `REDIS_PASSWORD` (default: `None`)

### MySQL (Future Use)

MySQL is set up in docker-compose but not currently used. It's ready for future analytics features.

## Testing

1. Process some tasks through Code Assistant or Document Assistant
2. Navigate to Analytics section in the UI
3. Watch metrics update in real-time (every 3 seconds)
4. See quality improvements and performance history

## Troubleshooting

**Redis Connection Failed:**
- Check if Docker containers are running: `docker ps`
- Check Redis logs: `docker logs chakra_redis`
- Verify port 6379 is not in use

**No Analytics Data:**
- Ensure backend is recording (check console for "✓ Analytics: Connected to Redis")
- Process some tasks first
- Check Redis: `docker exec -it chakra_redis redis-cli KEYS analytics:*`

**Charts Not Showing:**
- Check browser console for errors
- Verify recharts is installed: `npm list recharts`
- Check API responses in Network tab

## Architecture

```
User Task → Backend Processing → Analytics Recording (non-blocking)
                                      ↓
                                  Redis Storage
                                      ↓
                              Analytics API Endpoints
                                      ↓
                              Frontend Dashboard (3s polling)
```

The system is designed to be:
- **Non-blocking**: Analytics don't slow down task processing
- **Real-time**: Dashboard updates every 3 seconds
- **Scalable**: Redis handles high throughput
- **Efficient**: Only keeps last 100 tasks in memory

