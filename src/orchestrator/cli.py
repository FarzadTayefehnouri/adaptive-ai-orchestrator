"""CLI Entrypoint for Adaptive AI Orchestrator (Point 24).
Usage:
    adaptive-orchestrator serve
    adaptive-orchestrator run --prompt "..."
    adaptive-orchestrator health
"""
import argparse
import asyncio
import json
import sys
from src.orchestrator.config import settings

def main(argv=None):
    parser = argparse.ArgumentParser(prog="adaptive-orchestrator", description="Adaptive AI Orchestrator CLI")
    sub = parser.add_subparsers(dest="command")

    serve_p = sub.add_parser("serve", help="Start the FastAPI monitoring and orchestration server")
    serve_p.add_argument("--host", default=settings.host, help="Bind host (default 127.0.0.1)")
    serve_p.add_argument("--port", type=int, default=settings.port, help="Bind port (default 8000)")

    run_p = sub.add_parser("run", help="Submit and execute a prompt from the command line")
    run_p.add_argument("--prompt", required=True, help="Task prompt to execute")
    run_p.add_argument("--complexity", default="auto", help="Task complexity (auto/light/moderate/complex)")

    sub.add_parser("health", help="Check orchestrator health and configuration")

    args = parser.parse_args(argv)
    if args.command == "serve":
        import uvicorn
        uvicorn.run("src.orchestrator.api.app:app", host=args.host, port=args.port, log_level="info")
    elif args.command == "run":
        from src.orchestrator.api.app import create_task_v2, V2TaskCreateRequest
        from src.orchestrator.security.auth import UserRole
        res = asyncio.run(create_task_v2(V2TaskCreateRequest(prompt=args.prompt, complexity=args.complexity), role=UserRole.ADMIN))
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif args.command == "health":
        from src.orchestrator.api.app import health_endpoint
        res = asyncio.run(health_endpoint())
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
