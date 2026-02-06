# tayzhang-py-backend

FastAPI backend for tayzhang-app personal website.

## Tech Stack

- Python 3.12
- FastAPI (async)
- SQLAlchemy (async)
- Alembic (migrations)
- PostgreSQL 16

## Project Structure

```
tayzhang-py-backend/
├── app/
│   ├── main.py              # FastAPI app entry, middleware setup
│   ├── config.py            # Pydantic settings (env vars)
│   ├── database.py          # Async SQLAlchemy engine
│   ├── security/
│   │   ├── api_key.py       # X-API-Key header validation
│   │   └── rate_limit.py    # slowapi rate limiting
│   ├── models/
│   │   └── base.py          # SQLAlchemy base, timestamp mixin
│   ├── schemas/
│   │   └── post.py          # Pydantic models for API
│   ├── routers/
│   │   ├── health.py        # GET /health (public)
│   │   ├── posts.py         # Posts API endpoints
│   │   └── apps/            # Future: showcase app APIs
│   └── services/            # Business logic layer
├── alembic/                 # Database migrations
├── tests/                   # Test suite (48 tests)
├── Dockerfile
└── requirements.txt
```

## API Endpoints

| Endpoint | Auth | Rate Limit | Description |
|----------|------|------------|-------------|
| `GET /health` | None | None | Health check |
| `GET /api/posts` | Required | 60/min | List posts |
| `GET /api/posts/{slug}` | Required | 60/min | Get single post |
| `GET /api/posts/tags` | Required | 60/min | List all unique tags |
| `GET /api/posts/{slug}/related` | Required | 60/min | Get related posts by shared tags |
| `GET /docs` | None | None | Swagger UI |
| `GET /redoc` | None | None | ReDoc UI |

### Query Parameters

**GET /api/posts**
- `?q=<search>` - Full-text search across title, description, content
- `?tag=<tag>` - Filter posts by tag

## Features

- **Folder-based posts**: Supports `posts/slug/README.md` structure with local images
- **Search**: Full-text search across title, description, and content
- **Tag filtering**: Filter posts by tag
- **Reading time**: Auto-calculated (words / 200 WPM)
- **Related posts**: Returns posts with shared tags

## Authentication

All API endpoints (except `/health`, `/docs`, `/redoc`) require API key:

```
Header: X-API-Key: <api-key>
```

## Development

```bash
# Run with Docker (recommended)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# Run migrations
docker compose exec backend alembic upgrade head

# Create migration
docker compose exec backend alembic revision --autogenerate -m "description"

# Install for local development
pip install -e ".[dev]"
```

## Testing

```bash
# Run test suite
pytest

# Health check (no auth)
curl http://localhost:8000/health

# API endpoints (requires auth)
curl -H "X-API-Key: changeme-in-production" http://localhost:8000/api/posts
curl -H "X-API-Key: changeme-in-production" "http://localhost:8000/api/posts?q=search-term"
curl -H "X-API-Key: changeme-in-production" "http://localhost:8000/api/posts?tag=tech"
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_PASSWORD` | (required) | Database password |
| `API_KEY` | (required) | API authentication key |
| `RATE_LIMIT_PER_MINUTE` | 100 | Global rate limit |
| `DATABASE_URL` | (auto) | PostgreSQL connection string |
| `CONTENT_REPO_PATH` | /app/content | Mounted content directory |
| `CORS_ORIGINS` | localhost:3000 | Allowed CORS origins |
