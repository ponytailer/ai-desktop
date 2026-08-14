"""控制台入口：允许 `uv run start` / `python -m ai_desktop` 启动开发服务器。"""
import uvicorn


def run() -> None:
    uvicorn.run("ai_desktop.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    run()
