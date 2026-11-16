# How to patch the game .exe (simple guide)

These optional patches change how the cabinet game behaves with the matchmaking server.
Every patch can be undone. You need your own legitimate copy of the game.

> This repo does **not** include the game, the executable, or the patch scripts.
> The scripts are shared privately. Ask in the [Discord](https://discord.gg/YENXAmjkYX).

## What the patches do

| Patch | What it changes |
|---|---|
| **Pair keep-searching** | A team pair keeps searching for a human match instead of the game cancelling after ~30 seconds and showing the partner-lost / CPU prompt. |
| **Free play, no GAME OVER** | After an online match, losers go back to practice and searching on the same card instead of GAME OVER. (`-LossOnly` keeps the 10-win cap.) |

The patches stack, so you can use one or both.

## Before you start

1. **Close every cabinet game.** The scripts refuse to patch a game that is running.
   Card servers can stay running.
2. Put the patch scripts in the `_re` folder inside your main game folder
   (for example `EXVS2IB_V29\_re`).
3. **Don't patch the Live Monitor (LM).** Only the cabinet executable is patched.

## Apply

Open the `_re` folder and run these from a Command Prompt there (or double-click the `.bat` for the main folder only).

1. **Test first (changes nothing):**
   ```
   pair-patch-apply.bat -DryRun
   ```
   It should say your executable is recognized. If it says the version is unknown, stop.
2. **Apply the pair patch:**
   ```
   pair-patch-apply.bat
   ```
3. **Apply the free play patch:**
   ```
   freeplay-patch-apply.bat
   ```

**Running more than one cabinet on one PC?** Each copy has its own folder, and **every
copy must be patched**, or pairs will still cancel. Add `-All` to patch the main folder plus
`_P2`, `_P3` and `_P4`, or use `-GameDir "<folder>"` for one specific folder.

The first time, each folder's original `.exe` is backed up to `<game folder>\_re\exe-backup`.
Keep that backup, and never upload or share the `.exe`.

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

Close the cabinets, then run the matching revert script (add `-All` if you used it):

```
freeplay-patch-revert.bat
pair-patch-revert.bat
```

Each one removes only its own patch. If anything goes wrong, copy the original `.exe` back from
`_re\exe-backup`.

## Need help?

Ask in the [Discord](https://discord.gg/YENXAmjkYX) troubleshooting channel. Include which
patches you applied, the error code (for example 21-01), and what was on screen.
