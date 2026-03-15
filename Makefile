up:
	@docker compose -f docker-compose-dev.yml up --build --force-recreate -d

make-env:
	@cp ./.env.example ./.env