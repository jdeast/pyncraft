class Speed:
    FASTEST=0.0005
    FAST=0.001
    MIDDLE=0.005
    SLOW=0.01
    SLOWEST=0.05

SYS_SPEED=Speed.MIDDLE

# Off by default: a library should not print to stdout unless it is asked to.
# Set either to True for the old chatty behaviour.
SHOW_DEBUG=False
SHOW_LOG=False

# old spelling, kept so scripts that set it still work
SHOW_Log=SHOW_LOG
