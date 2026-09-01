@echo off
set D=E:\EDR\EDRTest\automation\docs

mkdir "%D%\spec" 2>nul
mkdir "%D%\archive" 2>nul
mkdir "%D%\handoff" 2>nul
mkdir "%D%\ai" 2>nul

move /y "%D%\STDOUT_SPEC.md" "%D%\spec\"
move /y "%D%\MAPPING_GUIDE.md" "%D%\spec\"
move /y "%D%\E2E_VALIDATION_METHOD.md" "%D%\spec\"

move /y "%D%\ARCHIVE.md" "%D%\archive\"
move /y "%D%\MAPPING_CHANGELOG.md" "%D%\archive\"

move /y "%D%\BEHAVIOR_LEDGER.md" "%D%\ioa\"
move /y "%D%\FILE_SAMPLE_AUDIT.md" "%D%\ioa\"
move /y "%D%\EDR_TELEMETRY_BASELINE.md" "%D%\ioa\"

move /y "%D%\BASELINE_HANDOFF_V2.md" "%D%\handoff\"
move /y "%D%\FRONTEND_HANDOFF.md" "%D%\handoff\"
move /y "%D%\AI_MAPPING_HANDOFF.md" "%D%\handoff\"
move /y "%D%\ABOUT.md" "%D%\handoff\"

move /y "%D%\AI_MAPPING_METHODOLOGY.md" "%D%\ai\"
move /y "%D%\AI_SUMMARY_SPEC.md" "%D%\ai\"
move /y "%D%\AI_CHAIN_LOG.md" "%D%\ai\"
move /y "%D%\RETEST_BACKLOG.md" "%D%\ai\"

echo Done.
pause
