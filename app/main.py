from fastapi import FastAPI

app = FastAPI(title="Crypto Telemetry Board")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
