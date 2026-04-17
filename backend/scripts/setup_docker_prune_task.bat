@echo off
:: scripts\setup_docker_prune_task.bat
:: Windows Task Scheduler에 Docker prune 작업 등록/해제
:: 반드시 관리자 권한으로 실행하세요

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [오류] 관리자 권한으로 실행해주세요.
    echo 이 파일을 우클릭 후 "관리자 권한으로 실행"을 선택하세요.
    pause
    exit /b 1
)

set TASK_NAME=HealthGuide-DockerPrune
set XML_PATH=%~dp0docker_prune_task.xml

echo ========================================
echo  Docker Prune 자동화 설정
echo  매주 일요일 새벽 3시 자동 실행
echo ========================================
echo.
echo 1) 작업 등록
echo 2) 작업 해제
echo.
set /p choice="선택 (1/2): "

if "%choice%"=="1" (
    schtasks /create /tn "%TASK_NAME%" /xml "%XML_PATH%" /f
    if %errorlevel% equ 0 (
        echo.
        echo [완료] 작업이 등록되었습니다.
        echo 매주 일요일 새벽 3시에 Docker 미사용 리소스가 자동 정리됩니다.
    ) else (
        echo [오류] 작업 등록에 실패했습니다.
    )
) else if "%choice%"=="2" (
    schtasks /delete /tn "%TASK_NAME%" /f
    if %errorlevel% equ 0 (
        echo [완료] 작업이 해제되었습니다.
    ) else (
        echo [오류] 작업 해제에 실패했습니다. 작업이 존재하지 않을 수 있습니다.
    )
) else (
    echo [오류] 잘못된 선택입니다.
)

echo.
pause
