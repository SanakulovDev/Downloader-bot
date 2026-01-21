# Extract CONTAINER_NAME for use in docker exec command
CONTAINER_NAME := $(shell grep CONTAINER_NAME app/.env | cut -d '=' -f2)

# Point docker-compose to the correct env file for interpolation
DOCKER_COMPOSE := docker-compose --env-file app/.env

.PHONY: build up down logs restart clean exec

make setup:
	$(DOCKER_COMPOSE) build && $(DOCKER_COMPOSE) down && $(DOCKER_COMPOSE) up -d

build:
	$(DOCKER_COMPOSE) build

up:
	$(DOCKER_COMPOSE) up -d

down:
	$(DOCKER_COMPOSE) down

logs:
	$(DOCKER_COMPOSE) logs -f

# Use docker exec -it directly with the container name for interactive shell
exec:
	docker exec -it $(CONTAINER_NAME) /bin/bash

restart: down up

pro:
	git pull origin main && make restart && make logs

clean:
	$(DOCKER_COMPOSE) down -v
	find . -type d -name "__pycache__" -exec rm -rf {} +
