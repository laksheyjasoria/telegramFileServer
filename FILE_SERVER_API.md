# File Server API Documentation

## Overview

This is a Telegram-based file server API that allows uploading, managing, and retrieving files. All files are stored in Telegram's cloud storage with direct access URLs.

---

## Base Information

- **Base URL**: `http://localhost:5000` (or your server URL)
- **Authentication**: API Key via `X-API-Key` header
- **Content-Type**: `application/json` (for JSON requests)
- **Response Format**: JSON

---

## Authentication

All endpoints (except `/health`) require the `X-API-Key` header:

```
X-API-Key: your_api_key_here
```

---

## File Object Structure

When you receive file details, they contain:

```json
{
  "file_id": "unique_id",
  "filename": "document.pdf",
  "size": 250000,
  "mime_type": "application/pdf",
  "file_type": "document",
  "status": "completed",
  "telegram_file_id": "BQACAgUA...",
  "url": "https://source.url",
  "view_url": "/view/BQACAgUA...",
  "download_url": "https://api.telegram.org/file/bot.../documents/file_1.pdf",
  "created_at": "2026-02-16T10:30:00.000000",
  "updated_at": "2026-02-16T10:30:00.000000",
  "metadata": {}
}
```

| Field | Type | Description |
|-------|------|-------------|
| `file_id` | string | Unique identifier for the file |
| `filename` | string | Original filename with extension |
| `size` | integer | File size in bytes |
| `mime_type` | string | MIME type (e.g., application/pdf) |
| `file_type` | string | Category: audio, video, image, document, other |
| `status` | string | File status: pending, processing, completed, failed |
| `telegram_file_id` | string | Telegram's internal file identifier |
| `url` | string | Original source URL (for imports) |
| `view_url` | string | Internal endpoint to view the file |
| `download_url` | string | Direct URL to download the file |
| `created_at` | string | Creation timestamp (ISO 8601) |
| `updated_at` | string | Last update timestamp (ISO 8601) |
| `metadata` | object | Custom metadata |

---

## File Status

- **pending**: File is queued for processing
- **processing**: File is being processed/uploaded
- **completed**: File is ready to use (✅)
- **failed**: Upload or processing failed (❌)

---

## Endpoints

### 1️⃣ Upload Single File

**Endpoint:** `POST /api/upload`

**Description:** Upload a single file and get the file_id

**Headers:**
```
X-API-Key: your_api_key
```

**Body:** Form Data
```
file: <binary file>
```

**Response (200 OK):**
```json
{
  "file_id": "abc123def456",
  "status": "pending"
}
```

**Error Response (400/500):**
```
null
```

---

### 2️⃣ Upload Multiple Files

**Endpoint:** `POST /api/upload/multiple`

**Description:** Upload multiple files at once

**Headers:**
```
X-API-Key: your_api_key
```

**Body:** Form Data
```
files: [<file1>, <file2>, <file3>...]
```

**Response (200 OK):**
```json
{
  "file_ids": ["id1", "id2", "id3"],
  "errors": []
}
```

**Response with Errors:**
```json
{
  "file_ids": ["id1", "id2"],
  "errors": [
    {
      "filename": "failed_file.txt",
      "error": "error message"
    }
  ]
}
```

---

### 3️⃣ Upload Audio from URL

**Endpoint:** `POST /api/upload/audio`

**Description:** Import audio file from a playable URL

**Headers:**
```
X-API-Key: your_api_key
Content-Type: application/json
```

**Body:** JSON
```json
{
  "url": "https://example.com/audio.mp3",
  "filename": "song.mp3"
}
```

**Response (200 OK):**
```json
{
  "file_id": "audio123",
  "status": "pending"
}
```

**Error Response (400/500):**
```
null
```

---

### 4️⃣ Get File Information

**Endpoint:** `GET /api/file/{file_id}/info`

**Description:** Get complete details about a file

**Headers:**
```
X-API-Key: your_api_key
```

**Response (200 OK):**
```json
{
  "file_id": "abc123",
  "filename": "document.pdf",
  "size": 250000,
  "mime_type": "application/pdf",
  "file_type": "document",
  "status": "completed",
  "telegram_file_id": "BQACAgUA...",
  "url": null,
  "view_url": "/view/BQACAgUA...",
  "download_url": "https://api.telegram.org/file/bot.../documents/file_1.pdf",
  "created_at": "2026-02-16T10:30:00.000000",
  "updated_at": "2026-02-16T10:30:00.000000",
  "metadata": {}
}
```

**Error Response (404):**
```json
{
  "error": "File not found"
}
```

---

### 5️⃣ Get View URL

**Endpoint:** `GET /api/file/{file_id}/view-url`

**Description:** Get the viewable/streaming URL for a file

**Headers:**
```
X-API-Key: your_api_key
```

**Response (200 OK):**
```json
{
  "view_url": "/view/BQACAgUA..."
}
```

**Response (202 - Not Ready):**
```json
{
  "error": "File not ready: pending"
}
```

