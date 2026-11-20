# Backups: nightly encrypted copy to a USB drive

Every night the suite makes a password-protected copy of its databases on a USB drive.
It is in addition to the copies in `C:\BiologicalSoftware_Backups` (those are made by the apps
when they close).

## Set up (once per computer)

1. Plug in the USB drive.
2. Install the two packages: `py -3.14 -m pip install pyzipper keyring`
3. See what would happen (changes nothing): `py -3.14 scripts\setup_nightly_backup.py`
4. Set it up: `py -3.14 scripts\setup_nightly_backup.py --drive D: --apply`
   (use the drive's own letter). It must be a drive other than the system drive and the drive holding the data. It asks for a password twice, makes the folder
   `BiologicalSoftware_Backups` on the drive, and creates a scheduled task that runs daily at
   19:00 and ten minutes after each logon, only while you are logged on.
5. **Write the password down** and keep it somewhere safe, away from the computer. Without it the
   backups cannot be opened.

Settings are in `%LOCALAPPDATA%\BiologicalSoftware\backup_settings.json` (time, how many nightly
and monthly zips to keep, days before the warning). They are per computer, not in OneDrive.

## What happens each night

- The working databases (observatum, munia, examen, gamification, lector, codex) are copied safely,
  checked, and put in `<COMPUTER>\nightly\YYYY-MM-DD.zip` on the drive. The most recent 14 are kept (a setting).
- Once a month the zip `<COMPUTER>\monthly\YYYY-MM.zip` also holds every database in the data
  folder and `saved_filters.json`. The most recent 12 are kept (a setting).
- Each zip is re-opened and checked before it is kept. Only then are the oldest zips removed.
  Nothing else on the drive is ever removed.
- `<COMPUTER>\backup_log.txt` on the drive records each night.
- Only one backup runs at a time (a lock file `.backup.lock` in the computer's folder).
- An away copy (laptop) makes no backups.
- If the computer's clock has gone backwards, so that older-looking zips are dated after today,
  nothing is removed and the home screen line turns red until the clock is put right.

## Drive not plugged in

The night is skipped (noted in `%LOCALAPPDATA%\BiologicalSoftware\backup_log.txt`). A missed night
(drive out, or the PC off) is made up the next time you log on with the drive plugged in, or the
next evening. If today's nightly zip already exists, a second run does nothing (add `--force` to
`py -3.14 -m shared.nightly_backup` to make another). The drive is found by its marker file, so its
letter does not matter; network and CD drives are never looked at.

## The warning

The Atrium panel shows "Last backed up: ..." at the bottom. If the last good backup is more than
3 days old (a setting) it turns red: "Last backed up N days ago -- check the backup drive". Plug the drive in.
`py -3.14 -m shared.nightly_backup --status` prints the same line.

## The `_failed` folder

`<COMPUTER>\_failed` holds unfinished zips and stale lock files from a crashed night, moved aside
rather than deleted. It is safe to empty by hand.

## Restore

Always by hand; the instructions are on the drive in `HOW TO RESTORE.txt`. In short: close the
apps, extract the zip with 7-Zip (7-zip.org; Windows' own tool cannot open it), rename the current
database (do not delete it), copy the restored one into the `data` folder, open the app and check.

## Remove

`py -3.14 scripts\setup_nightly_backup.py --remove --apply` removes the scheduled task only. The
drive, the zips and the stored password are left alone.
