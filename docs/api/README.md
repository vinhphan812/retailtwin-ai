# API Documentation

API reference documentation for RetailTwin AI.

## Documents

| Document | Description |
|----------|-------------|
| [API_DOCUMENTATION.md](API_DOCUMENTATION.md) | Complete API reference |

## Quick Links

- [API Documentation](API_DOCUMENTATION.md)

## Base URL

```
Local:    http://127.0.0.1:8000
Production: https://retailtwin-api-*.a.run.app
```

## Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/store` | Get store state |
| GET | `/inventory/{sku}` | Get inventory |
| POST | `/events` | Submit event |
| POST | `/demo/reset` | Reset demo |
| POST | `/demo/start` | Start demo |
| GET | `/demo/status` | Get demo status |
