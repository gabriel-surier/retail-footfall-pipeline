.PHONY: setup env dirs perms init build-etl up up-local network down logs ps clean \
    check-docker-gid print-docker-gid password \
    deploy reload-streamlit ensure-buckets rebuild

# Default env files, override if needed
ENV_FILE ?= .env
ENV_DOCKER_FILE ?= .env_docker

# DOCKER_GID computed from the socket. := (not =) avoids re-expanding a CLI override as $(shell ...).
DOCKER_GID := $(shell \
    sock=/var/run/docker.sock; \
    test -S "$$sock" || sock=/run/docker.sock; \
    test -S "$$sock" && stat -c '%g' "$$sock")
export DOCKER_GID

# --- Full first-time setup, local dev only: builds+starts minio via up-local ---
setup: env dirs perms network init build-etl up-local
	@echo "Stack ready. Run 'make logs' to follow."
	@$(MAKE) --no-print-directory password

# --- Fail loudly if a required file is missing ---
env:
	@test -f $(ENV_FILE) || (echo "Missing $(ENV_FILE)."; exit 1)
	@test -f $(ENV_DOCKER_FILE) || (echo "Missing $(ENV_DOCKER_FILE)."; exit 1)

# --- Fail loudly if DOCKER_GID could not be resolved ---
check-docker-gid:
	@test -n "$(DOCKER_GID)" || \
	   (echo "Could not resolve DOCKER_GID. Override: make up DOCKER_GID=<gid>."; exit 1)

# --- Print the resolved value, for a quick unit test ---
print-docker-gid:
	@echo "$(DOCKER_GID)"

# --- Create host dirs Airflow writes into ---
dirs:
	mkdir -p orchestration/logs
	mkdir -p orchestration/dags

# --- Chown via throwaway container, no host sudo needed. uid 50000 = airflow user ---
perms: dirs
	docker run --rm \
	   -v "$$(pwd)/orchestration/logs:/logs" \
	   alpine chown -R 50000:0 /logs

# --- Create airflow-net if missing (idempotent). Needed since compose declares it external. ---
# Prod: this network is created by the separate external minio stack, never by this repo.
# Local: nothing else creates it, so run this (or up-local, which includes it) first.
network:
	docker network create airflow-net 2>/dev/null || true

# --- Migrate DB, wait for clean exit before anything else ---
init: check-docker-gid
	docker compose up airflow-init
	@echo "airflow-init done, DB migrated"

# --- Build the ETL image, tagged for on-demand use by DockerOperator, never a standing container ---
build-etl:
	docker compose --profile build-only build etl-rfp

# --- Start the full stack, PROD mode: minio is external, airflow-net must already exist ---
up: check-docker-gid
	docker compose up -d

# --- Start the full stack, LOCAL DEV mode: creates network, builds+starts minio via profile ---
up-local: check-docker-gid network
	docker compose --profile local up -d

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

# --- Reload streamlit only. --no-deps keeps minio and others untouched ---
reload-streamlit: check-docker-gid
	docker compose build streamlit
	docker compose up -d --no-deps streamlit

# --- Ensure bucket exists. required:false on minio dep means this works local or prod ---
ensure-buckets: check-docker-gid
	docker compose run --rm create-buckets

# --- CD pipeline (prod, triggered on merge to main): rebuild ETL, bucket, then streamlit ---
deploy: check-docker-gid build-etl ensure-buckets reload-streamlit
	@echo "Deployment complete."

# --- Print the auto-generated Airflow admin password. Retries: api-server may take a few seconds ---
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
	   echo "Password not ready yet, is api-server up? Retry: make password"; \
	   exit 1; \
	fi; \
	echo "Airflow admin user:     $$user"; \
	echo "Airflow admin password: $$pass"