# SteamView developer tasks.
#
# Deploying to a Deck is parameterised by environment variables so no
# host, user or path is ever committed. See README.md.

DECK_HOST ?= steamdeck
DECK_USER ?= deck
DECK_PORT ?= 22
DECK_PLUGIN_DIR ?= /home/$(DECK_USER)/homebrew/plugins
PLUGIN_NAME ?= SteamView

SSH := ssh -p $(DECK_PORT) $(DECK_USER)@$(DECK_HOST)
RSYNC := rsync -avz --delete -e "ssh -p $(DECK_PORT)"

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

.PHONY: install
install: ## Install frontend dependencies
	pnpm install --frozen-lockfile

.PHONY: build
build: ## Build dist/index.js
	pnpm run build

.PHONY: watch
watch: ## Rebuild on change
	pnpm run watch

.PHONY: typecheck
typecheck: ## Run tsc --noEmit
	pnpm run typecheck

.PHONY: lint
lint: ## Run eslint
	pnpm run lint

.PHONY: test
test: ## Run the Python test suite
	python3 -m pytest

.PHONY: check
check: typecheck lint test ## Everything CI runs
	python3 scripts/check_stdlib_only.py

.PHONY: package
package: build ## Build the installable plugin ZIP into out/
	python3 scripts/package.py --out-dir out

.PHONY: clean
clean: ## Remove build output
	rm -rf dist out
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

# --- On-device -------------------------------------------------------
#
#   make deploy DECK_HOST=192.168.1.42
#
# Requires SSH access to the Deck (Steam > Settings > System > Enable
# Remote Debugging is not enough; you need sshd running and a password
# set via `passwd` in Desktop Mode).

.PHONY: deploy
deploy: build ## rsync the plugin to a Deck and restart Decky
	@echo "Deploying $(PLUGIN_NAME) to $(DECK_USER)@$(DECK_HOST):$(DECK_PLUGIN_DIR)"
	$(SSH) "mkdir -p $(DECK_PLUGIN_DIR)/$(PLUGIN_NAME)"
	$(RSYNC) \
		--exclude '.git' --exclude 'node_modules' --exclude 'out' \
		--exclude 'tests' --exclude 'src' --exclude '__pycache__' \
		--exclude '.pytest_cache' --exclude 'scripts' \
		plugin.json package.json main.py LICENSE README.md dist py_modules \
		$(DECK_USER)@$(DECK_HOST):$(DECK_PLUGIN_DIR)/$(PLUGIN_NAME)/
	$(MAKE) restart

.PHONY: restart
restart: ## Restart the Decky plugin loader on the Deck
	$(SSH) "sudo systemctl restart plugin_loader"

.PHONY: logs
logs: ## Tail the plugin's log on the Deck
	$(SSH) "tail -f /home/$(DECK_USER)/homebrew/logs/$(PLUGIN_NAME)/plugin.log"
