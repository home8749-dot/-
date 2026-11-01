# ThinkPad X1 Carbon 7th - 일괄 업데이트 + 배터리 확인 (관리자 PowerShell에서 실행)
# 원본 가이드: 노트북_성능최적화_AI구동_가이드_v2_20261101.md

Write-Host "[1/5] 배터리 수명 확인" -ForegroundColor Cyan
powercfg /batteryreport /xml /output "$env:TEMP\battery.xml" | Out-Null
[xml]$b = Get-Content "$env:TEMP\battery.xml"
$b.BatteryReport.Batteries.Battery | ForEach-Object {
  $pct = [math]::Round($_.FullChargeCapacity / $_.DesignCapacity * 100, 1)
  "설계용량 $($_.DesignCapacity) mWh / 완충용량 $($_.FullChargeCapacity) mWh / 잔존 $pct% / 충전횟수 $($_.CycleCount)"
}

Write-Host "[2/5] 설치된 프로그램 전체 업데이트 (winget)" -ForegroundColor Cyan
winget upgrade --all --silent --accept-source-agreements --accept-package-agreements

Write-Host "[3/5] Lenovo Vantage 설치 (스토어)" -ForegroundColor Cyan
winget install --id 9WZDNCRFJ4MV --source msstore --accept-source-agreements --accept-package-agreements

Write-Host "[4/5] 윈도우 업데이트 검사 시작" -ForegroundColor Cyan
UsoClient StartInteractiveScan
Start-Process "ms-settings:windowsupdate"

Write-Host "[5/5] 전원 설정 화면 열기 -> '전원 모드: 최고 성능' 선택" -ForegroundColor Cyan
Start-Process "ms-settings:powersleep"

Write-Host "완료. 위 배터리 줄을 캡처해서 공유하세요." -ForegroundColor Green
