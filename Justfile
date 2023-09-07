dev:
  DATASETTE_SECRET=abc123 watchexec --signal SIGKILL --restart --clear -e py,ts,html,js,css -- \
    python3 -m datasette --root --memory --setting base_url /based_url/ --internal internal.db
