# Version pinned by default for reproducible builds; override via compose
# build args if a service needs a different runtime.
ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-slim

WORKDIR /app

# Dependencies copied and installed separately from source code
# to avoid busting the pip cache on every code change.
COPY /api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ ./api/
COPY src/sensor/ ./src/sensor/

# ARG does not persist to runtime; promoted to ENV so the port
# is available both at build (EXPOSE) and at container start.
ARG APP_PORT=8002
ENV APP_PORT=${APP_PORT}
EXPOSE ${APP_PORT}

# Single-responsibility container: ENTRYPOINT is intentional here,
# not CMD, so the image cannot be run with an arbitrary command.
# "exec" gives uvicorn PID 1 for correct signal handling on stop/restart.
ENTRYPOINT ["sh", "-c", "exec uvicorn api.store_api:app --host 0.0.0.0 --port ${APP_PORT}"]