**Error Response (404):**
```json
{
  "error": "File not found"
}
```

---

### 6️⃣ Get Download URL

**Endpoint:** `GET /api/file/{file_id}/download-url`

**Description:** Get the direct download URL for a file

**Headers:**
```
X-API-Key: your_api_key
```

**Response (200 OK):**
```json
{
  "download_url": "https://api.telegram.org/file/bot.../documents/file_1.pdf"
}
```

**Response (202 - Not Ready):**
```json
{
  "error": "File not ready: processing"
}
```

**Error Response (404):**
```json
{
  "error": "File not found"
}
```

---

### 7️⃣ List All Files

**Endpoint:** `GET /api/files`

**Description:** List all completed files with optional filtering

**Headers:**
```
X-API-Key: your_api_key
```

**Query Parameters:**
- `type` (optional): Filter by type - `audio`, `video`, `image`, `document`, `other`
- `limit` (optional): Maximum files to return (default: 100)

**Example:**
```
GET /api/files?type=image&limit=50
```

**Response (200 OK):**
```json
{
  "total": 2,
  "files": [
    {
      "file_id": "id1",
      "filename": "photo.jpg",
      "size": 172197,
      "mime_type": "image/jpeg",
      "file_type": "image",
      "status": "completed",
      ...
    },
    {
      "file_id": "id2",
      "filename": "document.pdf",
      ...
    }
  ]
}
```

---

### 8️⃣ Delete File

**Endpoint:** `DELETE /api/file/{file_id}`

**Description:** Delete a file from storage

**Headers:**
```
X-API-Key: your_api_key
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "File abc123 deleted"
}
```

**Error Response (404):**
```json
{
  "error": "File not found"
}
```

---

### 9️⃣ Get Server Statistics

**Endpoint:** `GET /api/stats`

**Description:** Get server statistics

**Headers:**
```
X-API-Key: your_api_key
```

**Response (200 OK):**
```json
{
  "total_files": 42,
  "completed": 40,
  "failed": 2,
  "total_size": 157286400,
  "by_type": {
    "audio": 5,
    "video": 3,
    "image": 25,
    "document": 8,
    "other": 1
  }
}
```

---

### 🔟 Health Check

**Endpoint:** `GET /health`

**Description:** Check if server is running (no authentication required)

**Response (200 OK):**
```json
{
  "status": "healthy",
  "service": "Telegram File Server",
  "timestamp": "2026-02-16T10:30:00.000000"
}
```

---

## HTTP Status Codes

| Code | Meaning |
|------|---------|
| `200` | Success ✅ |
| `202` | Accepted - File processing (not ready yet) ⏳ |
| `400` | Bad Request (missing parameters) ❌ |
| `401` | Unauthorized (invalid API key) 🔐 |
| `404` | Not Found (file doesn't exist) 🔍 |
| `500` | Server Error 💥 |

---

## Usage Examples

### Example 1: Upload a File
```bash
curl -X POST http://localhost:5000/api/upload \
  -H "X-API-Key: your_api_key" \
  -F "file=@document.pdf"
```

### Example 2: Get File Info
```bash
curl -X GET http://localhost:5000/api/file/abc123/info \
  -H "X-API-Key: your_api_key"
```

### Example 3: Get Download URL
```bash
curl -X GET http://localhost:5000/api/file/abc123/download-url \
  -H "X-API-Key: your_api_key"
```

### Example 4: Upload Multiple Files
```bash
curl -X POST http://localhost:5000/api/upload/multiple \
  -H "X-API-Key: your_api_key" \
  -F "files=@file1.txt" \
  -F "files=@file2.pdf" \
  -F "files=@file3.jpg"
```

### Example 5: List Files by Type
```bash
curl -X GET "http://localhost:5000/api/files?type=image&limit=10" \
  -H "X-API-Key: your_api_key"
```

---

## Workflow Examples

### Upload and Get Download URL

1. **Upload file:**
   ```
   POST /api/upload
   Response: {"file_id": "abc123", "status": "pending"}
   ```

2. **Wait a moment, then get info:**
   ```
   GET /api/file/abc123/info
   Response: {..., "status": "completed", ...}
   ```

3. **Get download URL:**
   ```
   GET /api/file/abc123/download-url
   Response: {"download_url": "https://..."}
   ```

4. **Download or share the URL**

---

## Error Handling

- **File not found**: GET returns 404 with `{"error": "File not found"}`
- **Upload errors**: File upload returns `null` with error status code
- **Invalid API key**: All endpoints return 401
- **Missing parameters**: Endpoints return 400 with error message

---

## Notes

- File uploads are asynchronous (status: pending)
- Check file info or wait a moment before requesting download URL
- Files persist in Telegram's cloud storage
- All timestamps are in ISO 8601 format (UTC)
- File IDs are unique and permanent (don't expire)
- Short codes were removed; use file_id for all operations

---

## Support

For issues or questions, check the server logs or contact your system administrator.
