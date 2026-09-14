.PHONY: setup env dirs perms init build-etl up down logs ps clean \
    check-docker-gid print-docker-gid password \
    deploy reload-streamlit ensure-buckets rebuild

# Default env files, override if needed
ENV_FILE ?= .env
ENV_DOCKER_FILE ?= .env_docker

# DOCKER_GID: computed from the socket, not read from a file.
# := (immediate evaluation, once) instead of = (recursive):
# prevents a command-line override from being re-expanded as a
# $(shell ...) function every time the variable is referenced later.
# Never feed this variable from an untrusted CI input
# (workflow_dispatch input, external branch name, etc.).
DOCKER_GID := $(shell \
    sock=/var/run/docker.sock; \
    test -S "$$sock" || sock=/run/docker.sock; \
    test -S "$$sock" && stat -c '%g' "$$sock")
export DOCKER_GID

# --- Full first-time setup, run this once ---
setup: env dirs perms init build-etl up
	@echo "Stack ready. Run 'make logs' to follow."
	@$(MAKE) --no-print-directory password

# --- Fail loudly if a required file is missing ---
env:
	@test -f $(ENV_FILE) || \
	   (echo "Missing $(ENV_FILE)."; \
	   echo "Create it with your MinIO, Postgres,"; \
	   echo "Airflow and store-api variables first."; \
	   exit 1)
	@test -f $(ENV_DOCKER_FILE) || \
	   (echo "Missing $(ENV_DOCKER_FILE)."; \
	   echo "Create it, same vars as $(ENV_FILE)."; \
	   exit 1)

# --- Fail loudly if DOCKER_GID could not be resolved ---
check-docker-gid:
	@test -n "$(DOCKER_GID)" || \
	   (echo "Could not resolve DOCKER_GID."; \
	   echo "No docker.sock at /var/run or /run,"; \
	   echo "or override it: make up DOCKER_GID=<gid>."; \
	   exit 1)

# --- Print the resolved value, for a quick unit test ---
print-docker-gid:
	@echo "$(DOCKER_GID)"

# --- Create host dirs Airflow writes into ---
dirs:
	mkdir -p orchestration/logs
	mkdir -p orchestration/dags

# --- Chown via throwaway container, no host sudo needed ---
# Fixed to uid 50000: the "airflow" user baked into every
# apache/airflow image. No host UID to track or sync, ever.
perms: dirs
	docker run --rm \
	   -v "$$(pwd)/orchestration/logs:/logs" \
	   alpine chown -R 50000:0 /logs

# --- Migrate DB, wait for clean exit before anything else ---
init: check-docker-gid
	docker compose up airflow-init
	@echo "airflow-init done, DB migrated"

# --- Build the ETL image, never started as a standing container.
# profile flag required: service is tagged build-only on purpose,
# DockerOperator instantiates it on demand, not compose itself.
build-etl:
	docker compose --profile build-only build etl-rfp

# --- Start the full stack in background ---
up: check-docker-gid
	docker compose up -d

# --- Stop and remove containers, keep volumes ---
down:
	docker compose down

# --- Tail logs for all running services ---
logs:
	docker compose logs -f

# --- Quick status check on all services ---
ps:
	docker compose ps

# --- Rebuild to reload images and parameters ---
rebuild:
	docker compose up --build -d

# --- Reload streamlit only (rebuild image + recreate container) ---
# --no-deps keeps minio and other services untouched
reload-streamlit: check-docker-gid
	docker compose build streamlit
	docker compose up -d --no-deps streamlit

# --- Ensure the bucket exists, without relying on a "already started" state ---
# run --rm always spins up a fresh one-off container, more reliable in CD
# than "up" on a service that may already be Exited (mc mb --ignore-existing
# handles idempotency)
ensure-buckets: check-docker-gid
	docker compose run --rm create-buckets

# --- Continuous deployment pipeline ---
# Order: rebuild ETL image (never started as a standing container, just
# tagged for the next DockerOperator run), bucket, then streamlit
deploy: check-docker-gid build-etl ensure-buckets reload-streamlit
	@echo "Deployment complete."

# --- Print the auto-generated Airflow admin password.
# Username comes from the container's own env var, not .env,
# so this stays correct even if AIRFLOW_ADMIN_USER changes.
# Retries: api-server may take a few seconds to write the file.
password:
	@user=$$(docker exec api-server printenv \
	   AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_USERS | cut -d: -f1); \
	tries=0; \
	while [ $$tries -lt 15 ]; do \
	   pass=$$(docker exec api-server python3 -c \
	      "import json,sys; \
	      f='/opt/airflow/simple_auth_manager_passwords.json.generated'; \
	      d=json.load(open(f)); \
	      print(d.get(sys.argv[1], ''))" "$$user" 2>/dev/null); \
	   test -n "$$pass" && break; \
	   tries=$$((tries + 1)); \
	   sleep 2; \
	done; \
	if [ -z "$$pass" ]; then \
	   echo "Password not ready yet, is api-server up?"; \
	   echo "Retry in a few seconds: make password"; \
	   exit 1; \
	fi; \
	echo "Airflow admin user:     $$user"; \
	echo "Airflow admin password: $$pass"