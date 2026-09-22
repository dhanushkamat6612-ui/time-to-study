# ULTRON

Cleaned and reorganized ULTRON project. Run install.bat, then start.bat on Windows.


## First launch
1. Run `install.bat` once.
2. Run `start.bat`.
3. Keep the terminal open while ULTRON is running.
4. If startup fails, `start.bat` now keeps the error visible.

The EventBus module is located at `core/bus.py`, matching the imports used by `server/app.py`.


### v3 fix
The network monitor was corrected for psutil.net_if_addrs() returning lists of address records per interface.
