#!/usr/bin/env python3
"""
Simple server startup script
Run the FastAPI server locally for development
"""
import uvicorn
import os

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    
    print(f"Starting server on http://{host}:{port}")
    print(f"Access the API at: http://localhost:{port}")
    print(f"Health check: http://localhost:{port}/health")
    print("\nPress Ctrl+C to stop the server\n")
    
    uvicorn.run(
        "src.entrypoint:app",
        host=host,
        port=port,
        reload=True,  # Auto-reload on code changes
        log_level="info"
    )

