.PHONY: setup env dirs perms init build-etl up up-local down logs ps clean \
    check-docker-gid print-docker-gid password \
    deploy reload-streamlit ensure-buckets rebuild

ENV_FILE ?= .env
ENV_DOCKER_FILE ?= .env_docker

# Two -f flags for every prod command that touches running containers:
# docker-compose.prod.yml overrides networks.default to external: true.
PROD_COMPOSE = docker compose -f docker-compose.yml -f docker-compose.prod.yml

DOCKER_GID := $(shell \
    sock=/var/run/docker.sock; \
    test -S "$$sock" || sock=/run/docker.sock; \
    test -S "$$sock" && stat -c '%g' "$$sock")
export DOCKER_GID

setup: env dirs perms init build-etl up-local
	@echo "Stack ready. Run 'make logs' to follow."
	@$(MAKE) --no-print-directory password

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

check-docker-gid:
	@test -n "$(DOCKER_GID)" || \
	   (echo "Could not resolve DOCKER_GID."; \
	   echo "No docker.sock at /var/run or /run,"; \
	   echo "or override it: make up DOCKER_GID=<gid>."; \
	   exit 1)

print-docker-gid:
	@echo "$(DOCKER_GID)"

dirs:
	mkdir -p orchestration/logs
	mkdir -p orchestration/dags

perms: dirs
	docker run --rm \
	   -v "$$(pwd)/orchestration/logs:/logs" \
	   alpine chown -R 50000:0 /logs

init: check-docker-gid
	docker compose up airflow-init
	@echo "airflow-init done, DB migrated"

build-etl:
	docker compose --profile build-only build etl-rfp

# --- PROD: minio is external, never started here ---
up: check-docker-gid
	$(PROD_COMPOSE) up -d

# --- LOCAL DEV: --profile local activates minio in this same file ---
up-local: check-docker-gid
	docker compose --profile local up -d

down:
	docker compose down

logs:
	docker compose logs -f

ps:
	docker compose ps

rebuild:
	$(PROD_COMPOSE) up --build -d

reload-streamlit: check-docker-gid
	$(PROD_COMPOSE) build streamlit
	$(PROD_COMPOSE) up -d --no-deps streamlit

ensure-buckets: check-docker-gid
	$(PROD_COMPOSE) run --rm create-buckets

deploy: check-docker-gid build-etl ensure-buckets reload-streamlit
	@echo "Deployment complete."

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