"""Keep native Qt/Python fault traces visible in unattended test runs.

This module is imported by unittest discovery before UI test modules. It does
not change assertions, Qt behavior or the installed application.
"""
import faulthandler

faulthandler.enable()
