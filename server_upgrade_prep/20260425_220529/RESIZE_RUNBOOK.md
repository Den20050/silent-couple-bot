# Server Resize Runbook (Timeweb)

This runbook is prepared for current server layout:
- root disk: `/dev/vda1`
- filesystem: `ext4`
- mountpoint: `/`

## 0) Prepared artifacts (already done)

Local folder:
- `server_upgrade_prep/20260425_220529`

Files:
- `silent_couple_bot_20260425_220545.dump` (PostgreSQL backup)
- `sbc_systemd_20260425_220545.tar.gz` (systemd units)
- `sbc_runtime_20260425_220545.tar.gz` (`.env`, nginx, cert renewal config)
- `server_pre_resize_snapshot.txt` (baseline server snapshot)

## 1) Right before clicking "Save changes" in Timeweb

SSH to server:

```bash
ssh root@91.222.237.94
```

Stop bot services to avoid transient callback errors during resize/restart window:

```bash
sudo systemctl stop silent-couple-bot-webhook
sudo systemctl stop silent-couple-bot-worker
```

Keep database/redis up (default).

## 2) After Timeweb operation finishes and server reboots

SSH again:

```bash
ssh root@91.222.237.94
```

Check resources were applied:

```bash
nproc
free -h
lsblk -f
df -h /
```

## 3) If disk size did NOT grow automatically

Install growpart helper (Ubuntu/Debian):

```bash
sudo apt update
sudo apt install -y cloud-guest-utils
```

Grow partition 1 on `/dev/vda`:

```bash
sudo growpart /dev/vda 1
```

Resize ext4 filesystem:

```bash
sudo resize2fs /dev/vda1
```

Verify:

```bash
lsblk -f
df -h /
```

## 4) Start services and validate

Start in this order:

```bash
sudo systemctl start postgresql
sudo systemctl start redis
sudo systemctl start silent-couple-bot-worker
sudo systemctl start silent-couple-bot-webhook
```

Check status:

```bash
sudo systemctl status postgresql --no-pager
sudo systemctl status redis --no-pager
sudo systemctl status silent-couple-bot-worker --no-pager
sudo systemctl status silent-couple-bot-webhook --no-pager
```

Quick logs check:

```bash
sudo journalctl -u silent-couple-bot-webhook --since "15 min ago" --no-pager
sudo journalctl -u silent-couple-bot-worker --since "15 min ago" --no-pager
```

## 5) Telegram smoke test (manual)

From Telegram:
1. `/start`
2. press one inline button
3. run admin statistics command

Expected:
- no long delays
- no `query is too old and response timeout expired` in fresh logs

## 6) Optional hardening after resize

Add swap (recommended even with 4 GB RAM):

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -h
```

## 7) Rollback path (if something goes wrong)

Restore DB:

```bash
sudo -u postgres dropdb --if-exists silent_couple_bot
sudo -u postgres createdb silent_couple_bot
sudo -u postgres pg_restore -d silent_couple_bot /root/silent_couple_bot_20260425_220545.dump
```

Restore configs from backup archive if needed:

```bash
sudo tar -xzf /root/sbc_systemd_20260425_220545.tar.gz -C /
sudo tar -xzf /root/sbc_runtime_20260425_220545.tar.gz -C /
sudo systemctl daemon-reload
```
