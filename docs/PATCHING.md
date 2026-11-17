# How to patch the game .exe (simple guide)

These optional patches change how the cabinet game behaves with the matchmaking server.
Every patch can be undone. You need your own legitimate copy of the game.

> This repo does **not** include the game, the executable, or the patches themselves.
> The patches come as a separate **patch pack** that is shared privately. Ask in the
> [Discord](https://discord.gg/YENXAmjkYX).

## What the patches do

| Patch | What it changes |
|---|---|
| **Pair keep-searching** | A team pair keeps searching for a human match instead of the game cancelling after ~30 seconds and showing the partner-lost / CPU prompt. |
| **Free play, no GAME OVER** | After an online match, losers go back to practice and searching on the same card instead of GAME OVER. (**LossOnly** keeps the 10-win cap.) |

The patches stack, so you can use one or both.

## Easiest way: "Patch game" in the server package

The Windows server package has an optional step, **`4-Patch-Game.bat`**. It does nothing by
itself. It only starts the patch pack if you have one.

1. Get the patch pack from the Discord (a zip named `exvs2-patch-pack-<date>.zip`).
2. Put the zip in the server package folder, next to `4-Patch-Game.bat`
   (or unzip it there into a folder named `patch-pack`).
3. **Close every cabinet game and the Live Monitor (LM).** Card servers can stay running.
4. Double-click **`4-Patch-Game.bat`**. If it finds the zip, it asks to unpack it, then opens the patch menu.
   Without a pack it just says so and links back here.
5. The first time, type the folder that **contains** your game folders, for example `E:\EXVS2` if your
   copies are `E:\EXVS2\EXVS2IB_V29`, `E:\EXVS2\EXVS2IB_V29_P2`, and so on. Folder names don't matter:
   it finds every copy of the cabinet game in there. It remembers the folder for next time.
6. Pick what to do:

   ```
     1) Status of every game folder
     2) Apply PAIR patch          (pairs keep searching, no partner-lost prompt)
     3) Apply FREE PLAY patch     (no GAME OVER on free play - FULL)
     4) Apply FREE PLAY patch     (LossOnly: only a loss/draw keeps playing)
     5) Undo PAIR patch
     6) Undo FREE PLAY patch
     7) Change where to look / search again
     Q) Quit
   ```

   Before it changes anything, it lists each game folder, what's in it now and what it will be after.
   Then type **Y** to go, **D** for a test run that changes nothing, or anything else to cancel.

What the patch pack checks for you:

- **Only your exact game version.** Each game file is checked against the known versions first.
  An unknown or already-modified file is refused and left alone.
- **Only the cabinet game.** The LM program (`vsac29_Release_LM.exe`) is never touched, even when it
  shares a folder with a cabinet.
- **Not while running.** A folder is skipped while the cabinet or LM is running from it.
- **Backups.** Each file is backed up to `<game folder>\_re\exe-backup` before every change, and the
  result is checked afterwards. If the check fails, the backup is put back automatically.

**Running more than one cabinet on one PC?** Each copy has its own folder, and **every copy must be
patched**, or pairs will still cancel. The menu patches all copies it found unless you pick some.

## After patching

Start everything in this order: **card servers → LM → cabinets.**

For patched pairs, the matchmaker should have these settings in `server.json`:

| Setting | Value |
|---|---|
| `PairNeverCpu` | `true` |
| `PairCancelQuarantineSeconds` | `0` |
| `CrossWorldTeamRooms` | `false` |

## Quick test

- **Pair:** a team pair searches alone. There should be no partner-lost prompt, and the pair keeps searching.
- **Free play:** lose an online match. You should go back to practice and searching, with no GAME OVER.
- **Force quit:** OPTION → force end should still end the play.

## Undo

Close the cabinets and the LM, run `4-Patch-Game.bat` (or `Patch-Menu.bat` in the pack), and pick
**Undo PAIR patch** or **Undo FREE PLAY patch**. Each one removes only its own patch. To switch free play
between FULL and LossOnly, undo it first, then apply the other one.

If anything goes wrong, copy the original `.exe` back from `_re\exe-backup`
(the file named `vsac29_Release.exe.orig-<date>`). Keep that backup, and never upload or share the `.exe`.

## Command line (advanced)

The pack also has command-line scripts. Run them from a Command Prompt in the pack folder:

```
patch-status.bat
pair-patch-apply.bat -All -DryRun
pair-patch-apply.bat -All
freeplay-patch-apply.bat -All [-LossOnly]
pair-patch-revert.bat -All
freeplay-patch-revert.bat -All
```

- `-All` finds every cabinet copy (`-Root "E:\EXVS2"` says where to look).
- `-GameDir "E:\EXVS2\EXVS2IB_V29"` patches just that folder (several: separate them with `;`).
- `-DryRun` changes nothing. `-Yes` skips the confirmation.

## Patch pack interface (for developers)

The public package contains **no patch data**: no bytes, offsets or executable hashes.
`scripts/patch-game.ps1` only looks for a pack and starts it:

- It looks in these places, in order: `patch-pack\manifest.json`, then `patch-pack\<folder>\manifest.json`,
  then `exvs2-patch-pack-*\manifest.json` next to the package. If none is found, it offers to unpack an
  `exvs2-patch-pack-*.zip` from the package folder into `patch-pack\`.
- `manifest.json` (schema 1):

  ```json
  {
    "schema": 1,
    "name": "exvs2-patch-pack",
    "title": "EXVS2 IB cabinet patch pack",
    "version": "2026.11.16",
    "entry": { "menu": "scripts/patch-menu.ps1" }
  }
  ```

- `entry.menu` must be a `.ps1` inside the pack (no absolute path, no `..`). It is started as
  `<entry.menu> -InstallerRoot <package folder>`, followed by any arguments given to `4-Patch-Game.bat`.
- `release/make-release.sh` refuses to build a release that contains a pack, a patch engine,
  a hash table or other SHA-256 strings, and `.gitignore` keeps pack files out of the repo.

Only use a pack you got from the project Discord. `4-Patch-Game.bat` runs the pack's own script.

## Need help?

Ask in the [Discord](https://discord.gg/YENXAmjkYX) troubleshooting channel. Include which
patches you applied, the error code (for example 21-01), and what was on screen.
