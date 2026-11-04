@echo off
rem Start the meteor counter with radioconda's Python (default install location).
rem radioconda's library folders must be on PATH, as in the Radioconda Prompt;
rem without them SoapySDR cannot load the RTL-SDR driver and no SDR is listed.
set "CONDA=%USERPROFILE%\radioconda"
set "PATH=%CONDA%;%CONDA%\Library\mingw-w64\bin;%CONDA%\Library\usr\bin;%CONDA%\Library\bin;%CONDA%\Scripts;%PATH%"
cd /d "%~dp0"
"%CONDA%\python.exe" -m rt_meteor_counter %*
if errorlevel 1 pause
