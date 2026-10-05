### Defensive settings for make:
#     https://tech.davis-hansson.com/p/make/
SHELL:=bash
.ONESHELL:
.SHELLFLAGS:=-xeu -o pipefail -O inherit_errexit -c
.SILENT:
.DELETE_ON_ERROR:
MAKEFLAGS+=--warn-undefined-variables
MAKEFLAGS+=--no-builtin-rules

CURRENT_DIR:=$(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))

IMAGE_NAME:=synology-chat-jitsi-webhook
IMAGE_TAG:=latest
APP_PORT:=5001

# We like colors
# From: https://coderwall.com/p/izxssa/colored-makefile-for-golang-projects
RED=`tput setaf 1`
GREEN=`tput setaf 2`
RESET=`tput sgr0`
YELLOW=`tput setaf 3`

# Add the following 'help' target to your Makefile
# And add help text after each target name starting with '\#\#'
.PHONY: help
help: ## This help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

###########################################
# Environment
###########################################
.PHONY: pre-requirements
pre-requirements:  ## Pre-requirements installation
	@echo "Pre-requirements installation"
	sudo apt update && sudo apt upgrade -y
	sudo apt install -y nginx
	sudo apt install -y certbot python3-certbot-nginx

###########################################
# Container images
###########################################
.PHONY: app-build
app-build:  ## Docker: Build Image
	@echo "Build"
	docker build . -t $(IMAGE_NAME):$(IMAGE_TAG) -f Dockerfile --build-arg APP_PORT=$(APP_PORT)

.PHONY: app-run
app-run: app-build  ## Docker: Running Container
	@echo "Run"
	docker run -d --name $(IMAGE_NAME) --env-file .env -p $(APP_PORT):5001 $(IMAGE_NAME):$(IMAGE_TAG)
