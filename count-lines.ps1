$exts = '\.(py|java|ts|vue|js|css|html|yml|yaml|xml|sql)$'
$exclude = '(^|/)(node_modules|target|\.venv|venv|__pycache__|dist|build|artifacts|uploads|\.git)(/|$)'

$tracked = git ls-files
$untracked = git ls-files --others --exclude-standard
$files = @($tracked + $untracked) |
  Where-Object { $_ -match $exts -and $_ -notmatch $exclude } |
  Sort-Object -Unique

$totalLines = 0
$totalNonBlank = 0
$stats = @{}

foreach ($f in $files) {
  $content = Get-Content -LiteralPath $f -ErrorAction SilentlyContinue
  $lines = ($content | Measure-Object -Line).Lines
  $nonBlank = ($content | Where-Object { $_.Trim() -ne "" } | Measure-Object -Line).Lines

  $totalLines += $lines
  $totalNonBlank += $nonBlank

  $top = ($f -split '/')[0]
  if (-not $stats.ContainsKey($top)) {
    $stats[$top] = [PSCustomObject]@{
      Files = 0
      Lines = 0
      NonBlank = 0
    }
  }

  $stats[$top].Files += 1
  $stats[$top].Lines += $lines
  $stats[$top].NonBlank += $nonBlank
}

$stats.GetEnumerator() |
  Sort-Object Name |
  ForEach-Object {
    [PSCustomObject]@{
      Module = $_.Name
      Files = $_.Value.Files
      Lines = $_.Value.Lines
      NonBlank = $_.Value.NonBlank
    }
  } |
  Format-Table -AutoSize

"源码文件数: $($files.Count)"
"总行数: $totalLines"
"非空行数: $totalNonBlank"