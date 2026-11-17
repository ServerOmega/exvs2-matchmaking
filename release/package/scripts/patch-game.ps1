# patch-game.ps1 - optional "Patch game" step of the EXVS2 matchmaking package.
#
# This public script contains NO patch data (no bytes, offsets, exe hashes or disassembly). It only looks for a
# separately distributed patch pack next to this package and starts the pack's own entry script.
# Without a pack it explains where to get one.
#
# Patch pack interface (schema 1), see docs/PATCHING.md "Patch pack interface":
#   <pack>\manifest.json  { "schema": 1, "name": "exvs2-patch-pack", "title": "...", "version": "...",
#                           "entry": { "menu": "scripts/patch-menu.ps1" } }
#   The entry script is started with:  -InstallerRoot <this package folder>   (plus any arguments given here)
# Where the pack may be (first match wins):
#   1. <package>\patch-pack\manifest.json            (folder named patch-pack)
#   2. <package>\patch-pack\<any>\manifest.json      (zip unpacked into patch-pack)
#   3. <package>\exvs2-patch-pack-*\manifest.json    (unpacked next to the package; newest name wins)
#   4. <package>\exvs2-patch-pack-*.zip              (unpacked here on request into patch-pack\)
$ErrorActionPreference = 'Stop'
$Pkg = Split-Path $PSScriptRoot -Parent
$Guide   = 'https://github.com/ServerOmega/exvs2-matchmaking/blob/main/docs/PATCHING.md'
$Discord = 'https://discord.gg/YENXAmjkYX'

function Read-Manifest([string]$dir) {
  $m = Join-Path $dir 'manifest.json'
  if (-not (Test-Path -LiteralPath $m)) { return $null }
  try { $j = Get-Content -LiteralPath $m -Raw | ConvertFrom-Json } catch { Write-Host "  Ignoring $m : not valid JSON." -ForegroundColor Yellow; return $null }
  if ($j.schema -ne 1 -or $j.name -ne 'exvs2-patch-pack') { Write-Host "  Ignoring $m : not an exvs2-patch-pack (schema 1) manifest." -ForegroundColor Yellow; return $null }
  $entry = [string]$j.entry.menu
  # the entry must be a .ps1 inside the pack folder
  if (-not $entry -or $entry -notmatch '\.ps1$' -or [IO.Path]::IsPathRooted($entry) -or $entry -match '(^|[\\/])\.\.([\\/]|$)') {
    Write-Host "  Ignoring $m : bad entry.menu '$entry'." -ForegroundColor Yellow; return $null }
  $full = Join-Path $dir $entry
  if (-not (Test-Path -LiteralPath $full -PathType Leaf)) { Write-Host "  Ignoring $m : entry script missing ($entry)." -ForegroundColor Yellow; return $null }
  return [pscustomobject]@{ Dir = $dir; Title = [string]$j.title; Version = [string]$j.version; Entry = $full }
}

function Find-Pack {
  $cands = @()
  $pp = Join-Path $Pkg 'patch-pack'
  if (Test-Path -LiteralPath $pp -PathType Container) {
    $cands += $pp
    $cands += @(Get-ChildItem -LiteralPath $pp -Directory -ErrorAction SilentlyContinue | Sort-Object Name -Descending | ForEach-Object { $_.FullName })
  }
  $cands += @(Get-ChildItem -LiteralPath $Pkg -Directory -Filter 'exvs2-patch-pack-*' -ErrorAction SilentlyContinue | Sort-Object Name -Descending | ForEach-Object { $_.FullName })
  foreach ($c in $cands) { $p = Read-Manifest $c; if ($p) { return $p } }
  return $null
}

function Show-NoPack {
  Write-Host ''
  Write-Host 'No patch pack found.' -ForegroundColor Yellow
  Write-Host ''
  Write-Host 'Patching the game exe is OPTIONAL. The matchmaking server works without it.'
  Write-Host 'The patches (pairs keep searching, no GAME OVER on free play) come as a separate'
  Write-Host 'patch pack that is not part of this public download.'
  Write-Host ''
  Write-Host "  What the patches do:  $Guide"
  Write-Host "  Get the patch pack:   ask in the Discord  $Discord"
  Write-Host ''
  Write-Host 'Then put the pack next to this file, either as the zip (exvs2-patch-pack-....zip)'
  Write-Host 'or as a folder named patch-pack, and run 4-Patch-Game.bat again.'
  Write-Host "  This package folder:  $Pkg"
}

Write-Host '== EXVS2 - patch game (optional) ==' -ForegroundColor Cyan
$pack = Find-Pack
if (-not $pack) {
  $zip = @(Get-ChildItem -LiteralPath $Pkg -File -Filter 'exvs2-patch-pack-*.zip' -ErrorAction SilentlyContinue | Sort-Object Name -Descending) | Select-Object -First 1
  if ($zip) {
    Write-Host "Found $($zip.Name)."
    $a = Read-Host "Unpack it into $(Join-Path $Pkg 'patch-pack') now? (Y/N)"
    if ($a -match '^[yY]') {
      $ppDir = Join-Path $Pkg 'patch-pack'
      $tmp = Join-Path $ppDir ('.unpack-' + [guid]::NewGuid().ToString('N').Substring(0,8))
      New-Item -ItemType Directory -Force -Path $tmp | Out-Null
      try {
        Expand-Archive -LiteralPath $zip.FullName -DestinationPath $tmp
        # the zip may hold the pack directly or inside one top folder
        $root = $tmp; $inner = @(Get-ChildItem -LiteralPath $tmp -Directory)
        if (-not (Test-Path -LiteralPath (Join-Path $tmp 'manifest.json')) -and $inner.Count -eq 1) { $root = $inner[0].FullName }
        $dest = Join-Path $ppDir ([IO.Path]::GetFileNameWithoutExtension($zip.Name))
        if (Test-Path -LiteralPath $dest) { Remove-Item -LiteralPath $dest -Recurse -Force }
        Move-Item -LiteralPath $root -Destination $dest
      } finally { if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Recurse -Force } }
      $pack = Read-Manifest $dest
    }
  }
}
if (-not $pack) { Show-NoPack; exit 1 }

Write-Host "Patch pack: $($pack.Title) $($pack.Version)"
Write-Host "  from $($pack.Dir)"
Write-Host 'Only use a patch pack you got from the project Discord: this step runs the pack''s own script.' -ForegroundColor DarkGray
Write-Host ''
& $pack.Entry -InstallerRoot $Pkg @args
exit $LASTEXITCODE
