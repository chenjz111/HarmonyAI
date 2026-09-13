Add-Type -AssemblyName System.Drawing
$ErrorActionPreference = "Stop"
$outDir = Join-Path $PSScriptRoot "../static/v31-home"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

function New-TabIcon {
  param([string]$Name, [string]$Hex, [ValidateSet("home", "profile")][string]$Kind)
  $bitmap = [Drawing.Bitmap]::new(96, 96, [Drawing.Imaging.PixelFormat]::Format32bppArgb)
  $graphics = [Drawing.Graphics]::FromImage($bitmap)
  $brush = [Drawing.SolidBrush]::new([Drawing.ColorTranslator]::FromHtml($Hex))
  $white = [Drawing.SolidBrush]::new([Drawing.Color]::White)
  try {
    $graphics.SmoothingMode = [Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $graphics.Clear([Drawing.Color]::Transparent)
    if ($Kind -eq "home") {
      $graphics.FillPolygon($brush, [Drawing.Point[]]@(
        [Drawing.Point]::new(12, 42), [Drawing.Point]::new(48, 12),
        [Drawing.Point]::new(84, 42), [Drawing.Point]::new(77, 46),
        [Drawing.Point]::new(77, 80), [Drawing.Point]::new(19, 80),
        [Drawing.Point]::new(19, 46)
      ))
      $graphics.FillRectangle($white, 40, 56, 16, 24)
    } else {
      $graphics.FillEllipse($brush, 33, 11, 30, 30)
      $graphics.FillClosedCurve($brush, [Drawing.Point[]]@(
        [Drawing.Point]::new(18, 80), [Drawing.Point]::new(22, 62),
        [Drawing.Point]::new(34, 50), [Drawing.Point]::new(62, 50),
        [Drawing.Point]::new(74, 62), [Drawing.Point]::new(78, 80)
      ))
    }
    $bitmap.Save((Join-Path $outDir $Name), [Drawing.Imaging.ImageFormat]::Png)
  } finally {
    $white.Dispose()
    $brush.Dispose()
    $graphics.Dispose()
    $bitmap.Dispose()
  }
}

New-TabIcon "nav-home.png" "#989fa0" "home"
New-TabIcon "nav-home-selected.png" "#079777" "home"
New-TabIcon "nav-profile.png" "#989fa0" "profile"
New-TabIcon "nav-profile-selected.png" "#079777" "profile"
