@echo off
REM Double-click this to OPEN the token dashboard with FRESH data.
REM It re-runs the fetch (cloud $ if ANALYTICS_API_KEY is set, else air-gapped no-op),
REM rebuilds the HTML, and opens it. %~dp0 = this scripts\ folder, so no path is hardcoded.
REM Make a desktop shortcut to this file for one-click "open = refresh".
powershell -NoProfile -ExecutionPolicy Bypass -Command ". '%~dp0monitor.ps1'; Show-TokenDashboard -Cloud"
