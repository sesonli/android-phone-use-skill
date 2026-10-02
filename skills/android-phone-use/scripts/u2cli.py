"""Frozen launcher for the unmodified upstream uiautomator2 agent CLI."""
from runtime import add_vendor, configure_adb

add_vendor()
configure_adb()
from uiautomator2.agent_cli.__main__ import main

if __name__ == '__main__':
    main()
