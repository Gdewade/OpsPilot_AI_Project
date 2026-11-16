# Disk Space Full

## Symptoms
- Logs show "No space left on device" or write failures.
- Database or application cannot write files; services fail to start.

## Likely Causes
- Log files grew without rotation.
- Old Docker images, containers or volumes piled up.
- Database WAL files, temporary files or backups filled the disk.
- A large upload or export was not cleaned up.

## Diagnosis
1. Check usage per filesystem: `df -h`.
2. Find large directories: `du -xh / --max-depth=2 | sort -h | tail -20`.
3. Check inode usage: `df -i`.
4. Check Docker usage: `docker system df`.

## Remediation
- Delete or compress old logs and set up log rotation (`logrotate`).
- Remove unused images and containers: `docker system prune` (review before running).
- Move backups to object storage and expand the volume if needed.
- Add a disk usage alert at 80 percent.

## Escalate When
- The database volume is full, because deleting files by hand can corrupt data.
