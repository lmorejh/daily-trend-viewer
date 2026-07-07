# 릴스 시드 자동 갱신 (작업 스케줄러용, 무인 실행)
# 결과는 seed_task.log에 기록됩니다.
Set-Location $PSScriptRoot
"===== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') 시드 갱신 시작 =====" >> seed_task.log

$py = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
& $py -X utf8 update_seed.py 2>&1 | Out-File -Append -Encoding utf8 seed_task.log

if ($LASTEXITCODE -ne 0) {
    "수집 실패 — 시드 유지, 푸시 생략" >> seed_task.log
    exit 1
}
git add seed 2>&1 | Out-Null
git -c core.quotepath=false commit -m "chore: 릴스 시드 자동 갱신" 2>&1 |
    Out-File -Append -Encoding utf8 seed_task.log
if ($LASTEXITCODE -eq 0) {
    git push 2>&1 | Out-File -Append -Encoding utf8 seed_task.log
} else {
    "변경 없음 — 푸시 생략" >> seed_task.log
}
"===== 완료 =====" >> seed_task.log
