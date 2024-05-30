from enum import Enum

class DestinationType(str, Enum):
    SLACK = "slack"
    CLI = "cli"
