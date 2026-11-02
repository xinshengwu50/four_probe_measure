# Testbenches

Use sim/scripts/run_hdl.py from the package root. The integration bench checks oneF/R window, native-unit selection, FULL/VERIFY/FORCED, open loop, ownership and reset. ALL_Final benches retain motor/safety, ADC/statistics and calculation checks. Only tests with terminalPASS and noFatal/ERROR count as passed; unsupported old fixtures must be updated against the actual interface, never by weakening a safety assertion.
