.PHONY: setup env dirs perms init build-etl up down logs ps clean

# Default env files, override if needed
ENV_FILE ?= .env
ENV_DOCKER_FILE ?= .env_docker

# --- Full first-time setup, run this once ---
setup: env dirs perms init build-etl up
	@echo "Stack ready. Run 'make logs' to follow."

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
	@grep -q "^DOCKER_GID=" $(ENV_FILE) || \
		(gid=$$(getent group docker | cut -d: -f3); \
		test -n "$$gid" || \
		(echo "No 'docker' group found on host."; exit 1); \
		echo "DOCKER_GID=$$gid" >> $(ENV_FILE))

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
init:
	docker compose up airflow-init
	@echo "airflow-init done, DB migrated"

# --- Build the ETL image, never started as a standing container.
# profile flag required: service is tagged build-only on purpose,
# DockerOperator instantiates it on demand, not compose itself.
build-etl:
	docker compose --profile build-only build etl-rfp

# --- Start the full stack in background ---
up:
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

