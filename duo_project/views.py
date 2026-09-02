"""Root URL views for the API server."""
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.db import connection
import redis
from datetime import datetime
import psutil
import os


def api_status_dashboard(request):
    """Root page showing API status and available resources."""
    
    # Check database connection
    db_status = "connected"
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        db_status = "disconnected"
    
    # Check Redis connection
    redis_status = "connected"
    try:
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
    except Exception:
        redis_status = "disconnected"
    
    context = {
        "app_name": "Duo API Server",
        "version": "1.0.0",
        "environment": "Development" if settings.DEBUG else "Production",
        "debug_mode": settings.DEBUG,
        "db_status": db_status,
        "redis_status": redis_status,
        "frontend_url": settings.FRONTEND_URL,
        "current_time": datetime.now(),
    }
    
    return render(request, "api_status.html", context)


def api_metrics(request):
    """API endpoint for real-time system metrics."""
    try:
        # Get system metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Get process info
        process = psutil.Process(os.getpid())
        process_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        return JsonResponse({
            "cpu_percent": round(cpu_percent, 1),
            "memory_percent": round(memory.percent, 1),
            "memory_used_mb": round(memory.used / 1024 / 1024, 1),
            "memory_total_mb": round(memory.total / 1024 / 1024, 1),
            "disk_percent": round(disk.percent, 1),
            "disk_used_gb": round(disk.used / 1024 / 1024 / 1024, 1),
            "disk_total_gb": round(disk.total / 1024 / 1024 / 1024, 1),
            "process_memory_mb": round(process_memory, 1),
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
