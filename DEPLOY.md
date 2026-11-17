# Deploying OpsPilot AI on AWS (single EC2 server)

One small Ubuntu server runs the whole stack with Docker Compose. Only Caddy is exposed to the
internet; it provides HTTPS and asks for a username and password before showing the dashboard.

```
Internet ──443──► Caddy (HTTPS + password) ──► Streamlit ──► FastAPI ──► PostgreSQL
                                                                    └──► Redis
```

**Why the password matters:** the dashboard has no login of its own. Without Caddy's password,
anyone who finds the URL could press *Investigate* and spend your OpenAI credits.

## Before you start

1. **AWS Budget alert.** Billing → Budgets → create a monthly cost budget of about $5 with an
   email alert. Do this first.
2. **OpenAI spending limit.** In the OpenAI dashboard set a small monthly limit.
3. **Check your free plan.** Billing → Free Tier shows what your account really includes.
   Free-tier rules differ between accounts and change over time, so do not assume.
4. A public IPv4 address is billed by the hour on AWS, even on a free tier, so expect a few
   dollars a month if you leave the server running.

## 1. Launch the server (EC2 console)

- **AMI:** Ubuntu Server 24.04 LTS.
- **Instance type:** `t3.small` (2 GB RAM) is comfortable. `t3.micro` (1 GB) can work only with
  swap (step 4) and may feel slow, because PostgreSQL, Redis, the API and Streamlit all run on it.
- **Key pair:** create one, download the `.pem` file, keep it private.
- **Storage:** 20 GB gp3.
- **Security group** (inbound rules):
  - SSH (22): **My IP** only.
  - HTTP (80): anywhere. Needed to obtain the HTTPS certificate.
  - HTTPS (443): anywhere.
  - Nothing else. Do **not** open 5432, 6379, 8000 or 8501.

## 2. Give it a fixed address

EC2 → Elastic IPs → Allocate → Associate with your instance. Without this the IP changes every
time the server is stopped and started, and the HTTPS name breaks.

Choose the web address (`SITE_ADDRESS`):
- If you own a domain: create an **A record** pointing to the Elastic IP, and use that domain.
- If not: use `<elastic-ip with dashes>.sslip.io`, for example `13-232-10-5.sslip.io` for
  `13.232.10.5`. It is a free service that resolves such names to the IP, and Caddy can get a
  real certificate for it.

## 3. Connect

From WSL (copy the key into WSL first, Windows folders ignore Linux file permissions):

```bash
mkdir -p ~/.ssh && cp /mnt/c/Users/<you>/Downloads/<key>.pem ~/.ssh/ && chmod 400 ~/.ssh/<key>.pem
ssh -i ~/.ssh/<key>.pem ubuntu@<ELASTIC_IP>
```

## 4. Install Docker and add swap (on the server)

```bash
sudo apt update && sudo apt install -y git curl
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu          # then log out and in again

# 2 GB swap (important on a 1 GB server, harmless on a 2 GB one)
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

Log out, log in again, then check: `docker --version && docker compose version && free -h`.

## 5. Get the code

```bash
git clone https://github.com/<you>/<repo>.git opspilot && cd opspilot
```

For a private repository, clone with a GitHub personal access token or a deploy key. Never put
secrets in the repository.

## 6. Create the secrets file

```bash
cp .env.example .env
nano .env
```

Set at least these (letters and digits only in the database password):

```
OPENAI_API_KEY=sk-...
POSTGRES_PASSWORD=<run: openssl rand -hex 16>
API_KEY=<run: openssl rand -hex 24>
SITE_ADDRESS=13-232-10-5.sslip.io
BASIC_AUTH_USER=gayatri
BASIC_AUTH_HASH='<see below>'
```

Create the password hash (it asks you to type the password you will use to log in):

```bash
docker run --rm -it caddy:2 caddy hash-password
```

Paste the output between **single quotes** as `BASIC_AUTH_HASH`. Then lock the file down:
`chmod 600 .env`.

## 7. Start

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps        # all services should be running / healthy
docker compose -f docker-compose.prod.yml logs -f caddy   # watch the certificate being issued
```

The first build takes several minutes. Then open `https://<SITE_ADDRESS>` in a browser. You
should see a login prompt, then the dashboard. In the sidebar, "AI mode" should say `llm`.

Load demo data once (optional):

```bash
docker compose -f docker-compose.prod.yml exec api python scripts/seed_demo.py
```

## Updating

```bash
cd ~/opspilot && git pull
docker compose -f docker-compose.prod.yml up -d --build
```

Your data stays in the `pgdata` volume.

## Backups

```bash
docker compose -f docker-compose.prod.yml exec -T db pg_dump -U opspilot opspilot > backup_$(date +%F).sql
```

Copy the file off the server (for example to S3). Restore with `psql` into a fresh database.

## Saving money

- Stopping the instance (not terminating) stops compute charges; storage and the Elastic IP
  still cost a little.
- To remove everything: terminate the instance, **release the Elastic IP**, delete the volume
  and snapshots, and delete the key pair if unused.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Browser cannot connect | Security group is missing HTTP/HTTPS, or the Elastic IP is not attached. |
| Certificate error | Caddy could not reach Let's Encrypt: ports 80 and 443 must be open and the name must point to the server. Check `logs caddy`. |
| 502 Bad Gateway | The dashboard is still starting, or crashed. Check `logs frontend`. |
| A service keeps restarting, `Killed` in logs | Out of memory. Add swap (step 4) or use a bigger instance. |
| Compose says a variable is missing | Fill in the named variable in `.env`. |
| "AI mode: offline" in the sidebar | `OPENAI_API_KEY` missing in `.env`. After changing it run `up -d --force-recreate`. |
